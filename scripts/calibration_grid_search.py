"""Grid search across weight calibrations to find optimal medium-aggressive profile.

Tests multiple combinations of risk_adjustment, fundamental, momentum, growth,
value weights — backtests each over the full 2.4-year OHLCV window, and ranks
by Sharpe ratio.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date
from itertools import product
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backtest.data.path1_loader import _synthesise_v2_score, DateSnapshot
from backtest.data.prices import PriceCache
from backtest.engine import BacktestEngine, EngineConfig
from backtest.metrics import summarize

logging.basicConfig(level=logging.WARNING, format='%(message)s')


def load_snapshots() -> pd.DataFrame:
    """Load the cached 2.4-year snapshot data."""
    cache_dir = REPO / 'backtest' / 'cache' / 'scores'
    candidates = [
        cache_dir / 'snapshots_2024-01-01_2026-05-13_weekly_n200_long.pkl',
        cache_dir / 'snapshots_2024-01-01_2026-05-13_weekly_n200.pkl',
    ]
    for p in candidates:
        if p.exists():
            df = pd.read_pickle(p)
            df['date'] = pd.to_datetime(df['date'])
            return df
    for p in sorted(cache_dir.glob('snapshots_*.pkl'), reverse=True):
        df = pd.read_pickle(p)
        df['date'] = pd.to_datetime(df['date'])
        return df
    raise FileNotFoundError('No cached snapshots found')


def rescore(df_all: pd.DataFrame, weights: dict) -> list[DateSnapshot]:
    df = df_all.copy()
    df['score_engine'] = _synthesise_v2_score(df, weights)
    valid = df.dropna(subset=['score_engine', 'current_price'])
    snapshots = []
    for d, grp in valid.groupby('date'):
        snapshots.append(DateSnapshot(
            decision_date=d.date() if hasattr(d, 'date') else d,
            df=grp.reset_index(drop=True),
        ))
    return snapshots


def run_backtest(snapshots: list[DateSnapshot], label: str,
                 prices: PriceCache) -> dict:
    cfg = EngineConfig(
        initial_capital=100_000.0,
        target_positions=10,
        max_positions=15,
        sector_cap_pct=30.0,
        rebalance='weekly',
        selection_mode='rank',
        min_entry_score=45.0,
    )
    engine = BacktestEngine(engine_label=label, cfg=cfg, price_cache=prices)
    result = engine.run(snapshots)
    result.summary = summarize(
        result.equity_curve, result.trades, cfg.initial_capital,
        benchmark=result.benchmark_curve,
    )
    return result.summary


def ic_quick(df_all: pd.DataFrame, weights: dict) -> dict:
    from scipy.stats import spearmanr
    df = df_all.copy()
    df['score'] = _synthesise_v2_score(df, weights)
    dates = sorted(df['date'].unique())
    ics = []
    for d in dates:
        fwd = [fd for fd in dates if fd > d]
        if len(fwd) < 4:
            continue
        fwd_d = fwd[min(3, len(fwd)-1)]
        today = df[df['date'] == d][['symbol', 'score', 'current_price']]
        future = df[df['date'] == fwd_d][['symbol', 'current_price']]
        future.columns = ['symbol', 'future_price']
        m = today.merge(future, on='symbol', how='inner').dropna()
        if len(m) < 20:
            continue
        m['ret'] = (m['future_price'] / m['current_price'] - 1) * 100
        rho, _ = spearmanr(m['score'], m['ret'])
        if not np.isnan(rho):
            ics.append(rho)
    return {
        'mean_ic': float(np.mean(ics)) if ics else 0,
        'pct_pos': sum(1 for x in ics if x > 0) / max(len(ics), 1) * 100,
    }


GRID = {
    'risk_adjustment': [-0.20, -0.15, -0.10, -0.05, 0.00, +0.05, +0.10, +0.20],
    'fundamental_quality': [0.00, 0.08, 0.12, 0.15, 0.20],
    'momentum_technical': [0.15, 0.20, 0.25, 0.30],
    'growth': [0.00, 0.08, 0.12],
    'value': [0.00, 0.05, 0.10],
}

FIXED = {
    'volume_strength': 0.10,
    'multi_timeframe': 0.18,
    'ml_signal': 0.00,
}


def generate_calibrations() -> list[dict]:
    """Generate weight combinations from the grid."""
    combos = []
    for risk, fund, mom, growth, value in product(
        GRID['risk_adjustment'],
        GRID['fundamental_quality'],
        GRID['momentum_technical'],
        GRID['growth'],
        GRID['value'],
    ):
        w = {
            'risk_adjustment': risk,
            'fundamental_quality': fund,
            'momentum_technical': mom,
            'growth': growth,
            'value': value,
            **FIXED,
        }
        total_abs = sum(abs(v) for v in w.values())
        if total_abs < 0.3:
            continue
        combos.append(w)
    return combos


def main():
    print('=' * 90)
    print('CALIBRATION GRID SEARCH — Finding Optimal Weights for Medium-Aggressive')
    print('=' * 90)

    df_all = load_snapshots()
    prices = PriceCache(refresh_days=1)

    print(f'Data: {len(df_all)} rows, {df_all["date"].nunique()} dates, '
          f'{df_all["symbol"].nunique()} symbols')
    print(f'Range: {df_all["date"].min().date()} -> {df_all["date"].max().date()}')

    calibrations = generate_calibrations()
    print(f'\nTotal calibrations to test: {len(calibrations)}')

    if len(calibrations) > 200:
        print(f'Too many ({len(calibrations)}), sampling 150 random + key combos...')
        import random
        random.seed(42)
        key_combos = [
            {'risk_adjustment': -0.05, 'fundamental_quality': 0.15,
             'momentum_technical': 0.20, 'growth': 0.12, 'value': 0.10, **FIXED},
            {'risk_adjustment': -0.10, 'fundamental_quality': 0.15,
             'momentum_technical': 0.25, 'growth': 0.08, 'value': 0.05, **FIXED},
            {'risk_adjustment': -0.15, 'fundamental_quality': 0.12,
             'momentum_technical': 0.25, 'growth': 0.12, 'value': 0.10, **FIXED},
            {'risk_adjustment': 0.00, 'fundamental_quality': 0.20,
             'momentum_technical': 0.20, 'growth': 0.12, 'value': 0.10, **FIXED},
            {'risk_adjustment': +0.10, 'fundamental_quality': 0.15,
             'momentum_technical': 0.25, 'growth': 0.08, 'value': 0.05, **FIXED},
            {'risk_adjustment': +0.20, 'fundamental_quality': 0.15,
             'momentum_technical': 0.25, 'growth': 0.00, 'value': 0.00, **FIXED},
            {'risk_adjustment': -0.20, 'fundamental_quality': 0.00,
             'momentum_technical': 0.25, 'growth': 0.00, 'value': 0.00, **FIXED},
            # Current v2
            {'momentum_technical': 0.1026, 'volume_strength': 0.0803,
             'multi_timeframe': 0.1329, 'ml_signal': -0.2287,
             'risk_adjustment': -0.45, 'fundamental_quality': 0.0,
             'growth': 0.0, 'value': 0.0},
            # V1 baseline
            {'fundamental_quality': 0.15, 'momentum_technical': 0.25,
             'volume_strength': 0.05, 'multi_timeframe': 0.15,
             'ml_signal': 0.00, 'risk_adjustment': 0.40,
             'growth': 0.00, 'value': 0.00},
        ]
        sampled = random.sample(calibrations, min(141, len(calibrations)))
        calibrations = key_combos + sampled

    print(f'Running {len(calibrations)} calibrations...\n')

    all_results = []
    t0 = time.time()

    for i, weights in enumerate(calibrations):
        try:
            snaps = rescore(df_all, weights)
            if len(snaps) < 20:
                continue

            summary = run_backtest(snaps, f'cal_{i}', prices)
            ic = ic_quick(df_all, weights)

            row = {
                'idx': i,
                'risk_adj': weights.get('risk_adjustment', 0),
                'fundamental': weights.get('fundamental_quality', 0),
                'momentum': weights.get('momentum_technical', 0),
                'growth': weights.get('growth', 0),
                'value': weights.get('value', 0),
                'volume': weights.get('volume_strength', 0),
                'mtf': weights.get('multi_timeframe', 0),
                'total_return': summary.get('total_return_pct', 0),
                'cagr': summary.get('cagr_pct', 0),
                'sharpe': summary.get('sharpe', 0),
                'sortino': summary.get('sortino', 0),
                'max_dd': summary.get('max_drawdown_pct', 0),
                'win_rate': summary.get('trades_win_rate_pct', 0),
                'profit_factor': summary.get('profit_factor', 0),
                'trades': summary.get('trades_total', 0),
                'excess_nifty': summary.get('excess_return_pct', 0),
                'mean_ic': ic.get('mean_ic', 0),
                'weights': weights,
            }
            all_results.append(row)

            if (i + 1) % 10 == 0:
                elapsed = time.time() - t0
                rate = (i + 1) / elapsed
                eta = (len(calibrations) - i - 1) / rate
                print(f'  [{i+1}/{len(calibrations)}] {elapsed:.0f}s elapsed, '
                      f'~{eta:.0f}s remaining | '
                      f'Best Sharpe so far: {max(r["sharpe"] for r in all_results):.2f}')

        except Exception as e:
            continue

    total_time = time.time() - t0
    print(f'\nCompleted {len(all_results)} calibrations in {total_time:.0f}s')

    if not all_results:
        print('No successful results!')
        return

    df = pd.DataFrame(all_results)

    print('\n' + '=' * 90)
    print('TOP 15 BY SHARPE RATIO')
    print('=' * 90)
    top = df.nlargest(15, 'sharpe')
    print(f'\n{"#":<3} {"Risk":>6} {"Fund":>6} {"Mom":>6} {"Grw":>5} {"Val":>5} '
          f'{"Return":>8} {"CAGR":>7} {"Sharpe":>7} {"MaxDD":>8} {"WinR":>6} {"PF":>6} {"ExNif":>7}')
    print('-' * 95)
    for rank, (_, r) in enumerate(top.iterrows(), 1):
        print(f'{rank:<3} {r["risk_adj"]:>+6.2f} {r["fundamental"]:>6.2f} '
              f'{r["momentum"]:>6.2f} {r["growth"]:>5.2f} {r["value"]:>5.2f} '
              f'{r["total_return"]:>+7.1f}% {r["cagr"]:>+6.1f}% '
              f'{r["sharpe"]:>7.2f} {r["max_dd"]:>+7.1f}% '
              f'{r["win_rate"]:>5.1f}% {r["profit_factor"]:>5.2f} '
              f'{r["excess_nifty"]:>+6.1f}%')

    print('\n' + '=' * 90)
    print('TOP 10 BY TOTAL RETURN')
    print('=' * 90)
    top_ret = df.nlargest(10, 'total_return')
    print(f'\n{"#":<3} {"Risk":>6} {"Fund":>6} {"Mom":>6} {"Grw":>5} {"Val":>5} '
          f'{"Return":>8} {"CAGR":>7} {"Sharpe":>7} {"MaxDD":>8} {"PF":>6}')
    print('-' * 85)
    for rank, (_, r) in enumerate(top_ret.iterrows(), 1):
        print(f'{rank:<3} {r["risk_adj"]:>+6.2f} {r["fundamental"]:>6.2f} '
              f'{r["momentum"]:>6.2f} {r["growth"]:>5.2f} {r["value"]:>5.2f} '
              f'{r["total_return"]:>+7.1f}% {r["cagr"]:>+6.1f}% '
              f'{r["sharpe"]:>7.2f} {r["max_dd"]:>+7.1f}% '
              f'{r["profit_factor"]:>5.2f}')

    print('\n' + '=' * 90)
    print('TOP 10 BY RISK-ADJUSTED (Sharpe > 1.0, Max DD > -25%)')
    print('=' * 90)
    safe = df[(df['sharpe'] > 1.0) & (df['max_dd'] > -25)].nlargest(10, 'sharpe')
    if safe.empty:
        safe = df[df['sharpe'] > 0.5].nlargest(10, 'sharpe')
    print(f'\n{"#":<3} {"Risk":>6} {"Fund":>6} {"Mom":>6} {"Grw":>5} {"Val":>5} '
          f'{"Return":>8} {"CAGR":>7} {"Sharpe":>7} {"MaxDD":>8} {"PF":>6} {"ExNif":>7}')
    print('-' * 90)
    for rank, (_, r) in enumerate(safe.iterrows(), 1):
        print(f'{rank:<3} {r["risk_adj"]:>+6.2f} {r["fundamental"]:>6.2f} '
              f'{r["momentum"]:>6.2f} {r["growth"]:>5.2f} {r["value"]:>5.2f} '
              f'{r["total_return"]:>+7.1f}% {r["cagr"]:>+6.1f}% '
              f'{r["sharpe"]:>7.2f} {r["max_dd"]:>+7.1f}% '
              f'{r["profit_factor"]:>5.2f} {r["excess_nifty"]:>+6.1f}%')

    print('\n' + '=' * 90)
    print('WEIGHT SENSITIVITY ANALYSIS')
    print('=' * 90)

    for param in ['risk_adj', 'fundamental', 'momentum', 'growth', 'value']:
        grouped = df.groupby(param).agg({
            'sharpe': 'mean',
            'total_return': 'mean',
            'max_dd': 'mean',
            'profit_factor': 'mean',
        }).round(2)
        print(f'\n  {param.upper()}:')
        for val, row in grouped.iterrows():
            print(f'    {val:>+6.2f} -> Sharpe={row["sharpe"]:.2f}  '
                  f'Return={row["total_return"]:+.1f}%  '
                  f'MaxDD={row["max_dd"]:.1f}%  PF={row["profit_factor"]:.2f}')

    best = df.loc[df['sharpe'].idxmax()]
    print('\n' + '=' * 90)
    print('RECOMMENDED CALIBRATION (Best Sharpe)')
    print('=' * 90)
    print(f'\n  risk_adjustment:     {best["risk_adj"]:+.2f}')
    print(f'  fundamental_quality: {best["fundamental"]:.2f}')
    print(f'  momentum_technical:  {best["momentum"]:.2f}')
    print(f'  growth:              {best["growth"]:.2f}')
    print(f'  value:               {best["value"]:.2f}')
    print(f'  volume_strength:     {best["volume"]:.2f}')
    print(f'  multi_timeframe:     {best["mtf"]:.2f}')
    print(f'\n  Return: {best["total_return"]:+.1f}% | CAGR: {best["cagr"]:+.1f}% | '
          f'Sharpe: {best["sharpe"]:.2f} | MaxDD: {best["max_dd"]:.1f}% | '
          f'PF: {best["profit_factor"]:.2f} | Excess: {best["excess_nifty"]:+.1f}%')

    out = REPO / 'data' / 'calibration_grid_search_results.json'
    export = {
        'best_sharpe': {k: v for k, v in best.to_dict().items() if k != 'weights'},
        'best_sharpe_weights': best['weights'],
        'top_15_sharpe': top[[c for c in top.columns if c != 'weights']].to_dict('records'),
        'sensitivity': {
            param: df.groupby(param)['sharpe'].mean().to_dict()
            for param in ['risk_adj', 'fundamental', 'momentum', 'growth', 'value']
        },
        'total_calibrations': len(all_results),
        'runtime_seconds': total_time,
    }
    with open(out, 'w') as f:
        json.dump(export, f, indent=2, default=str)
    print(f'\nFull results saved to {out}')


if __name__ == '__main__':
    main()
