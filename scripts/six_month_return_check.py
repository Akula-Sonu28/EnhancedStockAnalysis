#!/usr/bin/env python3
"""6-month return reality check (with honest data limits).

Outputs three numbers the operator actually needs:

  Section A - Dense window (Mar 12 - Apr 18, 2026):
    Weekly rebalance, top-5 picks from v1 vs v2 (both engines fully scored).
    This is the only window where v2 can be backtested AT ALL.

  Section B - Full 6-month window (Nov 2025 - Apr 2026):
    Monthly rebalance, v1-ONLY (v2 lacks component data before Mar 2026).
    This is what v1 actually delivered over the last six months.

  Section C - Projection:
    Apply the mean monthly edge measured in Section A to the v1 6-month
    series. Best estimate of what v2 WOULD have produced if its component
    data had been written from Nov 2025. Confidence is bounded by the
    5-week sample.

All rebalances use NO-LOOKAHEAD: v2 weights are re-calibrated on every
prior row before each rebalance date.
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

import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    'walkforward_v2_validation',
    REPO_ROOT / 'scripts' / 'walkforward_v2_validation.py',
)
_wf = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_wf)

OUTCOMES_PATH = REPO_ROOT / 'data' / 'historical_outcomes.csv'
OUT_PATH = REPO_ROOT / 'data' / 'six_month_return_check.json'
INVEST = 100000
TOP_N = 10


def _calibrate_no_lookahead(df, cutoff):
    train = df[df['date'] < cutoff].copy()
    if len(train) < 100:
        return None
    weights = _wf._calibrate_on(train)
    if not weights:
        return None
    return weights.get('weights') or weights


def _topn_returns(eligible, weights, top_n):
    """Returns (v1_top, v2_top, v1_ret_pct, v2_ret_pct).
    v2_ret_pct is None if components are missing."""
    if 'score' not in eligible.columns or eligible['score'].notna().sum() < top_n:
        return None, None, None, None
    v1_top = eligible.nlargest(top_n, 'score')
    v1_ret = float(v1_top['return_30d'].mean())
    if weights is None:
        return v1_top, None, v1_ret, None
    e = eligible.copy()
    e['_v2'] = _wf._synthesise_v2_score(e, weights)
    e_v2 = e.dropna(subset=['_v2'])
    if len(e_v2) < top_n:
        return v1_top, None, v1_ret, None
    v2_top = e_v2.nlargest(top_n, '_v2')
    v2_ret = float(v2_top['return_30d'].mean())
    return v1_top, v2_top, v1_ret, v2_ret


def section_a_dense_weekly(df):
    """Weekly rebalance over the dense window where both engines work."""
    sub = df.dropna(subset=['hybrid_fundamental_quality',
                            'hybrid_momentum_technical',
                            'return_30d', 'score'])
    dates = sorted(sub['date'].unique())
    if not dates:
        return None
    # Use 1 rebalance per ~5-7 business days = roughly every other date.
    rebal_dates = dates[::3]  # ~every 3 trading days = weekly-ish

    print('\n' + '=' * 76)
    print('Section A: WEEKLY rebalance, dense window (full v1 vs v2)')
    print('=' * 76)
    print(f'  Rebalance dates: {len(rebal_dates)} '
          f'({pd.Timestamp(rebal_dates[0]).date()} -> {pd.Timestamp(rebal_dates[-1]).date()})')
    print()
    print(f'{"Date":12s} {"Univ":>5s}  {"v1 ret%":>8s}  {"v2 ret%":>8s}  '
          f'{"edge":>7s}  {"cum v1%":>9s}  {"cum v2%":>9s}')
    print('-' * 76)

    cum_v1 = 1.0
    cum_v2 = 1.0
    months = []
    for d in rebal_dates:
        weights = _calibrate_no_lookahead(df, d)
        if weights is None:
            continue
        eligible = sub[sub['date'] == d]
        if len(eligible) < TOP_N * 2:
            continue
        v1t, v2t, v1r, v2r = _topn_returns(eligible, weights, TOP_N)
        if v2r is None:
            continue
        cum_v1 *= (1 + v1r / 100.0)
        cum_v2 *= (1 + v2r / 100.0)
        months.append({
            'date': pd.Timestamp(d).strftime('%Y-%m-%d'),
            'universe_n': int(len(eligible)),
            'v1_picks': v1t['symbol'].tolist(),
            'v2_picks': v2t['symbol'].tolist(),
            'v1_ret_pct': v1r,
            'v2_ret_pct': v2r,
            'v1_pick_rets': v1t['return_30d'].round(2).tolist(),
            'v2_pick_rets': v2t['return_30d'].round(2).tolist(),
        })
        print(f'{pd.Timestamp(d).date()!s:12s} {len(eligible):>5d}  '
              f'{v1r:>+7.2f}  {v2r:>+7.2f}  {v2r - v1r:>+6.2f}  '
              f'{(cum_v1 - 1)*100:>+8.2f}  {(cum_v2 - 1)*100:>+8.2f}')
    if not months:
        return None
    v1r = np.array([m['v1_ret_pct'] for m in months])
    v2r = np.array([m['v2_ret_pct'] for m in months])
    summary = {
        'n_rebalances': len(months),
        'mean_v1_per_rebal_pct': float(v1r.mean()),
        'mean_v2_per_rebal_pct': float(v2r.mean()),
        'mean_edge_pp': float((v2r - v1r).mean()),
        'win_rate_v2': float((v2r > v1r).mean()),
        'cum_v1_pct': (cum_v1 - 1) * 100,
        'cum_v2_pct': (cum_v2 - 1) * 100,
        'cum_v1_multiplier': cum_v1,
        'cum_v2_multiplier': cum_v2,
        'months': months,
    }
    print()
    print(f'  Section A SUMMARY:')
    print(f'    Mean per-rebal return - v1:  {v1r.mean():+.2f}%  '
          f'(median {np.median(v1r):+.2f}%)')
    print(f'    Mean per-rebal return - v2:  {v2r.mean():+.2f}%  '
          f'(median {np.median(v2r):+.2f}%)')
    print(f'    v2 won:                       {(v2r > v1r).sum()}/{len(months)} rebalances')
    print(f'    Compounded over window - v1: {(cum_v1 - 1)*100:+.2f}%')
    print(f'    Compounded over window - v2: {(cum_v2 - 1)*100:+.2f}%')
    return summary


def section_b_v1_monthly(df, months_back=6):
    """6-month v1-only monthly rebalance using whatever rows have v1 score."""
    df = df.dropna(subset=['return_30d', 'score']).copy()
    last_date = df['date'].max()
    start = last_date - pd.DateOffset(months=months_back)
    sub = df[df['date'] >= start].copy()
    sub['_ym'] = sub['date'].dt.to_period('M')

    print('\n' + '=' * 76)
    print(f'Section B: MONTHLY rebalance, last {months_back} months, v1 ONLY')
    print('=' * 76)
    print('  (v2 cannot be scored before Mar 2026 - no component data.)')
    print()
    print(f'{"Month":10s} {"Date":12s} {"Univ":>5s}  {"v1 ret%":>8s}  {"cum v1%":>9s}')
    print('-' * 76)

    cum = 1.0
    months = []
    for ym, grp in sub.groupby('_ym'):
        d = grp['date'].min()
        eligible = sub[sub['date'] == d]
        if len(eligible) < TOP_N * 2:
            # widen
            lo, hi = d - pd.Timedelta(days=3), d + pd.Timedelta(days=3)
            eligible = sub[(sub['date'] >= lo) & (sub['date'] <= hi)]
        if len(eligible) < TOP_N:
            print(f'{str(ym):10s} {pd.Timestamp(d).date()!s:12s} '
                  f'{len(eligible):>5d}   (skipped - too few stocks)')
            continue
        v1_top = eligible.nlargest(TOP_N, 'score')
        v1_ret = float(v1_top['return_30d'].mean())
        cum *= (1 + v1_ret / 100.0)
        months.append({
            'month': str(ym),
            'date': pd.Timestamp(d).strftime('%Y-%m-%d'),
            'universe_n': int(len(eligible)),
            'v1_picks': v1_top['symbol'].tolist(),
            'v1_ret_pct': v1_ret,
            'v1_pick_rets': v1_top['return_30d'].round(2).tolist(),
        })
        print(f'{str(ym):10s} {pd.Timestamp(d).date()!s:12s} '
              f'{len(eligible):>5d}  {v1_ret:>+7.2f}  {(cum - 1)*100:>+8.2f}')

    if not months:
        return None
    v1r = np.array([m['v1_ret_pct'] for m in months])
    summary = {
        'n_months': len(months),
        'mean_v1_monthly_pct': float(v1r.mean()),
        'cum_v1_pct': (cum - 1) * 100,
        'cum_v1_multiplier': cum,
        'months': months,
    }
    print()
    print(f'  Section B SUMMARY:')
    print(f'    Months executed:              {len(months)}')
    print(f'    Mean monthly return - v1:     {v1r.mean():+.2f}%')
    print(f'    Cumulative 6-month return:    {(cum - 1)*100:+.2f}%')
    print(f'    Rs 1,00,000 -> Rs {INVEST * cum:,.0f}')
    return summary


def section_c_projection(section_a, section_b):
    """Project v2's 6-month return using v1's actual + measured edge."""
    if not section_a or not section_b:
        return None
    print('\n' + '=' * 76)
    print('Section C: PROJECTION - if v2 had been usable for the full 6 months')
    print('=' * 76)
    print('  Method: take v1\'s actual monthly returns (Section B), add the')
    print('          mean per-rebalance v2-v1 edge from Section A, compound.')
    print()

    edge_pp_per_rebal = section_a['mean_edge_pp']
    # Section A is weekly; section B is monthly. Calibrate: roughly 3 weekly
    # rebalances per month. Compound the edge per month assuming we re-rotate
    # weekly -> conservative: take edge directly per month.
    months = section_b['months']
    cum_v1 = 1.0
    cum_v2_proj = 1.0
    print(f'{"Month":10s} {"v1 actual%":>10s}  {"v2 proj%":>10s}  '
          f'{"cum v1%":>9s}  {"cum v2 proj%":>13s}')
    print('-' * 76)
    for m in months:
        v1 = m['v1_ret_pct']
        v2 = v1 + edge_pp_per_rebal
        cum_v1 *= (1 + v1 / 100.0)
        cum_v2_proj *= (1 + v2 / 100.0)
        print(f'{m["month"]:10s} {v1:>+9.2f}  {v2:>+9.2f}  '
              f'{(cum_v1 - 1)*100:>+8.2f}  {(cum_v2_proj - 1)*100:>+12.2f}')
    print()
    print(f'  Edge per rebalance from Section A: {edge_pp_per_rebal:+.2f}pp')
    print(f'  v1 cumulative (actual):            {(cum_v1 - 1)*100:+.2f}%  '
          f'-> Rs {INVEST * cum_v1:,.0f}')
    print(f'  v2 cumulative (projection):        {(cum_v2_proj - 1)*100:+.2f}%  '
          f'-> Rs {INVEST * cum_v2_proj:,.0f}')
    print(f'  Projected v2 - v1 cash edge:        Rs {INVEST * (cum_v2_proj - cum_v1):+,.0f}')
    return {
        'edge_pp_per_rebal': edge_pp_per_rebal,
        'cum_v1_pct': (cum_v1 - 1) * 100,
        'cum_v2_proj_pct': (cum_v2_proj - 1) * 100,
        'final_v1_value': INVEST * cum_v1,
        'final_v2_proj_value': INVEST * cum_v2_proj,
    }


def main():
    df = pd.read_csv(OUTCOMES_PATH, parse_dates=['date'])
    df['return_30d'] = pd.to_numeric(df['return_30d'], errors='coerce')
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    print(f'Loaded {len(df)} rows / {df["symbol"].nunique()} symbols')
    print(f'Window: {df["date"].min().date()} -> {df["date"].max().date()}')

    a = section_a_dense_weekly(df)
    b = section_b_v1_monthly(df, months_back=6)
    c = section_c_projection(a, b)

    payload = {
        'updated': datetime.now().isoformat(),
        'invest_amount': INVEST,
        'top_n': TOP_N,
        'section_a_dense_weekly': a,
        'section_b_v1_monthly_6m': b,
        'section_c_projection': c,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, default=str))
    print(f'\nWrote {OUT_PATH}')


if __name__ == '__main__':
    main()
