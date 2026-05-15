#!/usr/bin/env python3
"""6-month monthly-rebalance portfolio backtest: v1 vs v2.

Setup:
    - Universe: data/historical_outcomes.csv (forward returns already merged).
    - Backtest window: trailing 6 months from the latest date in the file.
    - Rebalance cadence: monthly. Six rebalance dates total.
    - At each rebalance date d:
        * Train v2 on ALL rows strictly before d  (no lookahead).
        * From rows AT date d (or the nearest available date in that month),
          rank by v1 score and by synthesised v2 score.
        * "Buy" top N (default 5), equal-weight.
        * 30-day forward return is read directly from return_30d on those rows.
    - Compound monthly returns into total return.

Outputs:
    - Console table with per-month picks + returns + cumulative.
    - data/monthly_rebalance_6mo_backtest.json artifact.

Run:
    python3 scripts/monthly_rebalance_backtest.py [--top-n 5] [--months 6]
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
OUT_PATH = REPO_ROOT / 'data' / 'monthly_rebalance_6mo_backtest.json'


def _pick_rebalance_dates(df: pd.DataFrame, months: int) -> list:
    """Pick `months` monthly rebalance dates from the trailing window.

    For each calendar month inside the trailing window, pick the EARLIEST
    available date in that month (so we "buy" right at the start of the month).
    """
    last_date = df['date'].max()
    first_date = last_date - pd.DateOffset(months=months)
    sub = df[df['date'] >= first_date].copy()
    sub['_ym'] = sub['date'].dt.to_period('M')
    picks = []
    for ym, grp in sub.groupby('_ym'):
        picks.append(grp['date'].min())
    return sorted(picks)[-months:]


def _eligible_today(df: pd.DataFrame, d, tol_days: int = 0) -> pd.DataFrame:
    """All rows with date == d (or within `tol_days` if exact match is sparse)."""
    same = df[df['date'] == d]
    if len(same) >= 10 or tol_days <= 0:
        return same.copy()
    lo = d - pd.Timedelta(days=tol_days)
    hi = d + pd.Timedelta(days=tol_days)
    return df[(df['date'] >= lo) & (df['date'] <= hi)].copy()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--top-n', type=int, default=5)
    parser.add_argument('--months', type=int, default=6)
    parser.add_argument('--tol-days', type=int, default=3,
                        help='If exact rebalance date has <10 rows, widen by +/- N days.')
    args = parser.parse_args()

    df = pd.read_csv(OUTCOMES_PATH, parse_dates=['date'])
    df['return_30d'] = pd.to_numeric(df['return_30d'], errors='coerce')
    df['score'] = pd.to_numeric(df['score'], errors='coerce')
    df = df.dropna(subset=['return_30d', 'score'])

    rebalance_dates = _pick_rebalance_dates(df, args.months)
    print(f'Loaded {len(df)} rows / {df["symbol"].nunique()} symbols')
    print(f'Trailing-{args.months}m window with monthly rebalances:')
    for d in rebalance_dates:
        print(f'  -> {d.date()}')
    print()

    months_log = []
    v1_returns = []
    v2_returns = []
    cum_v1 = 1.0
    cum_v2 = 1.0

    print(f'{"Month":12s} {"Universe":>9s}  {"v1 ret%":>9s}  {"v2 ret%":>9s}  '
          f'{"v2-v1":>8s}  {"cum v1%":>10s}  {"cum v2%":>10s}')
    print('-' * 78)

    for d in rebalance_dates:
        # Train v2 on rows strictly BEFORE today (no lookahead).
        train = df[df['date'] < d].copy()
        if len(train) < 100:
            print(f'{d.date()!s:12s}    skipped (train n={len(train)})')
            continue
        weights = _wf._calibrate_on(train)
        w = (weights.get('weights') or weights) if weights else {}

        # Eligible test universe at rebalance date.
        eligible = _eligible_today(df, d, tol_days=args.tol_days)
        if len(eligible) < args.top_n * 2:
            print(f'{d.date()!s:12s}    skipped (universe n={len(eligible)})')
            continue
        eligible = eligible.assign(_v2=_wf._synthesise_v2_score(eligible, w))

        v1_top = eligible.nlargest(args.top_n, 'score')
        v2_top = eligible.dropna(subset=['_v2']).nlargest(args.top_n, '_v2')
        if len(v1_top) < args.top_n or len(v2_top) < args.top_n:
            print(f'{d.date()!s:12s}    skipped (insufficient picks)')
            continue

        v1_ret_pct = float(v1_top['return_30d'].mean())
        v2_ret_pct = float(v2_top['return_30d'].mean())
        v1_returns.append(v1_ret_pct)
        v2_returns.append(v2_ret_pct)
        cum_v1 *= (1.0 + v1_ret_pct / 100.0)
        cum_v2 *= (1.0 + v2_ret_pct / 100.0)

        months_log.append({
            'rebalance_date': d.strftime('%Y-%m-%d'),
            'universe_n': int(len(eligible)),
            'train_n': int(len(train)),
            'v1_picks': v1_top['symbol'].tolist(),
            'v2_picks': v2_top['symbol'].tolist(),
            'v1_ret_pct': v1_ret_pct,
            'v2_ret_pct': v2_ret_pct,
            'v1_pick_returns_pct': v1_top['return_30d'].round(2).tolist(),
            'v2_pick_returns_pct': v2_top['return_30d'].round(2).tolist(),
        })

        print(f'{d.date()!s:12s} {len(eligible):>9d}  '
              f'{v1_ret_pct:>+8.2f}  {v2_ret_pct:>+8.2f}  '
              f'{v2_ret_pct - v1_ret_pct:>+7.2f}  '
              f'{(cum_v1 - 1)*100:>+9.2f}  {(cum_v2 - 1)*100:>+9.2f}')

    if not months_log:
        print('\nNo eligible months. Aborting.')
        return 1

    n = len(months_log)
    a1 = np.array(v1_returns)
    a2 = np.array(v2_returns)

    print('\n' + '=' * 78)
    print(f'TRAILING-{args.months}M MONTHLY-REBALANCE SUMMARY (top-{args.top_n} picks, equal-weight)')
    print('=' * 78)
    print(f'  Months executed:              {n}')
    print(f'  Mean monthly return - v1:     {a1.mean():+.2f}%   (median {np.median(a1):+.2f}%)')
    print(f'  Mean monthly return - v2:     {a2.mean():+.2f}%   (median {np.median(a2):+.2f}%)')
    print(f'  Volatility (stdev) - v1:      {a1.std():.2f}%')
    print(f'  Volatility (stdev) - v2:      {a2.std():.2f}%')
    print(f'  v2 beat v1 in:                {(a2 > a1).sum()} / {n} months ({(a2 > a1).mean()*100:.0f}%)')
    print(f'  Cumulative return - v1:       {(cum_v1 - 1)*100:+.2f}%')
    print(f'  Cumulative return - v2:       {(cum_v2 - 1)*100:+.2f}%')
    print(f'  Edge (v2 - v1) cumulative:    {(cum_v2 - cum_v1)*100:+.2f}pp')

    # Translate to a 1 lakh investment for the operator's intuition.
    INVEST = 100000
    print()
    print(f'  Hypothetical Rs 1,00,000 portfolio:')
    print(f'    Trading v1 monthly picks    -> Rs {INVEST * cum_v1:>12,.0f}  '
          f'({(cum_v1 - 1)*100:+.2f}%)')
    print(f'    Trading v2 monthly picks    -> Rs {INVEST * cum_v2:>12,.0f}  '
          f'({(cum_v2 - 1)*100:+.2f}%)')
    print(f'    Difference (v2 vs v1)       -> Rs {INVEST * (cum_v2 - cum_v1):>+12,.0f}')

    # paired t-test
    try:
        from scipy.stats import ttest_rel
        t, p = ttest_rel(a2, a1)
        print(f'\n  paired t-test (v2 vs v1):     t={t:.3f}, p={p:.3e}')
    except Exception:
        pass

    payload = {
        'updated': datetime.now().isoformat(),
        'months_executed': n,
        'top_n': args.top_n,
        'mean_v1_monthly_pct': float(a1.mean()),
        'mean_v2_monthly_pct': float(a2.mean()),
        'cumulative_v1_pct': (cum_v1 - 1) * 100,
        'cumulative_v2_pct': (cum_v2 - 1) * 100,
        'invest_amount': INVEST,
        'final_value_v1': INVEST * cum_v1,
        'final_value_v2': INVEST * cum_v2,
        'months': months_log,
    }
    OUT_PATH.write_text(json.dumps(payload, indent=2, default=str))
    print(f'\nWrote {OUT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
