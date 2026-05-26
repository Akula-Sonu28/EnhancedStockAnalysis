"""Strategy explorer for 15-30 day holding period.

Tests 25+ strategies at BIWEEKLY rebalance (every 2 weeks)
to match the 15-30 day holding window.
"""

from __future__ import annotations

import json, logging, sys
from pathlib import Path
from datetime import date

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
    # --- CURRENT ---
    'mtf_momentum_current': {
        'momentum_technical': 0.25, 'volume_strength': 0.08,
        'multi_timeframe': 0.30, 'fundamental_quality': 0.10,
        'risk_adjustment': -0.12, 'growth': 0.08, 'value': 0.07, 'ml_signal': 0.0,
    },

    # --- MTF DOMINANT VARIANTS ---
    'mtf_heavy': {
        'momentum_technical': 0.20, 'volume_strength': 0.05,
        'multi_timeframe': 0.40, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.12, 'growth': 0.08, 'value': 0.07, 'ml_signal': 0.0,
    },
    'mtf_fund_anchor': {
        'momentum_technical': 0.20, 'volume_strength': 0.05,
        'multi_timeframe': 0.30, 'fundamental_quality': 0.18,
        'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.09, 'ml_signal': 0.0,
    },
    'mtf_growth_tilt': {
        'momentum_technical': 0.22, 'volume_strength': 0.05,
        'multi_timeframe': 0.28, 'fundamental_quality': 0.10,
        'risk_adjustment': -0.10, 'growth': 0.15, 'value': 0.10, 'ml_signal': 0.0,
    },

    # --- MOMENTUM VARIANTS ---
    'momentum_concentrated': {
        'momentum_technical': 0.35, 'volume_strength': 0.05,
        'multi_timeframe': 0.25, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.12, 'growth': 0.08, 'value': 0.07, 'ml_signal': 0.0,
    },
    'momentum_safe': {
        'momentum_technical': 0.28, 'volume_strength': 0.05,
        'multi_timeframe': 0.22, 'fundamental_quality': 0.15,
        'risk_adjustment': -0.05, 'growth': 0.10, 'value': 0.10, 'ml_signal': 0.0,
    },
    'momentum_risk_on': {
        'momentum_technical': 0.28, 'volume_strength': 0.08,
        'multi_timeframe': 0.25, 'fundamental_quality': 0.05,
        'risk_adjustment': -0.22, 'growth': 0.06, 'value': 0.06, 'ml_signal': 0.0,
    },

    # --- RISK-ADJUSTED ---
    'low_vol_momentum': {
        'momentum_technical': 0.22, 'volume_strength': 0.05,
        'multi_timeframe': 0.25, 'fundamental_quality': 0.12,
        'risk_adjustment': 0.15, 'growth': 0.10, 'value': 0.11, 'ml_signal': 0.0,
    },
    'quality_trend': {
        'momentum_technical': 0.18, 'volume_strength': 0.05,
        'multi_timeframe': 0.25, 'fundamental_quality': 0.22,
        'risk_adjustment': 0.05, 'growth': 0.12, 'value': 0.13, 'ml_signal': 0.0,
    },

    # --- HYBRID TIMEFRAME ---
    'short_trend_catch': {
        'momentum_technical': 0.30, 'volume_strength': 0.12,
        'multi_timeframe': 0.28, 'fundamental_quality': 0.05,
        'risk_adjustment': -0.15, 'growth': 0.05, 'value': 0.05, 'ml_signal': 0.0,
    },
    'trend_initiation': {
        'momentum_technical': 0.18, 'volume_strength': 0.20,
        'multi_timeframe': 0.30, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.10, 'growth': 0.07, 'value': 0.07, 'ml_signal': 0.0,
    },
    'breakout_mtf': {
        'momentum_technical': 0.22, 'volume_strength': 0.18,
        'multi_timeframe': 0.28, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.12, 'growth': 0.06, 'value': 0.06, 'ml_signal': 0.0,
    },

    # --- GROWTH STRATEGIES ---
    'growth_momentum': {
        'momentum_technical': 0.22, 'volume_strength': 0.05,
        'multi_timeframe': 0.20, 'fundamental_quality': 0.10,
        'risk_adjustment': -0.08, 'growth': 0.25, 'value': 0.10, 'ml_signal': 0.0,
    },
    'growth_quality': {
        'momentum_technical': 0.15, 'volume_strength': 0.05,
        'multi_timeframe': 0.18, 'fundamental_quality': 0.20,
        'risk_adjustment': -0.05, 'growth': 0.22, 'value': 0.15, 'ml_signal': 0.0,
    },

    # --- VALUE+MOMENTUM ---
    'value_momentum': {
        'momentum_technical': 0.25, 'volume_strength': 0.05,
        'multi_timeframe': 0.20, 'fundamental_quality': 0.12,
        'risk_adjustment': -0.05, 'growth': 0.08, 'value': 0.25, 'ml_signal': 0.0,
    },
    'deep_value_trend': {
        'momentum_technical': 0.18, 'volume_strength': 0.08,
        'multi_timeframe': 0.22, 'fundamental_quality': 0.15,
        'risk_adjustment': 0.05, 'growth': 0.05, 'value': 0.27, 'ml_signal': 0.0,
    },

    # --- BALANCED RISK ---
    'equal_weight_all': {
        'momentum_technical': 0.15, 'volume_strength': 0.10,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.15,
        'risk_adjustment': -0.10, 'growth': 0.15, 'value': 0.10, 'ml_signal': 0.0,
    },
    'risk_parity_15_30': {
        'momentum_technical': 0.18, 'volume_strength': 0.08,
        'multi_timeframe': 0.20, 'fundamental_quality': 0.18,
        'risk_adjustment': 0.08, 'growth': 0.14, 'value': 0.14, 'ml_signal': 0.0,
    },

    # --- AGGRESSIVE ---
    'max_alpha': {
        'momentum_technical': 0.30, 'volume_strength': 0.10,
        'multi_timeframe': 0.30, 'fundamental_quality': 0.05,
        'risk_adjustment': -0.15, 'growth': 0.05, 'value': 0.05, 'ml_signal': 0.0,
    },
    'turbo_mtf': {
        'momentum_technical': 0.25, 'volume_strength': 0.05,
        'multi_timeframe': 0.35, 'fundamental_quality': 0.05,
        'risk_adjustment': -0.18, 'growth': 0.06, 'value': 0.06, 'ml_signal': 0.0,
    },

    # --- DEFENSIVE ---
    'safe_compounder': {
        'momentum_technical': 0.15, 'volume_strength': 0.05,
        'multi_timeframe': 0.18, 'fundamental_quality': 0.28,
        'risk_adjustment': 0.10, 'growth': 0.12, 'value': 0.12, 'ml_signal': 0.0,
    },
    'dividend_momentum': {
        'momentum_technical': 0.20, 'volume_strength': 0.05,
        'multi_timeframe': 0.18, 'fundamental_quality': 0.15,
        'risk_adjustment': 0.08, 'growth': 0.05, 'value': 0.29, 'ml_signal': 0.0,
    },
}


