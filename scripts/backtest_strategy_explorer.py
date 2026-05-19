"""Strategy explorer: test 20+ distinct investment strategies to find the best.

Goes beyond momentum/volume variations to test fundamentally different
approaches: contrarian, breakout, quality-momentum, sector rotation,
mean-reversion, GARP, etc.
"""

from __future__ import annotations

import json
import logging
import sys
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
    # --- WINNER FROM PRIOR RUN ---
    'flow_chaser': {
        'momentum_technical': 0.25, 'volume_strength': 0.25,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.15, 'growth': 0.06, 'value': 0.06, 'ml_signal': 0.0,
    },

    # --- PURE STRATEGIES (single-factor dominant) ---
    'pure_momentum': {
        'momentum_technical': 0.50, 'volume_strength': 0.10,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.05,
        'risk_adjustment': -0.10, 'growth': 0.05, 'value': 0.05, 'ml_signal': 0.0,
    },
    'pure_volume': {
        'momentum_technical': 0.10, 'volume_strength': 0.50,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.05,
        'risk_adjustment': -0.10, 'growth': 0.05, 'value': 0.05, 'ml_signal': 0.0,
    },
    'pure_quality': {
        'momentum_technical': 0.10, 'volume_strength': 0.05,
        'multi_timeframe': 0.10, 'fundamental_quality': 0.45,
        'risk_adjustment': 0.15, 'growth': 0.10, 'value': 0.05, 'ml_signal': 0.0,
    },
    'pure_value': {
        'momentum_technical': 0.10, 'volume_strength': 0.05,
        'multi_timeframe': 0.10, 'fundamental_quality': 0.15,
        'risk_adjustment': 0.10, 'growth': 0.10, 'value': 0.40, 'ml_signal': 0.0,
    },

    # --- CLASSIC STRATEGIES ---
    'GARP': {  # Growth At Reasonable Price
        'momentum_technical': 0.15, 'volume_strength': 0.05,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.15,
        'risk_adjustment': 0.05, 'growth': 0.25, 'value': 0.20, 'ml_signal': 0.0,
    },
    'quality_momentum': {  # Buffett meets momentum
        'momentum_technical': 0.25, 'volume_strength': 0.05,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.25,
        'risk_adjustment': 0.05, 'growth': 0.15, 'value': 0.10, 'ml_signal': 0.0,
    },
    'contrarian_value': {  # Buy beaten-down quality
        'momentum_technical': -0.10, 'volume_strength': 0.10,
        'multi_timeframe': -0.05, 'fundamental_quality': 0.30,
        'risk_adjustment': 0.10, 'growth': 0.15, 'value': 0.30, 'ml_signal': 0.0,
    },
    'mean_reversion': {  # Buy oversold, sell overbought
        'momentum_technical': -0.20, 'volume_strength': 0.15,
        'multi_timeframe': -0.10, 'fundamental_quality': 0.20,
        'risk_adjustment': -0.10, 'growth': 0.10, 'value': 0.25, 'ml_signal': 0.0,
    },

    # --- FLOW VARIATIONS ---
    'flow_chaser_v2': {  # Volume even higher
        'momentum_technical': 0.20, 'volume_strength': 0.30,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.15, 'growth': 0.06, 'value': 0.06, 'ml_signal': 0.0,
    },
    'flow_quality': {  # Flow + fundamentals anchor
        'momentum_technical': 0.20, 'volume_strength': 0.22,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.15,
        'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.10, 'ml_signal': 0.0,
    },
    'flow_growth': {  # Flow + growth tilt
        'momentum_technical': 0.22, 'volume_strength': 0.22,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.10, 'growth': 0.15, 'value': 0.08, 'ml_signal': 0.0,
    },

    # --- TREND STRATEGIES ---
    'trend_follower': {  # MTF dominant
        'momentum_technical': 0.20, 'volume_strength': 0.10,
        'multi_timeframe': 0.35, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.09, 'ml_signal': 0.0,
    },
    'breakout_hunter': {  # Volume spike + momentum initiation
        'momentum_technical': 0.20, 'volume_strength': 0.30,
        'multi_timeframe': 0.20, 'fundamental_quality': 0.05,
        'risk_adjustment': -0.15, 'growth': 0.05, 'value': 0.05, 'ml_signal': 0.0,
    },

    # --- RISK-ADJUSTED ---
    'risk_parity': {  # Equal risk contribution
        'momentum_technical': 0.18, 'volume_strength': 0.12,
        'multi_timeframe': 0.18, 'fundamental_quality': 0.18,
        'risk_adjustment': 0.10, 'growth': 0.12, 'value': 0.12, 'ml_signal': 0.0,
    },
    'max_sharpe': {  # Optimize risk-adjusted return
        'momentum_technical': 0.22, 'volume_strength': 0.15,
        'multi_timeframe': 0.18, 'fundamental_quality': 0.12,
        'risk_adjustment': -0.08, 'growth': 0.10, 'value': 0.15, 'ml_signal': 0.0,
    },

    # --- AGGRESSIVE ---
    'high_beta_momentum': {  # Ride the riskiest momentum
        'momentum_technical': 0.30, 'volume_strength': 0.15,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.05,
        'risk_adjustment': -0.25, 'growth': 0.05, 'value': 0.05, 'ml_signal': 0.0,
    },
    'turnaround': {  # Low quality + improving momentum
        'momentum_technical': 0.25, 'volume_strength': 0.20,
        'multi_timeframe': 0.15, 'fundamental_quality': -0.10,
        'risk_adjustment': -0.20, 'growth': 0.15, 'value': 0.05, 'ml_signal': 0.0,
    },

    # --- DEFENSIVE ---
    'dividend_quality': {
        'momentum_technical': 0.10, 'volume_strength': 0.05,
        'multi_timeframe': 0.10, 'fundamental_quality': 0.25,
        'risk_adjustment': 0.15, 'growth': 0.05, 'value': 0.30, 'ml_signal': 0.0,
    },
}


