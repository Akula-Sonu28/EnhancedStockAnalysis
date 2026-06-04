#!/usr/bin/env python3
"""Deep-dive: grid + composite pick strategies vs fq_score (IC pre-filter).

Writes data/strategy_deepdive_screen.json — feed top names to
factor_enhancement_backtest.py --variants ...

Usage:
    python3 scripts/strategy_deepdive_screen.py
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.flow_quality_oracle import adaptive_momentum_lambda, compute_flow_quality_score  # noqa: E402
from src.picking_metrics import quintile_spread, spearman_ic, synthesise_v2_score  # noqa: E402

DEFAULT_INPUT = REPO_ROOT / 'data' / 'historical_outcomes_with_fq_all_dates.csv'
OUT_JSON = REPO_ROOT / 'data' / 'strategy_deepdive_screen.json'
WEIGHTS_PATH = REPO_ROOT / 'data' / 'calibrated_weights_v2.json'
BASELINE = 'fq_score'


def _load_weights() -> dict:
    if not WEIGHTS_PATH.exists():
        return {}
    try:
        return json.loads(WEIGHTS_PATH.read_text()).get('weights') or {}
    except Exception:
        return {}


def _cols(df: pd.DataFrame) -> dict:
    return {
        'vs': pd.to_numeric(df.get('hybrid_volume_strength'), errors='coerce'),
        'mt': pd.to_numeric(df.get('hybrid_momentum_technical'), errors='coerce'),
        'mtf': pd.to_numeric(df.get('hybrid_multi_timeframe'), errors='coerce'),
        'fq': pd.to_numeric(df.get('hybrid_fundamental_quality'), errors='coerce'),
        'gr': pd.to_numeric(df.get('hybrid_growth'), errors='coerce'),
        'vl': pd.to_numeric(df.get('hybrid_value'), errors='coerce'),
        'rk': pd.to_numeric(df.get('hybrid_risk_adjustment'), errors='coerce'),
        'ml': pd.to_numeric(df.get('hybrid_ml_signal'), errors='coerce'),
    }


def build_all_strategies(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    out = df.copy()
    c = _cols(out)
    vs, mt, mtf, fq, gr, vl, rk = c['vs'], c['mt'], c['mtf'], c['fq'], c['gr'], c['vl'], c['rk']

    # Lambda grid (flow quality family)
    for lam in (0.3, 0.5, 0.8, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5):
        key = f'flow_lam_{str(lam).replace(".", "_")}'
        out[key] = vs - lam * mt

    # Production cousins
    if 'fq_adapt_score' not in out.columns:
        out['fq_adapt_score'] = [
            compute_flow_quality_score(v, m, lam=adaptive_momentum_lambda(m, cfg), cfg=cfg)
            for v, m in zip(vs.fillna(50), mt.fillna(50))
        ]
    if 'volume_pick_score' not in out.columns:
        out['volume_pick_score'] = vs

    weights = _load_weights()
    if weights:
        out['score_v2'] = synthesise_v2_score(out, weights)

    # Composites (QMST / turbo / quality themes)
    out['fq_lambda_2'] = vs - 2.0 * mt
    out['mtf_minus_mom'] = mtf - mt
    out['turbo_proxy'] = 0.35 * mtf + 0.25 * mt + 0.40 * vs
    out['turbo_proxy_v2'] = 0.35 * mtf + 0.25 * mt + 0.40 * vs - 0.15 * mt.clip(upper=65)
    out['quality_flow'] = fq + 0.5 * vs
    out['qglp_proxy'] = 0.4 * fq + 0.25 * gr + 0.2 * vs - 0.15 * vl
    out['fq_gated_48'] = (vs - 0.5 * mt).where(fq >= 48)
    out['fq_gated_52'] = (vs - 0.5 * mt).where(fq >= 52)
    out['flow_risk_adj'] = (vs - 0.5 * mt) + 0.2 * (rk - 50)
    out['flow_mtf_confirm'] = (vs - 0.5 * mt) + 0.15 * (mtf - 50)
    out['anti_chase_mtf'] = (vs - 1.25 * mt) + 0.1 * (mtf - 50)
    out['volume_mtf'] = 0.6 * vs + 0.4 * mtf
    out['vs_only'] = vs
    out['low_mom_high_vol'] = vs - 1.5 * mt.clip(lower=40)

    # Regime-conditional (same formula, SIDEWAYS stricter)
    if 'regime' in out.columns:
        reg = out['regime'].astype(str).str.upper()
        lam_s = pd.Series(0.5, index=out.index)
        lam_s = lam_s.where(reg != 'SIDEWAYS', 1.25)
        lam_s = lam_s.where(reg != 'BEAR', 1.5)
        out['flow_regime_lam'] = vs - lam_s * mt

    return out


def _cs_ic_mean(df: pd.DataFrame, col: str, ret: str) -> float | None:
    rhos = []
    for _, g in df.groupby('date'):
        if len(g) < 15:
            continue
        rho, _, n = spearman_ic(pd.to_numeric(g[col], errors='coerce'), pd.to_numeric(g[ret], errors='coerce'))
        if rho is not None and n >= 15:
            rhos.append(rho)
    return round(float(np.mean(rhos)), 4) if rhos else None


def _eval(df: pd.DataFrame, col: str, ret: str) -> dict:
    s = pd.to_numeric(df[col], errors='coerce')
    r = pd.to_numeric(df[ret], errors='coerce')
    rho, p, n = spearman_ic(s, r)
    q5, q1, sp, _ = quintile_spread(s, r)
    base_s = pd.to_numeric(df[BASELINE], errors='coerce')
    base_rho, _, _ = spearman_ic(base_s, r)
    return {
        'strategy': col,
        'n': n,
        'ic_30d': round(rho, 4) if rho is not None else None,
        'spread_pp': round(sp, 3) if sp is not None else None,
        'cs_ic_mean': _cs_ic_mean(df, col, ret),
        'ic_vs_fq_delta': round((rho or 0) - (base_rho or 0), 4) if rho and base_rho else None,
        'cs_vs_fq_delta': None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT)
    parser.add_argument('--ret', default='return_30d')
    parser.add_argument('--top', type=int, default=15)
    args = parser.parse_args()

    if not args.input.exists():
        print(f'ERROR: {args.input}')
        return 1

    raw = pd.read_csv(args.input, parse_dates=['date'])
    work = raw.dropna(subset=[args.ret, BASELINE]).copy()
    work = build_all_strategies(work)

    skip = {'date', 'symbol', 'current_price', 'data_source', 'active_oracle', 'on_oracle_watchlist'}
    strategy_cols = [
        c for c in work.columns
        if c not in skip
        and work[c].dtype in (float, np.float64, int, 'float64')
        and work[c].notna().sum() >= 200
        and not c.startswith('return_')
        and c not in ('oracle_pick_pct', 'picking_rank')
    ]

    baseline_eval = _eval(work.dropna(subset=[BASELINE]), BASELINE, args.ret)
    b_cs = baseline_eval['cs_ic_mean']

    rows = []
    for col in strategy_cols:
        sub = work.dropna(subset=[col])
        if len(sub) < 200:
            continue
        row = _eval(sub, col, args.ret)
        if row['cs_ic_mean'] is not None and b_cs is not None:
            row['cs_vs_fq_delta'] = round(row['cs_ic_mean'] - b_cs, 4)
        rows.append(row)

    rows.sort(
        key=lambda x: (
            x.get('cs_ic_mean') is None,
            -(x.get('cs_ic_mean') or -99),
            -(x.get('ic_30d') or -99),
        ),
    )

    # Score for backtest shortlist: CS IC + pooled IC vs baseline
    for r in rows:
        cs_d = r.get('cs_vs_fq_delta') or 0
        ic_d = r.get('ic_vs_fq_delta') or 0
        r['shortlist_score'] = round(cs_d * 2 + ic_d, 4)
        if r['strategy'] == BASELINE:
            r['tier'] = 'BASELINE'
        elif cs_d >= 0.02 and ic_d >= 0:
            r['tier'] = 'A'
        elif cs_d >= 0 or ic_d >= 0.02:
            r['tier'] = 'B'
        else:
            r['tier'] = 'C'

    tier_a = [r for r in rows if r['tier'] == 'A'][:8]
    shortlist = list(dict.fromkeys(
        [BASELINE, 'fq_lambda_2', 'fq_adapt_score']
        + [r['strategy'] for r in tier_a]
    ))[:12]

    # Lambda sweep summary
    lam_rows = [r for r in rows if r['strategy'].startswith('flow_lam_')]
    best_lam = max(lam_rows, key=lambda x: x.get('cs_ic_mean') or -99) if lam_rows else None

    payload = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'input': str(args.input.relative_to(REPO_ROOT)),
        'n_rows': len(work),
        'baseline': baseline_eval,
        'best_lambda_sweep': best_lam,
        'ranked': rows[: args.top + 5],
        'top_by_cs_ic': rows[: args.top],
        'backtest_shortlist': shortlist,
        'backtest_cmd': (
            'python3 scripts/factor_enhancement_backtest.py --durations 3m 6m 12m '
            f'--variants {" ".join(shortlist[:8])}'
        ),
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    print('=' * 90)
    print('STRATEGY DEEP-DIVE (IC screen — %d strategies)' % len(rows))
    print('=' * 90)
    print(f'Baseline {BASELINE}: IC={baseline_eval["ic_30d"]} CS_IC={baseline_eval["cs_ic_mean"]} spread={baseline_eval["spread_pp"]}pp')
    if best_lam:
        print(f'Best lambda sweep: {best_lam["strategy"]} CS_IC={best_lam["cs_ic_mean"]} (delta {best_lam.get("cs_vs_fq_delta")})')
    print(f'\n{"strategy":28s} {"IC":>8s} {"CS_IC":>8s} {"dCS":>8s} {"spread":>8s} tier')
    print('-' * 90)
    for r in rows[: args.top]:
        print(
            f'{r["strategy"]:28s} {r.get("ic_30d") or 0:>8.4f} '
            f'{r.get("cs_ic_mean") or 0:>8.4f} {r.get("cs_vs_fq_delta") or 0:>8.4f} '
            f'{r.get("spread_pp") or 0:>8.2f} {r.get("tier", ""):>4s}'
        )
    print('-' * 90)
    print('Backtest shortlist:', ', '.join(shortlist[:8]))
    print(f'Wrote {OUT_JSON}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