def biweekly_rebalance_dates(all_dates):
    """Pick every other Monday-equivalent from the trading calendar."""
    df = pd.DataFrame({'d': pd.to_datetime(all_dates)})
    df['iso_week'] = df['d'].dt.isocalendar().week
    df['iso_year'] = df['d'].dt.isocalendar().year
    weekly = df.groupby(['iso_year', 'iso_week'])['d'].min().tolist()
    return [d.date() for i, d in enumerate(weekly) if i % 2 == 0]


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


def run_bt(snapshots, label, prices, rebalance='weekly'):
    cfg = EngineConfig(initial_capital=100_000.0, target_positions=10,
                       max_positions=15, sector_cap_pct=30.0,
                       rebalance=rebalance, selection_mode='rank',
                       min_entry_score=45.0)
    engine = BacktestEngine(engine_label=label, cfg=cfg, price_cache=prices)
    result = engine.run(snapshots)
    result.summary = summarize(result.equity_curve, result.trades,
                               cfg.initial_capital, benchmark=result.benchmark_curve)
    return result.summary


def main():
    print('=' * 100)
    print('15-30 DAY STRATEGY EXPLORER — 25 Strategies at Biweekly Rebalance')
    print('=' * 100)

    df_all = load_snapshots()
    prices = PriceCache(refresh_days=1)
    print(f'Data: {df_all["date"].nunique()} weeks, {df_all["symbol"].nunique()} stocks')
    print(f'Range: {df_all["date"].min().date()} -> {df_all["date"].max().date()}')

    rebalance_modes = {
        'weekly': 'weekly',
        'biweekly': 'monthly',  # closest proxy in the engine
    }

    for rb_label, rb_mode in rebalance_modes.items():
        print(f'\n{"="*50}')
        print(f'  REBALANCE: {rb_label.upper()}')
        print(f'{"="*50}')

        rows = []
        for label, weights in STRATEGIES.items():
            try:
                snaps = rescore(df_all, weights)
                s = run_bt(snaps, label, prices, rb_mode)
                rows.append({
                    'strategy': label, 'rebalance': rb_label,
                    'return': s['total_return_pct'], 'cagr': s['cagr_pct'],
                    'sharpe': s['sharpe'], 'sortino': s['sortino'],
                    'max_dd': s['max_drawdown_pct'],
                    'win_rate': s['trades_win_rate_pct'],
                    'pf': s['profit_factor'], 'trades': s['trades_total'],
                    'alpha': s.get('excess_return_pct', 0),
                    'mom': weights['momentum_technical'],
                    'mtf': weights['multi_timeframe'],
                    'fund': weights['fundamental_quality'],
                    'risk': weights['risk_adjustment'],
                })
                print(f'  {label:<25} Ret={s["total_return_pct"]:+5.1f}% '
                      f'Sharpe={s["sharpe"]:5.2f} DD={s["max_drawdown_pct"]:5.1f}% '
                      f'PF={s["profit_factor"]:4.2f} WR={s["trades_win_rate_pct"]:4.1f}%')
            except Exception as e:
                print(f'  {label:<25} ERROR: {e}')

        df = pd.DataFrame(rows)
        if df.empty:
            continue

        print(f'\n  TOP 10 BY SHARPE ({rb_label}):')
        top = df.nlargest(10, 'sharpe')
        print(f'  {"#":<3} {"Strategy":<25} {"Mom":>5} {"MTF":>5} {"Fund":>5} {"Risk":>6} | '
              f'{"Ret":>7} {"Sharpe":>7} {"DD":>7} {"PF":>5} {"Alpha":>7}')
        print(f'  {"-"*90}')
        for i, (_, r) in enumerate(top.iterrows(), 1):
            print(f'  {i:<3} {r["strategy"]:<25} {r["mom"]:>5.2f} {r["mtf"]:>5.2f} '
                  f'{r["fund"]:>5.2f} {r["risk"]:>+5.2f} | '
                  f'{r["return"]:>+6.1f}% {r["sharpe"]:>7.2f} {r["max_dd"]:>+6.1f}% '
                  f'{r["pf"]:>5.2f} {r["alpha"]:>+6.1f}%')

    out = REPO / 'data' / 'strategy_15_30day_results.json'
    with open(out, 'w') as f:
        json.dump(rows, f, indent=2, default=str)
    print(f'\nResults saved to {out}')


if __name__ == '__main__':
    main()
