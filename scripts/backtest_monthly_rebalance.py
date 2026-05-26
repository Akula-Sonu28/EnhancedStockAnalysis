"""Backtest: Flow Chaser vs MTF+Momentum vs Stable Balanced
at MONTHLY rebalance (not weekly) — matching the 1-3 month holding period.

This tests whether the strategies that won at weekly rebalancing
still win when you actually hold for a month.
"""

from __future__ import annotations

import json, logging, sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backtest.data.path1_loader import _synthesise_v2_score, DateSnapshot
from backtest.data.prices import PriceCache
from backtest.engine import BacktestEngine, EngineConfig
from backtest.metrics import summarize

logging.basicConfig(level=logging.WARNING)

STRATEGIES = {
    'flow_chaser': {
        'momentum_technical': 0.25, 'volume_strength': 0.25,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.15, 'growth': 0.06, 'value': 0.06, 'ml_signal': 0.0,
    },
    'mtf_momentum_v1': {
        'momentum_technical': 0.25, 'volume_strength': 0.08,
        'multi_timeframe': 0.30, 'fundamental_quality': 0.10,
        'risk_adjustment': -0.12, 'growth': 0.08, 'value': 0.07, 'ml_signal': 0.0,
    },
    'stable_balanced': {
        'momentum_technical': 0.20, 'volume_strength': 0.10,
        'multi_timeframe': 0.20, 'fundamental_quality': 0.25,
        'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.07, 'ml_signal': 0.0,
    },
}

REBALANCE_MODES = ['weekly', 'monthly']


def load_snapshots():
    cache_dir = REPO / 'backtest' / 'cache' / 'scores'
    for p in sorted(cache_dir.glob('snapshots_*_long.pkl'), reverse=True):
        return pd.read_pickle(p).assign(date=lambda d: pd.to_datetime(d['date']))
    for p in sorted(cache_dir.glob('snapshots_*.pkl'), reverse=True):
        return pd.read_pickle(p).assign(date=lambda d: pd.to_datetime(d['date']))
    raise FileNotFoundError('No cached snapshots')


def rescore(df_all, weights):
    df = df_all.copy()
    df['score_engine'] = _synthesise_v2_score(df, weights)
    valid = df.dropna(subset=['score_engine', 'current_price'])
    return [DateSnapshot(decision_date=d.date() if hasattr(d, 'date') else d,
                         df=grp.reset_index(drop=True))
            for d, grp in valid.groupby('date')]


def run_bt(snapshots, label, prices, rebalance):
    cfg = EngineConfig(
        initial_capital=100_000.0,
        target_positions=10,
        max_positions=15,
        sector_cap_pct=30.0,
        rebalance=rebalance,
        selection_mode='rank',
        min_entry_score=45.0,
    )
    engine = BacktestEngine(engine_label=label, cfg=cfg, price_cache=prices)
    result = engine.run(snapshots)
    result.summary = summarize(result.equity_curve, result.trades,
                               cfg.initial_capital, benchmark=result.benchmark_curve)
    return result.summary


def main():
    print('=' * 100)
    print('WEEKLY vs MONTHLY REBALANCE — Does the Strategy Survive Longer Holding Periods?')
    print('=' * 100)

    df_all = load_snapshots()
    prices = PriceCache(refresh_days=1)
    print(f'Data: {df_all["date"].nunique()} weeks, {df_all["symbol"].nunique()} stocks, '
          f'{df_all["date"].min().date()} -> {df_all["date"].max().date()}\n')

    results = {}

    for rebalance in REBALANCE_MODES:
        print(f'\n{"="*50}')
        print(f'  REBALANCE: {rebalance.upper()}')
        print(f'{"="*50}')

        for label, weights in STRATEGIES.items():
            key = f'{label}_{rebalance}'
            snaps = rescore(df_all, weights)
            s = run_bt(snaps, label, prices, rebalance)
            results[key] = {**s, 'strategy': label, 'rebalance': rebalance}

            print(f'  {label:<22} | Ret={s["total_return_pct"]:+6.1f}% '
                  f'Sharpe={s["sharpe"]:5.2f} DD={s["max_drawdown_pct"]:6.1f}% '
                  f'PF={s["profit_factor"]:4.2f} Trades={s["trades_total"]:3d} '
                  f'WinR={s["trades_win_rate_pct"]:4.1f}% '
                  f'Alpha={s.get("excess_return_pct",0):+6.1f}%')

    print('\n\n' + '=' * 100)
    print('COMPARISON: How Each Strategy Changes from Weekly to Monthly')
    print('=' * 100)

    print(f'\n{"Strategy":<22} | {"--- WEEKLY ---":>42} | {"--- MONTHLY ---":>42} | {"Δ Sharpe":>8}')
    print(f'{"":22} | {"Return":>8} {"Sharpe":>7} {"MaxDD":>7} {"PF":>5} {"Trds":>5} | '
          f'{"Return":>8} {"Sharpe":>7} {"MaxDD":>7} {"PF":>5} {"Trds":>5} | ')
    print('-' * 110)

    for label in STRATEGIES:
        w = results[f'{label}_weekly']
        m = results[f'{label}_monthly']
        delta_sharpe = m['sharpe'] - w['sharpe']
        print(f'{label:<22} | '
              f'{w["total_return_pct"]:>+7.1f}% {w["sharpe"]:>7.2f} {w["max_drawdown_pct"]:>+6.1f}% {w["profit_factor"]:>5.2f} {w["trades_total"]:>5d} | '
              f'{m["total_return_pct"]:>+7.1f}% {m["sharpe"]:>7.2f} {m["max_drawdown_pct"]:>+6.1f}% {m["profit_factor"]:>5.2f} {m["trades_total"]:>5d} | '
              f'{delta_sharpe:>+7.2f}')

    print('\n' + '=' * 100)
    print('SHARPE DECAY: How Much Alpha Leaks When You Hold Longer?')
    print('=' * 100)
    for label in STRATEGIES:
        w_sharpe = results[f'{label}_weekly']['sharpe']
        m_sharpe = results[f'{label}_monthly']['sharpe']
        decay = (1 - m_sharpe / w_sharpe) * 100 if w_sharpe > 0 else 0
        print(f'  {label:<22}: Weekly={w_sharpe:.2f} → Monthly={m_sharpe:.2f} | '
              f'Decay: {decay:+.0f}% {"BAD" if decay > 30 else "OK" if decay > 15 else "GOOD"}')

    best_monthly = max(
        [(k, v) for k, v in results.items() if 'monthly' in k],
        key=lambda x: x[1]['sharpe']
    )
    best_weekly = max(
        [(k, v) for k, v in results.items() if 'weekly' in k],
        key=lambda x: x[1]['sharpe']
    )

    print(f'\n  Best WEEKLY:  {best_weekly[0]} (Sharpe {best_weekly[1]["sharpe"]:.2f})')
    print(f'  Best MONTHLY: {best_monthly[0]} (Sharpe {best_monthly[1]["sharpe"]:.2f})')

    out = REPO / 'data' / 'monthly_vs_weekly_rebalance.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f'\nResults saved to {out}')


if __name__ == '__main__':
    main()
