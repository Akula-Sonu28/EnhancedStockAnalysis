"""Backtest: Current balanced weights vs momentum-rotator weights.

Compares the current v2 fixed weights against a momentum+volume
dominant profile optimized for an active 1-3 month swing trader
with -8% stop tolerance.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date
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

WEIGHT_SETS = {
    'v2_current_balanced': {
        'fundamental_quality': 0.1682,
        'momentum_technical': 0.2057,
        'volume_strength': 0.0935,
        'multi_timeframe': 0.1682,
        'ml_signal': 0.00,
        'risk_adjustment': -0.1402,
        'growth': 0.1121,
        'value': 0.1121,
    },
    'momentum_rotator': {
        'fundamental_quality': 0.10,
        'momentum_technical': 0.28,
        'volume_strength': 0.18,
        'multi_timeframe': 0.18,
        'ml_signal': 0.00,
        'risk_adjustment': -0.10,
        'growth': 0.08,
        'value': 0.08,
    },
    'aggressive_momentum': {
        'fundamental_quality': 0.05,
        'momentum_technical': 0.35,
        'volume_strength': 0.20,
        'multi_timeframe': 0.18,
        'ml_signal': 0.00,
        'risk_adjustment': -0.12,
        'growth': 0.05,
        'value': 0.05,
    },
    'flow_chaser': {
        'fundamental_quality': 0.08,
        'momentum_technical': 0.25,
        'volume_strength': 0.25,
        'multi_timeframe': 0.15,
        'ml_signal': 0.00,
        'risk_adjustment': -0.15,
        'growth': 0.06,
        'value': 0.06,
    },
}


def load_snapshots() -> pd.DataFrame:
    cache_dir = REPO / 'backtest' / 'cache' / 'scores'
    for p in sorted(cache_dir.glob('snapshots_*_long.pkl'), reverse=True):
        df = pd.read_pickle(p)
        df['date'] = pd.to_datetime(df['date'])
        return df
    for p in sorted(cache_dir.glob('snapshots_*.pkl'), reverse=True):
        df = pd.read_pickle(p)
        df['date'] = pd.to_datetime(df['date'])
        return df
    raise FileNotFoundError('No cached snapshots')


def rescore(df_all, weights):
    df = df_all.copy()
    df['score_engine'] = _synthesise_v2_score(df, weights)
    valid = df.dropna(subset=['score_engine', 'current_price'])
    snaps = []
    for d, grp in valid.groupby('date'):
        snaps.append(DateSnapshot(
            decision_date=d.date() if hasattr(d, 'date') else d,
            df=grp.reset_index(drop=True)))
    return snaps


def run_bt(snapshots, label, prices):
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
        benchmark=result.benchmark_curve)
    return result.summary


def ic_quick(df_all, weights):
    from scipy.stats import spearmanr
    df = df_all.copy()
    df['score'] = _synthesise_v2_score(df, weights)
    dates = sorted(df['date'].unique())
    ics, spreads = [], []
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
        q80, q20 = m['score'].quantile(0.80), m['score'].quantile(0.20)
        top = m[m['score'] >= q80]['ret'].mean()
        bot = m[m['score'] <= q20]['ret'].mean()
        if not np.isnan(top) and not np.isnan(bot):
            spreads.append(top - bot)
    return {
        'mean_ic': float(np.mean(ics)) if ics else 0,
        'mean_spread': float(np.mean(spreads)) if spreads else 0,
        'pct_pos': sum(1 for x in ics if x > 0) / max(len(ics), 1) * 100,
    }


def main():
    print('=' * 90)
    print('MOMENTUM ROTATOR BACKTEST — Current Balanced vs Active Rotation Profiles')
    print('=' * 90)

    df_all = load_snapshots()
    prices = PriceCache(refresh_days=1)
    print(f'Data: {len(df_all)} rows, {df_all["date"].nunique()} dates, '
          f'{df_all["symbol"].nunique()} symbols')
    print(f'Range: {df_all["date"].min().date()} -> {df_all["date"].max().date()}\n')

    results = {}

    for label, weights in WEIGHT_SETS.items():
        snaps = rescore(df_all, weights)
        ic = ic_quick(df_all, weights)
        summary = run_bt(snaps, label, prices)
        results[label] = {**summary, **ic}

        active_w = {k: f'{v:+.2f}' for k, v in weights.items() if v != 0}
        print(f'--- {label} ---')
        print(f'  Weights: mom={weights["momentum_technical"]:.2f} vol={weights["volume_strength"]:.2f} '
              f'mtf={weights["multi_timeframe"]:.2f} fund={weights["fundamental_quality"]:.2f} '
              f'risk={weights["risk_adjustment"]:+.2f} grw={weights["growth"]:.2f} val={weights["value"]:.2f}')
        print(f'  Return:  {summary["total_return_pct"]:+.1f}%  |  CAGR: {summary["cagr_pct"]:+.1f}%')
        print(f'  Sharpe:  {summary["sharpe"]:.2f}  |  Sortino: {summary["sortino"]:.2f}')
        print(f'  Max DD:  {summary["max_drawdown_pct"]:.1f}%  |  Win Rate: {summary["trades_win_rate_pct"]:.1f}%')
        print(f'  PF:      {summary["profit_factor"]:.2f}  |  Trades: {summary["trades_total"]}')
        print(f'  IC:      {ic["mean_ic"]:+.4f}  |  Spread: {ic["mean_spread"]:+.2f}pp')
        if summary.get('excess_return_pct') is not None:
            print(f'  Alpha:   {summary["excess_return_pct"]:+.1f}% vs Nifty')
        print()

    print('\n' + '=' * 90)
    print('SIDE-BY-SIDE COMPARISON')
    print('=' * 90)

    metrics = ['total_return_pct', 'cagr_pct', 'sharpe', 'sortino',
               'max_drawdown_pct', 'trades_win_rate_pct', 'profit_factor',
               'trades_total', 'excess_return_pct', 'mean_ic', 'mean_spread']

    labels = list(WEIGHT_SETS.keys())
    header = f'{"Metric":<22}'
    for l in labels:
        short = l[:18]
        header += f' | {short:>18}'
    print(header)
    print('-' * (22 + 21 * len(labels)))

    for m in metrics:
        row = f'{m:<22}'
        for l in labels:
            val = results.get(l, {}).get(m)
            if val is not None:
                row += f' | {val:>18.2f}'
            else:
                row += f' | {"N/A":>18}'
        print(row)

    best = max(results.items(), key=lambda x: x[1].get('total_return_pct', 0))
    best_sharpe = max(results.items(), key=lambda x: x[1].get('sharpe', 0))
    print(f'\nHighest Return: {best[0]} ({best[1]["total_return_pct"]:+.1f}%)')
    print(f'Best Sharpe:    {best_sharpe[0]} ({best_sharpe[1]["sharpe"]:.2f})')

    out = REPO / 'data' / 'momentum_rotator_backtest.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f'\nResults saved to {out}')


if __name__ == '__main__':
    main()
