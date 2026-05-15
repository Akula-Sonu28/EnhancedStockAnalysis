#!/usr/bin/env python3
"""Top-N picks simulation: would v1's top picks vs v2's top picks have made
money in the recommendation history?

Setup:
    - Group historical_outcomes.csv by date.
    - On each date, rank stocks by v1 score and by synthesised v2 score.
    - "Buy" the top 5 of each list.
    - Average their return_30d returns -> that period's portfolio return.
    - Repeat across all dates that have >= 10 rows (enough for a top-5 pick).
    - Report: mean / median / win rate / total cumulative return assuming
      equal-weight cash splits each period.

This is the simplest investor-facing question: "if I'd actually traded the
top-5 picks from each engine, which one would have made me more money?"
"""
from __future__ import annotations

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
WEIGHTS_PATH = REPO_ROOT / 'data' / 'calibrated_weights_v2.json'
OUT_PATH = REPO_ROOT / 'data' / 'top_n_picks_backtest.json'

TOP_N = 10


def main():
    df = pd.read_csv(OUTCOMES_PATH, parse_dates=['date'])
    df['return_30d'] = pd.to_numeric(df['return_30d'], errors='coerce')
    df = df.dropna(subset=['return_30d', 'score'])
    print(f'Loaded {len(df)} rows / {df["symbol"].nunique()} symbols / '
          f'{df["date"].dt.date.nunique()} unique dates')

    # Use the CURRENT calibrated v2 weights (the production ones).
    with open(WEIGHTS_PATH) as f:
        w = (json.load(f).get('weights') or {})
    print(f'Using v2 weights from {WEIGHTS_PATH.name} '
          f'(updated {json.loads(WEIGHTS_PATH.read_text()).get("updated", "?")})')
    df['score_v2'] = _wf._synthesise_v2_score(df, w)

    rows_v1 = []
    rows_v2 = []
    period_log = []
    for d, grp in df.groupby('date'):
        if len(grp) < 10:
            continue
        # v1 top N
        v1_top = grp.nlargest(TOP_N, 'score')
        v1_ret = float(v1_top['return_30d'].mean())
        # v2 top N (skip if no v2 score available for this row)
        grp_v2 = grp.dropna(subset=['score_v2'])
        if len(grp_v2) < TOP_N:
            continue
        v2_top = grp_v2.nlargest(TOP_N, 'score_v2')
        v2_ret = float(v2_top['return_30d'].mean())
        rows_v1.append(v1_ret)
        rows_v2.append(v2_ret)
        period_log.append({
            'date': d.strftime('%Y-%m-%d'),
            'n_universe': int(len(grp)),
            'v1_top_ret': v1_ret,
            'v2_top_ret': v2_ret,
            'v1_symbols': v1_top['symbol'].tolist(),
            'v2_symbols': v2_top['symbol'].tolist(),
        })

    if not rows_v1:
        print('No eligible periods.')
        return 1

    n = len(rows_v1)
    arr1 = np.array(rows_v1)
    arr2 = np.array(rows_v2)

    # Compound geometric return assuming we redeploy each period.
    cum_v1 = float(np.prod(1.0 + arr1 / 100.0) - 1.0)
    cum_v2 = float(np.prod(1.0 + arr2 / 100.0) - 1.0)

    print()
    print('=' * 72)
    print(f'TOP-{TOP_N} PICKS SIMULATION (return_30d, %)')
    print('=' * 72)
    print(f'  periods analysed:     {n}')
    print(f'  mean v1 top-{TOP_N} return:    {arr1.mean():+.2f}%   '
          f'(median {np.median(arr1):+.2f}%)')
    print(f'  mean v2 top-{TOP_N} return:    {arr2.mean():+.2f}%   '
          f'(median {np.median(arr2):+.2f}%)')
    print(f'  mean edge (v2 - v1):  {(arr2 - arr1).mean():+.2f}pp')
    print(f'  v2 beat v1 in:        {(arr2 > arr1).sum()} / {n} periods '
          f'({(arr2 > arr1).mean()*100:.1f}%)')
    print(f'  v1 positive periods:  {(arr1 > 0).sum()} / {n} '
          f'({(arr1 > 0).mean()*100:.1f}%)')
    print(f'  v2 positive periods:  {(arr2 > 0).sum()} / {n} '
          f'({(arr2 > 0).mean()*100:.1f}%)')
    print(f'  cumulative v1:        {cum_v1*100:+.2f}% (compounded)')
    print(f'  cumulative v2:        {cum_v2*100:+.2f}% (compounded)')

    # t-test on paired differences
    try:
        from scipy.stats import ttest_rel
        t_stat, p = ttest_rel(arr2, arr1)
        print(f'  paired t-test:        t={t_stat:.3f}, p={p:.3e}')
    except Exception:
        pass

    payload = {
        'updated': datetime.now().isoformat(),
        'periods': n,
        'top_n': TOP_N,
        'mean_v1_return_pct': float(arr1.mean()),
        'mean_v2_return_pct': float(arr2.mean()),
        'median_v1_return_pct': float(np.median(arr1)),
        'median_v2_return_pct': float(np.median(arr2)),
        'cumulative_v1_pct': cum_v1 * 100,
        'cumulative_v2_pct': cum_v2 * 100,
        'v2_beat_v1_pct': float((arr2 > arr1).mean() * 100),
        'periods_log_sample': period_log[:5] + period_log[-5:],
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, default=str))
    print(f'\nWrote {OUT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
