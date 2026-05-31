#!/usr/bin/env python3
"""Reconstruct fq_score from historical report components and evaluate pick IC.

Reads hybrid_volume_strength + hybrid_momentum_technical from on-disk reports
(or from `data/historical_outcomes.csv` in default mode). Recomputes:

  fq_score       = VS - λ_default * MT
  fq_adapt_score = VS - λ_adaptive(MT) * MT  (production-like)

No market re-fetch: forward returns come from historical_outcomes pairwise
matching (later report at T+7 / T+30) when available.

Writes:
  data/fq_report_ic_backfill.json
  data/historical_outcomes_with_fq.csv            (default)
  data/historical_outcomes_with_fq_all_dates.csv  (--all-report-dates)

Usage:
  python3 scripts/evaluate_fq_from_reports.py
  python3 scripts/evaluate_fq_from_reports.py --all-report-dates
  python3 scripts/evaluate_fq_from_reports.py --qmst-validation
  python3 scripts/evaluate_fq_from_reports.py --rebuild-outcomes
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from config import get_config  # noqa: E402
from src.flow_quality_oracle import add_oracle_pick_columns  # noqa: E402
from src.picking_metrics import (  # noqa: E402
    add_picking_rank_column,
    evaluate_picking_panel,
    quintile_spread,
    spearman_ic,
)

OUTCOMES_PATH = REPO_ROOT / 'data' / 'historical_outcomes.csv'
OUT_JSON = REPO_ROOT / 'data' / 'fq_report_ic_backfill.json'
OUT_CSV = REPO_ROOT / 'data' / 'historical_outcomes_with_fq.csv'
OUT_ALL_DATES_CSV = REPO_ROOT / 'data' / 'historical_outcomes_with_fq_all_dates.csv'
OUT_QMST_PICKING_JSON = REPO_ROOT / 'data' / 'qmst_report_picking_validation.json'
REPORTS_DIR = REPO_ROOT / 'reports'
BUILD_SCRIPT = REPO_ROOT / 'scripts' / 'build_historical_outcomes.py'

QMST_PICK_GATES = {
    'forward_picking_ic_30d': 0.05,
    'quintile_spread_pp': 3.0,
    'min_ic_decision_days': 15,
    'min_pooled_n': 30,
}


def _load_build_helpers():
    spec = importlib.util.spec_from_file_location('build_historical_outcomes', BUILD_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cross_sectional_ic(df: pd.DataFrame, score_col: str, ret_col: str = 'return_30d',
                        min_names: int = 15) -> dict:
    """Mean daily Spearman IC (correct rank-surface methodology)."""
    daily = []
    for dt, grp in df.groupby('date'):
        ic, p, n = spearman_ic(grp[score_col], grp[ret_col])
        if n >= min_names and ic is not None and not np.isnan(ic):
            daily.append({'date': str(dt.date()) if hasattr(dt, 'date') else str(dt),
                          'ic': float(ic), 'n': int(n)})
    if not daily:
        return {'mean_ic': None, 'icir': None, 'days': 0, 'daily': []}
    ics = np.array([d['ic'] for d in daily], dtype=float)
    mean_ic = float(np.mean(ics))
    std_ic = float(np.std(ics, ddof=1)) if len(ics) > 1 else 0.0
    icir = float(mean_ic / std_ic) if std_ic > 1e-9 else None
    return {
        'mean_ic': mean_ic,
        'std_ic': std_ic,
        'icir': icir,
        'days': len(daily),
        'pct_positive_days': float((ics > 0).mean() * 100),
        'daily': daily[-30:],
    }


def _panel_by_regime(df: pd.DataFrame, score_col: str) -> dict:
    out = {}
    if 'regime' not in df.columns:
        return out
    for reg, grp in df.groupby(df['regime'].astype(str).str.upper()):
        if len(grp) < 50:
            continue
        panel = evaluate_picking_panel(grp, score_col=score_col, rank_surface_only=False)
        cs = _cross_sectional_ic(grp, score_col)
        out[reg] = {
            'pooled_ic': panel.get('ic_rho'),
            'pooled_spread_pp': panel.get('spread_pp'),
            'pooled_n': panel.get('n'),
            'cs_mean_ic': cs.get('mean_ic'),
            'cs_days': cs.get('days'),
        }
    return out


def _load_outcomes(rebuild: bool) -> pd.DataFrame:
    if rebuild or not OUTCOMES_PATH.exists():
        import subprocess
        print('Rebuilding historical_outcomes from reports/ ...')
        rc = subprocess.call(
            [sys.executable, str(REPO_ROOT / 'scripts/build_historical_outcomes.py')],
            cwd=str(REPO_ROOT),
        )
        if rc != 0 and not OUTCOMES_PATH.exists():
            raise SystemExit(f'build_historical_outcomes failed rc={rc}')
    return pd.read_csv(OUTCOMES_PATH, parse_dates=['date'])


def _build_report_pairwise_caches(bh):
    """Load latest report per day + Complete Data cache for forward price lookup."""
    latest = bh._latest_report_per_date()
    dated_reports: dict = {}
    complete_cache: dict = {}
    for date_str, path in latest.items():
        try:
            dt = datetime.strptime(date_str, '%Y%m%d')
        except Exception:
            continue
        cd = bh._read_complete_data(path)
        if cd is None or cd.empty:
            continue
        dated_reports[dt] = path
        complete_cache[path] = cd
    return latest, dated_reports, complete_cache


def build_all_report_dates(*, pairwise_returns: bool = True) -> pd.DataFrame:
    """Walk every report date; keep rows with both VS and MT from Complete Data."""
    bh = _load_build_helpers()
    latest, dated_reports, complete_cache = _build_report_pairwise_caches(bh)
    rows = []
    skipped_mom_only = 0
    report_dates_vs_mt = 0

    print(f'  scanning {len(latest)} report dates (Complete Data, report VS+MT only) ...', flush=True)
    for date_str, path in sorted(latest.items()):
        cd = complete_cache.get(path)
        if cd is None or cd.empty or 'symbol' not in cd.columns:
            continue
        if 'hybrid_momentum_technical' not in cd.columns:
            skipped_mom_only += 1
            continue
        has_vs_col = 'hybrid_volume_strength' in cd.columns
        if not has_vs_col or cd['hybrid_volume_strength'].isna().all():
            skipped_mom_only += 1
            continue
        try:
            dt = datetime.strptime(date_str, '%Y%m%d')
        except Exception:
            continue
        report_dates_vs_mt += 1

        score_ser = bh._resolve_score(cd)
        regime_ser = bh._resolve_regime(cd)
        for idx, srow in cd.iterrows():
            sym = str(srow.get('symbol', '')).upper().strip()
            if not sym:
                continue
            mom = pd.to_numeric(srow.get('hybrid_momentum_technical'), errors='coerce')
            vs = pd.to_numeric(srow.get('hybrid_volume_strength'), errors='coerce')
            px = pd.to_numeric(srow.get('current_price'), errors='coerce')
            if pd.isna(mom) or pd.isna(vs) or pd.isna(px) or px <= 0:
                continue
            score = None
            if score_ser is not None and idx < len(score_ser):
                score = pd.to_numeric(score_ser.iloc[idx], errors='coerce')
            if pd.isna(score):
                score = pd.to_numeric(
                    srow.get('final_blended_score', srow.get('hybrid_overall_score')),
                    errors='coerce',
                )
            row = {
                'date': pd.Timestamp(dt),
                'symbol': sym,
                'score': float(score) if pd.notna(score) else 50.0,
                'hybrid_momentum_technical': float(mom),
                'hybrid_volume_strength': float(vs),
                'current_price': float(px),
                'regime': str(regime_ser.iloc[idx]) if idx < len(regime_ser) else 'UNKNOWN',
                'data_source': 'reports_all_dates',
                'return_7d': None,
                'return_30d': None,
            }
            for c in bh.HYBRID_COLS:
                if c in ('hybrid_volume_strength', 'hybrid_momentum_technical'):
                    continue
                v = pd.to_numeric(srow.get(c), errors='coerce') if c in cd.columns else None
                row[c] = None if v is None or pd.isna(v) else float(v)

            if pairwise_returns:
                fwd7 = bh._find_forward_price(
                    sym, dt, bh.WINDOW_7D, dated_reports, complete_cache, allow_yfinance=False,
                )
                fwd30 = bh._find_forward_price(
                    sym, dt, bh.WINDOW_30D, dated_reports, complete_cache, allow_yfinance=False,
                )
                if fwd7 is not None and fwd7 > 0:
                    row['return_7d'] = float((fwd7 - px) / px * 100.0)
                if fwd30 is not None and fwd30 > 0:
                    row['return_30d'] = float((fwd30 - px) / px * 100.0)
            rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    n_ret = int(df['return_30d'].notna().sum())
    ic_dates = sum(
        1 for _, grp in df.dropna(subset=['return_30d']).groupby('date')
        if len(grp) >= 15
    )
    print(
        f'  report dates VS+MT: {report_dates_vs_mt}  rows: {len(df)}  '
        f'skipped mom-only dates: {skipped_mom_only}  '
        f'return_30d (report pairwise): {n_ret}  IC-ready days (>=15): {ic_dates}',
        flush=True,
    )
    return df


def _enrich_fq(df: pd.DataFrame, cfg) -> pd.DataFrame:
    """Add fq columns; require hybrid VS and MT."""
    work = df.copy()
    work = work.dropna(subset=['hybrid_volume_strength', 'hybrid_momentum_technical'], how='any')
    if work.empty:
        return work
    parts = []
    for _, grp in work.groupby('date'):
        parts.append(add_oracle_pick_columns(grp, cfg))
    enriched = pd.concat(parts, ignore_index=True)
    return add_picking_rank_column(enriched, cfg)


def _build_results_payload(raw: pd.DataFrame, eval_df: pd.DataFrame, ret_col: str,
                           n_reports: int, source: str, extra: Optional[dict] = None) -> dict:
    has_both = raw.dropna(subset=['hybrid_volume_strength', 'hybrid_momentum_technical'], how='any')
    results = {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'source': source,
        'reports_on_disk': n_reports,
        'raw_outcomes_rows': len(raw),
        'fq_enriched_rows': len(has_both),
        'rows_with_returns': len(eval_df),
        'date_range': {
            'start': str(eval_df['date'].min().date()) if len(eval_df) else None,
            'end': str(eval_df['date'].max().date()) if len(eval_df) else None,
        },
        'unique_decision_dates': int(eval_df['date'].nunique()) if len(eval_df) else 0,
        'return_column': ret_col,
        'metrics': {},
    }
    if extra:
        results.update(extra)
    return results


def _append_metrics(results: dict, eval_df: pd.DataFrame, ret_col: str) -> None:
    for score_col, label in (
        ('fq_score', 'fq_fixed_lambda'),
        ('fq_adapt_score', 'fq_adaptive_lambda'),
        ('picking_rank', 'picking_rank_driver'),
        ('score', 'v1_blended_score'),
    ):
        if score_col not in eval_df.columns:
            continue
        panel = evaluate_picking_panel(eval_df, score_col=score_col, ret_col=ret_col,
                                       rank_surface_only=False)
        cs = _cross_sectional_ic(eval_df, score_col, ret_col=ret_col)
        q5, q1, spread, _ = quintile_spread(
            pd.to_numeric(eval_df[score_col], errors='coerce'),
            pd.to_numeric(eval_df[ret_col], errors='coerce'),
        )
        results['metrics'][label] = {
            'score_col': score_col,
            'pooled_ic': panel.get('ic_rho'),
            'pooled_spread_pp': panel.get('spread_pp'),
            'pooled_n': panel.get('n'),
            'q5_mean_pct': q5,
            'q1_mean_pct': q1,
            'cross_sectional_mean_ic': cs.get('mean_ic'),
            'cross_sectional_icir': cs.get('icir'),
            'cross_sectional_days': cs.get('days'),
            'pct_positive_ic_days': cs.get('pct_positive_days'),
            'by_regime': _panel_by_regime(eval_df, score_col),
        }

    dense = eval_df[(eval_df['date'] >= '2026-03-01') & (eval_df['date'] <= '2026-05-31')]
    if len(dense) >= 100:
        dense_metrics = {}
        for score_col, label in (('fq_adapt_score', 'fq_adapt'), ('fq_score', 'fq_fixed'), ('score', 'v1')):
            if score_col not in dense.columns:
                continue
            p = evaluate_picking_panel(dense, score_col=score_col, ret_col=ret_col, rank_surface_only=False)
            cs = _cross_sectional_ic(dense, score_col, ret_col=ret_col, min_names=10)
            dense_metrics[label] = {
                'pooled_ic': p.get('ic_rho'),
                'pooled_spread_pp': p.get('spread_pp'),
                'cs_mean_ic': cs.get('mean_ic'),
                'n': p.get('n'),
            }
        results['dense_window_2026_q1_q2'] = dense_metrics


def _evaluate_qmst_picking_gates(
    results: dict,
    eval_df: pd.DataFrame,
    enriched: pd.DataFrame,
    raw: pd.DataFrame,
    ret_col: str,
) -> dict:
    """QMST pick-layer gate checks for report-backfill certification."""
    pick_panel = evaluate_picking_panel(
        eval_df, score_col='picking_rank', ret_col=ret_col, rank_surface_only=False,
    )
    cs = _cross_sectional_ic(eval_df, 'picking_rank', ret_col=ret_col)
    ic_dates = int(cs.get('days') or 0)
    fq_dates = int(raw['date'].nunique()) if not raw.empty else 0
    watchlist_rows = int(enriched.get('on_oracle_watchlist', pd.Series(dtype=bool)).sum()) if 'on_oracle_watchlist' in enriched.columns else 0

    gates = {
        'forward_picking_ic_30d': {
            'value': pick_panel.get('ic_rho'),
            'threshold': QMST_PICK_GATES['forward_picking_ic_30d'],
            'pass': (
                pick_panel.get('ic_rho') is not None
                and float(pick_panel['ic_rho']) >= QMST_PICK_GATES['forward_picking_ic_30d']
                and (pick_panel.get('n') or 0) >= QMST_PICK_GATES['min_pooled_n']
            ),
            'n': pick_panel.get('n', 0),
            'source': 'report_backfill_picking_rank',
        },
        'quintile_spread_pp': {
            'value': pick_panel.get('spread_pp'),
            'threshold': QMST_PICK_GATES['quintile_spread_pp'],
            'pass': (
                pick_panel.get('spread_pp') is not None
                and float(pick_panel['spread_pp']) >= QMST_PICK_GATES['quintile_spread_pp']
            ),
        },
        'cross_sectional_ic_days': {
            'value': ic_dates,
            'threshold': QMST_PICK_GATES['min_ic_decision_days'],
            'pass': ic_dates >= QMST_PICK_GATES['min_ic_decision_days'],
        },
        'report_calendar_days_vs_mt': {
            'value': fq_dates,
            'threshold': 42,
            'pass': fq_dates >= 42,
            'note': '3 mom-only dates (Mar 12/13/16) excluded — no hybrid_volume_strength in report.',
        },
    }
    all_pass = all(g['pass'] for g in gates.values())
    return {
        'generated': datetime.now().isoformat(timespec='seconds'),
        'mode': 'qmst_report_picking_backfill',
        'report_dates_with_vs_mt': fq_dates,
        'fq_enriched_rows': len(enriched),
        'watchlist_rows_total': watchlist_rows,
        'rows_with_return_30d': len(eval_df),
        'ic_decision_dates': ic_dates,
        'ic_date_range': results.get('date_range'),
        'picking_rank_metrics': results['metrics'].get('picking_rank_driver', {}),
        'gates': gates,
        'pick_layer_certified': all_pass,
        'note': (
            'Pick layer validated on report VS+MT across all eligible calendar days. '
            'Full QMST-VALIDATED still requires walk-forward IC + backtest gates and '
            '60 consecutive days of live picking_rank history for production proof.'
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Evaluate fq IC from historical reports')
    parser.add_argument('--rebuild-outcomes', action='store_true',
                        help='Re-run build_historical_outcomes.py first (default mode)')
    parser.add_argument('--all-report-dates', action='store_true',
                        help='All 42 report dates with VS+MT; forward returns via report pairwise')
    parser.add_argument('--qmst-validation', action='store_true',
                        help='QMST pick IC on all 42 days + write qmst_report_picking_validation.json')
    parser.add_argument('--extended', action='store_true',
                        help=argparse.SUPPRESS)
    parser.add_argument('--ret-col', default='return_30d', choices=['return_7d', 'return_30d'])
    args = parser.parse_args()

    if args.extended:
        warnings.warn(
            '--extended is removed (it re-fetched prices). '
            'Use --all-report-dates to scan all reports, or run without flags for default.',
            stacklevel=2,
        )
        print('ERROR: --extended removed. Use --all-report-dates or default mode.', file=sys.stderr)
        return 2

    cfg = get_config()
    n_reports = len(list(REPORTS_DIR.glob('Enhanced_Stock_Report_*.xlsx')))
    ret_col = args.ret_col

    if args.qmst_validation:
        args.all_report_dates = True

    if args.all_report_dates:
        raw = build_all_report_dates(pairwise_returns=True)
        source = 'reports/Complete Data (all dates with VS+MT)'
        out_csv = OUT_ALL_DATES_CSV
        extra = {
            'mode': 'qmst_validation' if args.qmst_validation else 'all_report_dates',
            'report_dates_scanned': int(raw['date'].nunique()) if not raw.empty and 'date' in raw.columns else 0,
            'note': 'QMST fq pick on all VS+MT report days; return_30d from later-report pairwise match.',
        }
    else:
        raw = _load_outcomes(args.rebuild_outcomes)
        source = str(OUTCOMES_PATH)
        out_csv = OUT_CSV
        report_count = int((raw.get('data_source', pd.Series()) == 'reports_pairwise').sum()) if 'data_source' in raw.columns else len(raw)
        extra = {'reports_pairwise_rows': report_count, 'mode': 'standard'}

    enriched = _enrich_fq(raw, cfg)
    if not enriched.empty and 'date' in enriched.columns:
        enriched['date'] = pd.to_datetime(enriched['date'])
    eval_df = enriched.dropna(subset=[ret_col]).copy()
    results = _build_results_payload(raw, eval_df, ret_col, n_reports, source, extra)
    _append_metrics(results, eval_df, ret_col)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2), encoding='utf-8')
    enriched.to_csv(out_csv, index=False)

    qmst_pick_status = None
    if args.qmst_validation:
        qmst_pick_status = _evaluate_qmst_picking_gates(results, eval_df, enriched, raw, ret_col)
        OUT_QMST_PICKING_JSON.write_text(json.dumps(qmst_pick_status, indent=2), encoding='utf-8')

    mode = results.get('mode', 'standard')
    print('=' * 72)
    print(f'  FQ IC FROM HISTORICAL REPORTS ({mode})')
    print('=' * 72)
    print(f"  Reports on disk     : {n_reports}")
    print(f"  Raw rows            : {len(raw)}  →  fq-enriched: {len(enriched)}")
    print(f"  Decision dates (IC) : {results.get('unique_decision_dates', 0)}")
    print(f"  With {ret_col}       : {len(eval_df)}")
    print(f"  Date range (IC)     : {results['date_range']['start']} → {results['date_range']['end']}")
    if mode in ('all_report_dates', 'qmst_validation'):
        print(f"  Report dates scanned: {extra.get('report_dates_scanned', '—')}")
        print(f"  fq rows (all dates) : {len(enriched)}")
        if 'on_oracle_watchlist' in enriched.columns:
            wl = enriched.groupby('date')['on_oracle_watchlist'].sum()
            print(f"  watchlist picks/day : min={int(wl.min())} max={int(wl.max())} avg={wl.mean():.1f}")
    if qmst_pick_status:
        print()
        print('  [QMST pick-layer gates — report backfill]')
        for name, g in qmst_pick_status['gates'].items():
            ok = 'PASS' if g.get('pass') else 'FAIL'
            print(f"    [{ok}] {name}: {g.get('value')} (need {g.get('threshold')})")
        cert = 'CERTIFIED' if qmst_pick_status.get('pick_layer_certified') else 'NOT YET'
        print(f"  Pick layer: {cert}  (IC days: {qmst_pick_status.get('ic_decision_dates')})")
        print(f'  QMST JSON: {OUT_QMST_PICKING_JSON}')
    print()
    for label, m in results['metrics'].items():
        print(f"  [{label}]")
        print(f"    pooled IC         : {m.get('pooled_ic')}")
        print(f"    CS mean IC ({m.get('cross_sectional_days')}d): {m.get('cross_sectional_mean_ic')}")
        print(f"    Q5-Q1 spread      : {m.get('pooled_spread_pp')} pp")
        print(f"    +IC days          : {m.get('pct_positive_ic_days')}%")
    if 'dense_window_2026_q1_q2' in results:
        print('\n  [dense Mar–May 2026]')
        for k, v in results['dense_window_2026_q1_q2'].items():
            print(
                f"    {k}: pooled IC={v.get('pooled_ic')}  "
                f"CS IC={v.get('cs_mean_ic')}  spread={v.get('pooled_spread_pp')}pp"
            )
    print(f'\n  JSON: {OUT_JSON}')
    print(f'  CSV : {out_csv}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