def load_snapshots():
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
    return [DateSnapshot(decision_date=d.date() if hasattr(d, 'date') else d,
                         df=grp.reset_index(drop=True))
            for d, grp in valid.groupby('date')]


def run_bt(snapshots, label, prices):
    cfg = EngineConfig(initial_capital=100_000.0, target_positions=10,
                       max_positions=15, sector_cap_pct=30.0,
                       rebalance='weekly', selection_mode='rank',
                       min_entry_score=45.0)
    engine = BacktestEngine(engine_label=label, cfg=cfg, price_cache=prices)
    result = engine.run(snapshots)
    result.summary = summarize(result.equity_curve, result.trades,
                               cfg.initial_capital, benchmark=result.benchmark_curve)
    return result.summary


def main():
    print('=' * 100)
    print('STRATEGY EXPLORER — 20 Strategies Backtested Over 2.4 Years')
    print('=' * 100)

    df_all = load_snapshots()
    prices = PriceCache(refresh_days=1)
    print(f'Data: {df_all["date"].nunique()} weeks, {df_all["symbol"].nunique()} stocks, '
          f'{df_all["date"].min().date()} -> {df_all["date"].max().date()}\n')

    rows = []
    for label, weights in STRATEGIES.items():
        try:
            snaps = rescore(df_all, weights)
            s = run_bt(snaps, label, prices)
            rows.append({
                'strategy': label,
                'return': s['total_return_pct'],
                'cagr': s['cagr_pct'],
                'sharpe': s['sharpe'],
                'sortino': s['sortino'],
                'max_dd': s['max_drawdown_pct'],
                'win_rate': s['trades_win_rate_pct'],
                'pf': s['profit_factor'],
                'trades': s['trades_total'],
                'alpha': s.get('excess_return_pct', 0),
            })
            print(f'  {label:<25} Return={s["total_return_pct"]:+6.1f}%  '
                  f'Sharpe={s["sharpe"]:5.2f}  MaxDD={s["max_drawdown_pct"]:6.1f}%  '
                  f'PF={s["profit_factor"]:4.2f}  Trades={s["trades_total"]:3d}')
        except Exception as e:
            print(f'  {label:<25} ERROR: {e}')

    df = pd.DataFrame(rows)

    print('\n\n' + '=' * 100)
    print('TOP 10 BY RETURN')
    print('=' * 100)
    top = df.nlargest(10, 'return')
    print(f'\n{"#":<3} {"Strategy":<25} {"Return":>8} {"CAGR":>7} {"Sharpe":>7} {"MaxDD":>8} {"PF":>6} {"Trades":>7} {"Alpha":>8}')
    print('-' * 90)
    for i, (_, r) in enumerate(top.iterrows(), 1):
        print(f'{i:<3} {r["strategy"]:<25} {r["return"]:>+7.1f}% {r["cagr"]:>+6.1f}% '
              f'{r["sharpe"]:>7.2f} {r["max_dd"]:>+7.1f}% {r["pf"]:>5.2f} {r["trades"]:>7.0f} {r["alpha"]:>+7.1f}%')

    print('\n' + '=' * 100)
    print('TOP 10 BY SHARPE (risk-adjusted)')
    print('=' * 100)
    top_s = df.nlargest(10, 'sharpe')
    print(f'\n{"#":<3} {"Strategy":<25} {"Sharpe":>7} {"Return":>8} {"MaxDD":>8} {"PF":>6} {"Alpha":>8}')
    print('-' * 75)
    for i, (_, r) in enumerate(top_s.iterrows(), 1):
        print(f'{i:<3} {r["strategy"]:<25} {r["sharpe"]:>7.2f} {r["return"]:>+7.1f}% '
              f'{r["max_dd"]:>+7.1f}% {r["pf"]:>5.2f} {r["alpha"]:>+7.1f}%')

    print('\n' + '=' * 100)
    print('BOTTOM 5 (worst performers)')
    print('=' * 100)
    bot = df.nsmallest(5, 'return')
    for _, r in bot.iterrows():
        print(f'  {r["strategy"]:<25} Return={r["return"]:+.1f}%  Sharpe={r["sharpe"]:.2f}  MaxDD={r["max_dd"]:.1f}%')

    print('\n' + '=' * 100)
    print('STRATEGY CATEGORY AVERAGES')
    print('=' * 100)
    categories = {
        'Flow-based': ['flow_chaser', 'flow_chaser_v2', 'flow_quality', 'flow_growth'],
        'Momentum': ['pure_momentum', 'high_beta_momentum', 'breakout_hunter'],
        'Quality/Value': ['pure_quality', 'pure_value', 'GARP', 'dividend_quality'],
        'Contrarian': ['contrarian_value', 'mean_reversion', 'turnaround'],
        'Balanced': ['quality_momentum', 'risk_parity', 'max_sharpe', 'trend_follower'],
    }
    for cat, strats in categories.items():
        sub = df[df['strategy'].isin(strats)]
        if sub.empty:
            continue
        print(f'\n  {cat}:')
        print(f'    Avg Return: {sub["return"].mean():+.1f}%  |  Avg Sharpe: {sub["sharpe"].mean():.2f}  |  '
              f'Avg MaxDD: {sub["max_dd"].mean():.1f}%  |  Avg PF: {sub["pf"].mean():.2f}')

    out = REPO / 'data' / 'strategy_explorer_results.json'
    with open(out, 'w') as f:
        json.dump(rows, f, indent=2, default=str)
    print(f'\n\nResults saved to {out}')


if __name__ == '__main__':
    main()
