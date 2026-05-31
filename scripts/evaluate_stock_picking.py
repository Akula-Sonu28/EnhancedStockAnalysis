#!/usr/bin/env python3
"""Evaluate stock-picking IC and hit rates (rank-surface aware).

Writes:
  data/stock_picking_trends.md
  data/stock_picking_outcomes.csv

Re-run after each analysis batch or calibration cycle.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.picking_metrics import (  # noqa: E402
    add_picking_rank_column,
    evaluate_picking_panel,
    filter_rank_surface,
    fill_score_v2_column,
    synthesise_v2_score,
)

HISTORY_PATH = REPO_ROOT / 'data' / 'recommendation_history.csv'
HISTORICAL_OUTCOMES_PATH = REPO_ROOT / 'data' / 'historical_outcomes.csv'
WEIGHTS_PATH = REPO_ROOT / 'data' / 'calibrated_weights_v2.json'
WALKFORWARD_PATH = REPO_ROOT / 'data' / 'walkforward_v2_validation.json'
OUT_MD = REPO_ROOT / 'data' / 'stock_picking_trends.md'
OUT_CSV = REPO_ROOT / 'data' / 'stock_picking_outcomes.csv'


def _load_weights() -> dict:
    if not WEIGHTS_PATH.exists():
        return {}
    try:
        data = json.loads(WEIGHTS_PATH.read_text())
        return data.get('weights') or {}
    except Exception:
        return {}


def _rating_from_metrics(v2_panel: dict, buy_hit: float, buy_n: int) -> tuple:
    ic = v2_panel.get('ic_rho')
    spread = v2_panel.get('spread_pp')
    score = 5.0
    if ic is not None:
        if ic >= 0.08:
            score += 2.0
        elif ic >= 0.05:
            score += 1.0
        elif ic >= 0.0:
            score += 0.0
        elif ic >= -0.05:
            score -= 1.0
        else:
            score -= 2.0
    if spread is not None:
        if spread >= 3.0:
            score += 1.5
        elif spread >= 0:
            score += 0.5
        else:
            score -= 1.5
    if buy_n >= 20 and buy_hit >= 0.75:
        score += 1.0
    elif buy_n >= 10 and buy_hit >= 0.65:
        score += 0.5
    score = max(1.0, min(10.0, score))
    label = (
        'Strong' if score >= 8 else
        'Good' if score >= 6.5 else
        'Moderate' if score >= 5 else
        'Weak' if score >= 3.5 else
        'Poor'
    )
    return round(score, 1), label


def main() -> int:
    if not HISTORY_PATH.exists():
        print(f'ERROR: missing {HISTORY_PATH}')
        return 2

    hist = pd.read_csv(HISTORY_PATH, parse_dates=['date'])
    weights = _load_weights()
    generated = datetime.now().isoformat(timespec='seconds')

    if weights:
        hist = fill_score_v2_column(hist, weights)

    surf = filter_rank_surface(hist)
    surf = add_picking_rank_column(surf)

    v1_panel = evaluate_picking_panel(hist, score_col='score', rank_surface_only=True)
    v2_panel = evaluate_picking_panel(
        hist, score_col='score_v2', rank_surface_only=True, weights=weights or None,
    )
    pick_panel = evaluate_picking_panel(
        surf, score_col='picking_rank', rank_surface_only=False,
    )

    hist_oos_panel = {}
    v1_ho = {}
    if HISTORICAL_OUTCOMES_PATH.exists() and weights:
        ho = pd.read_csv(HISTORICAL_OUTCOMES_PATH)
        ho['score_v2'] = synthesise_v2_score(ho, weights)
        hist_oos_panel = evaluate_picking_panel(
            ho, score_col='score_v2', rank_surface_only=False,
        )
        v1_ho = evaluate_picking_panel(ho, score_col='score', rank_surface_only=False)

    wf_mean_ic = None
    if WALKFORWARD_PATH.exists():
        try:
            wf = json.loads(WALKFORWARD_PATH.read_text())
            folds = wf.get('folds_summary') or {}
            wf_mean_ic = folds.get('mean_ic')
        except Exception:
            pass

    out_rows = []
    for _, r in surf.iterrows():
        ret30 = pd.to_numeric(r.get('return_30d'), errors='coerce')
        bucket = str(r.get('action', ''))
        correct = None
        if pd.notna(ret30):
            if any(x in bucket.upper() for x in ('SELL', 'EXIT', 'REDUCE', 'BOOK', 'WEAK')):
                correct = ret30 < 0
            elif any(x in bucket.upper() for x in ('BUY', 'NEW', 'INCREASE')):
                correct = ret30 > 0
        out_rows.append({
            'date': r.get('date'),
            'symbol': r.get('symbol'),
            'action': r.get('action'),
            'action_bucket': bucket,
            'score': r.get('score'),
            'score_v2': r.get('score_v2'),
            'picking_rank': r.get('picking_rank'),
            'regime': r.get('regime'),
            'sector': r.get('sector'),
            'return_7d': r.get('return_7d'),
            'return_30d': ret30,
            'return_90d': r.get('return_90d'),
            'correct_30d': correct,
        })
    pd.DataFrame(out_rows).to_csv(OUT_CSV, index=False)

    buy = surf[surf['action'].astype(str).str.contains('NEW POSITION|INCREASE|BUY', case=False, na=False)]
    buy30 = buy.dropna(subset=['return_30d'])
    buy_hit = float((buy30['return_30d'] > 0).mean()) if len(buy30) else 0.0
    buy_n = len(buy30)

    sell = hist[hist['action'].astype(str).str.contains('SELL|EXIT|REDUCE|BOOK|WEAK', case=False, na=False)]
    sell30 = sell.dropna(subset=['return_30d'])
    sell_hit = float((sell30['return_30d'] < 0).mean()) if len(sell30) else 0.0
    sell_n = len(sell30)

    rating_panel = v2_panel
    if hist_oos_panel.get('ic_rho') is not None:
        rating_panel = hist_oos_panel
    elif wf_mean_ic is not None:
        rating_panel = {'ic_rho': wf_mean_ic, 'spread_pp': hist_oos_panel.get('spread_pp')}
    rating, label = _rating_from_metrics(rating_panel, buy_hit, buy_n)

    _qmst_badge = 'QMST-BETA'
    _qmst_status_path = REPO_ROOT / 'data' / 'qmst_validation_status.json'
    if _qmst_status_path.exists():
        try:
            _qmst_badge = json.loads(_qmst_status_path.read_text()).get('badge', _qmst_badge)
        except Exception:
            pass
    else:
        try:
            from config import get_config
            _qmst_badge = str(getattr(get_config(), 'QMST_STATUS_BADGE', _qmst_badge) or _qmst_badge)
        except Exception:
            pass

    lines = [
        '# Stock Picking Trends & Accuracy',
        '',
        f'**Generated:** {generated}',
        f'**QMST status:** {_qmst_badge}',
        f'**Source:** `{HISTORY_PATH.name}` ({len(hist)} rows, '
        f'{hist["date"].min()} → {hist["date"].max()})',
        '',
        f'## Picking ability rating: **{rating}/10** ({label})',
        '',
        'Rank-surface IC (excludes forced SELL/EXIT rows):',
        '',
        '| Engine | IC (30d) | Q5−Q1 (pp) | n |',
        '|--------|----------|------------|---|',
        f"| v1 score | {v1_panel.get('ic_rho', '—')} | "
        f"{v1_panel.get('spread_pp', '—')} | {v1_panel.get('n', 0)} |",
        f"| v2 score | {v2_panel.get('ic_rho', '—')} | "
        f"{v2_panel.get('spread_pp', '—')} | {v2_panel.get('n', 0)} |",
        f"| picking_rank | {pick_panel.get('ic_rho', '—')} | "
        f"{pick_panel.get('spread_pp', '—')} | {pick_panel.get('n', 0)} |",
        '',
    ]
    if hist_oos_panel:
        lines.extend([
            '### Historical outcomes panel (v2 calibration universe)',
            '',
            f"| v1 score | {v1_ho.get('ic_rho', '—')} | "
            f"{v1_ho.get('spread_pp', '—')} | {v1_ho.get('n', 0)} |",
            f"| v2 synth | {hist_oos_panel.get('ic_rho', '—')} | "
            f"{hist_oos_panel.get('spread_pp', '—')} | {hist_oos_panel.get('n', 0)} |",
            '',
        ])
    if wf_mean_ic is not None:
        lines.append(f'Walk-forward mean OOS IC (5-fold): **{wf_mean_ic:.4f}**')
        lines.append('')
    lines.extend([
        '## QMST forward pick telemetry',
        '',
        f"| picking_rank IC | {pick_panel.get('ic_rho', '—')} | "
        f"spread {pick_panel.get('spread_pp', '—')} pp | n={pick_panel.get('n', 0)} |",
        '',
        '> Validation gates: `python3 scripts/qmst_validation_gate.py`',
        '',
        '_Note: forward `recommendation_history` v2 IC needs 30d returns on rows with '
        '`hybrid_*` columns (hybrid logging started 2026-05-07)._',
        '',
        '## Overall Hit Rates',
        '',
        '| Horizon | BUY correct | n | SELL correct | n |',
        '|---------|-------------|---|--------------|---|',
        f'| 30d | {buy_hit*100:.1f}% | {buy_n} | {sell_hit*100:.1f}% | {sell_n} |',
        '',
        '> Re-run: `python3 scripts/evaluate_stock_picking.py`',
        '',
    ])
    OUT_MD.write_text('\n'.join(lines))
    print(f'Wrote {OUT_MD}')
    print(f'Wrote {OUT_CSV}')
    print(f'Rating: {rating}/10 ({label})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
