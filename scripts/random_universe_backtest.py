#!/usr/bin/env python3
"""Random-universe head-to-head backtest of v1 vs v2 scoring engines.

Purpose:
    Today's walk-forward validation used a chronological train/test split on
    the full historical universe. This script does the complementary check:
    sample N random sub-universes (different random seeds, different stocks)
    and ask whether v2's predictive edge over v1 is robust across them. If v2
    only beats v1 on the specific split walkforward_v2_validation chose, that
    would be a red flag. If v2 wins across most random sub-universes, the edge
    is real.

Methodology per trial:
    1. Pick a random seed; sample `n_symbols` symbols (default 100) from the
       set of symbols present in `data/historical_outcomes.csv`.
    2. Chronologically split that sub-universe 80/20 train/test.
    3. Calibrate v2 weights on the train rows (production calibrator).
    4. Synthesise a v2 score on the test rows from the trained weights.
    5. Compute Spearman IC and Q5-Q1 spread vs `return_30d` for BOTH
       v1's `score` column and the synthesised v2 score on the same test rows.
    6. Record (trial, n_test, v1_ic, v2_ic, v1_spread, v2_spread, v2_wins).

After all trials, print:
    - Win rate (% of trials where v2 OOS IC strictly exceeds v1 OOS IC)
    - Mean and stdev of v2 - v1 IC edge
    - Per-trial detail table
    - Aggregate verdict

Run:
    python3 scripts/random_universe_backtest.py --trials 20 --n-symbols 100
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import random
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# Re-use the walk-forward helpers so we evaluate v2 the same way production does.
import importlib.util as _ilu
_spec = _ilu.spec_from_file_location(
    'walkforward_v2_validation',
    REPO_ROOT / 'scripts' / 'walkforward_v2_validation.py',
)
_wf = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_wf)

OUTCOMES_PATH = REPO_ROOT / 'data' / 'historical_outcomes.csv'
OUTPUT_PATH = REPO_ROOT / 'data' / 'random_universe_backtest.json'


def _load_outcomes() -> pd.DataFrame:
    if not OUTCOMES_PATH.exists():
        raise FileNotFoundError(f'missing {OUTCOMES_PATH}')
    df = pd.read_csv(OUTCOMES_PATH, parse_dates=['date'])
    # Need: score (v1), date, symbol, return_30d, all hybrid_* cols.
    required = ['score', 'date', 'symbol', 'return_30d']
    for c in required:
        if c not in df.columns:
            raise ValueError(f'historical_outcomes.csv missing column {c}')
    df['return_30d'] = pd.to_numeric(df['return_30d'], errors='coerce')
    df = df.dropna(subset=['return_30d', 'score'])
    return df


def _trial(df_all: pd.DataFrame, seed: int, n_symbols: int, train_frac: float):
    rng = random.Random(seed)
    universe = sorted(df_all['symbol'].dropna().unique().tolist())
    if len(universe) < n_symbols:
        n_symbols = len(universe)
    sample_syms = rng.sample(universe, n_symbols)
    sub = df_all[df_all['symbol'].isin(sample_syms)].copy()
    sub = sub.sort_values('date').reset_index(drop=True)
    if len(sub) < 100:
        return None  # not enough rows to compute meaningful IC
    cut = int(len(sub) * train_frac)
    train = sub.iloc[:cut].copy()
    test = sub.iloc[cut:].copy()
    if len(train) < 50 or len(test) < 30:
        return None

    # Calibrate v2 on the random-trial train rows.
    weights = _wf._calibrate_on(train)
    if not weights:
        return None
    w = weights.get('weights') or weights
    score_v2 = _wf._synthesise_v2_score(test, w)
    test = test.assign(_v2=score_v2)

    v1_ic, v1_p, v1_n = _wf._ic(test['score'], test['return_30d'])
    v2_ic, v2_p, v2_n = _wf._ic(test['_v2'], test['return_30d'])
    v1_q5, v1_q1, v1_spread, _ = _wf._quintile_spread(test['score'], test['return_30d'])
    v2_q5, v2_q1, v2_spread, _ = _wf._quintile_spread(test['_v2'], test['return_30d'])

    return {
        'seed': seed,
        'n_symbols': n_symbols,
        'n_train': int(len(train)),
        'n_test': int(len(test)),
        'v1_ic_30d': v1_ic,
        'v1_p': v1_p,
        'v1_spread_pp': v1_spread,
        'v2_ic_30d': v2_ic,
        'v2_p': v2_p,
        'v2_spread_pp': v2_spread,
        'v2_minus_v1_ic': (v2_ic - v1_ic) if (v2_ic is not None and v1_ic is not None) else None,
        'v2_wins_ic': bool(v2_ic is not None and v1_ic is not None and v2_ic > v1_ic),
        'v2_wins_spread': bool(v2_spread is not None and v1_spread is not None and v2_spread > v1_spread),
    }


def main():
    parser = argparse.ArgumentParser(description='Random-universe v1 vs v2 backtest')
    parser.add_argument('--trials', type=int, default=20)
    parser.add_argument('--n-symbols', type=int, default=100)
    parser.add_argument('--train-frac', type=float, default=0.80)
    parser.add_argument('--seed-base', type=int, default=42)
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    df_all = _load_outcomes()
    print(f'Loaded {len(df_all)} rows / {df_all["symbol"].nunique()} unique symbols '
          f'from {OUTCOMES_PATH.name}')
    print(f'Date range: {df_all["date"].min().date()} -> {df_all["date"].max().date()}')
    print(f'\nRunning {args.trials} random-universe trials (n_symbols={args.n_symbols}, '
          f'train_frac={args.train_frac:.2f})...\n')

    trials = []
    for i in range(args.trials):
        seed = args.seed_base + i
        result = _trial(df_all, seed, args.n_symbols, args.train_frac)
        if result is None:
            print(f'  trial {i+1:2d} (seed={seed}): SKIPPED (insufficient data)')
            continue
        trials.append(result)
        v1 = result['v1_ic_30d'] or float('nan')
        v2 = result['v2_ic_30d'] or float('nan')
        edge = result['v2_minus_v1_ic'] or float('nan')
        win = 'v2 WINS' if result['v2_wins_ic'] else 'v1 wins'
        print(f'  trial {i+1:2d} (seed={seed}): n_test={result["n_test"]:4d}  '
              f'v1_IC={v1:+.4f}  v2_IC={v2:+.4f}  edge={edge:+.4f}  {win}')

    if not trials:
        print('\nNo valid trials. Aborting.')
        return 1

    n = len(trials)
    win_rate_ic = sum(1 for t in trials if t['v2_wins_ic']) / n
    win_rate_spread = sum(1 for t in trials if t['v2_wins_spread']) / n
    edges = [t['v2_minus_v1_ic'] for t in trials if t['v2_minus_v1_ic'] is not None]
    v1_ics = [t['v1_ic_30d'] for t in trials if t['v1_ic_30d'] is not None]
    v2_ics = [t['v2_ic_30d'] for t in trials if t['v2_ic_30d'] is not None]
    v1_spreads = [t['v1_spread_pp'] for t in trials if t['v1_spread_pp'] is not None]
    v2_spreads = [t['v2_spread_pp'] for t in trials if t['v2_spread_pp'] is not None]

    print('\n' + '=' * 72)
    print('RANDOM-UNIVERSE HEAD-TO-HEAD SUMMARY')
    print('=' * 72)
    print(f'  trials run:                {n}')
    print(f'  v2 IC win rate:            {win_rate_ic*100:.1f}%  ({int(win_rate_ic*n)} of {n})')
    print(f'  v2 spread win rate:        {win_rate_spread*100:.1f}%  ({int(win_rate_spread*n)} of {n})')
    print(f'  mean v1 IC:                {np.mean(v1_ics):+.4f}  (std {np.std(v1_ics):.4f})')
    print(f'  mean v2 IC:                {np.mean(v2_ics):+.4f}  (std {np.std(v2_ics):.4f})')
    print(f'  mean edge (v2 - v1):       {np.mean(edges):+.4f}  (std {np.std(edges):.4f})')
    print(f'  mean v1 spread (pp):       {np.mean(v1_spreads):+.2f}')
    print(f'  mean v2 spread (pp):       {np.mean(v2_spreads):+.2f}')

    if win_rate_ic >= 0.80 and np.mean(edges) >= 0.10:
        verdict = 'V2 ROBUST'
        reason = (f'v2 won {win_rate_ic*100:.0f}% of random universes with mean edge '
                  f'+{np.mean(edges):.3f}; predictive edge is not split-dependent.')
    elif win_rate_ic >= 0.60:
        verdict = 'V2 LIKELY ROBUST'
        reason = f'v2 wins {win_rate_ic*100:.0f}% of trials but edge is moderate.'
    else:
        verdict = 'V2 NOT ROBUST'
        reason = f'v2 only wins {win_rate_ic*100:.0f}%; the walk-forward edge may be split-specific.'
    print(f'\n  VERDICT: {verdict}')
    print(f'  reason:  {reason}')

    payload = {
        'updated': datetime.now().isoformat(),
        'trials_run': n,
        'win_rate_ic': win_rate_ic,
        'win_rate_spread': win_rate_spread,
        'mean_v1_ic': float(np.mean(v1_ics)),
        'mean_v2_ic': float(np.mean(v2_ics)),
        'mean_edge': float(np.mean(edges)),
        'std_edge': float(np.std(edges)),
        'mean_v1_spread_pp': float(np.mean(v1_spreads)),
        'mean_v2_spread_pp': float(np.mean(v2_spreads)),
        'verdict': verdict,
        'reason': reason,
        'trials': trials,
    }
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2, default=str))
    print(f'\nWrote {OUTPUT_PATH}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
