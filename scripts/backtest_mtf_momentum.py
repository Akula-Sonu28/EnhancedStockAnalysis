"""Backtest: Flow Chaser vs MTF+Momentum dominant strategy.

Tests the quant finding that MTF>90 is the real alpha signal (Sharpe 0.90)
and volume adds no edge (p=0.81). Compares current flow_chaser (mom=0.25,
vol=0.25) against MTF+momentum variants.
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
    'flow_chaser_current': {
        'momentum_technical': 0.25, 'volume_strength': 0.25,
        'multi_timeframe': 0.15, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.15, 'growth': 0.06, 'value': 0.06, 'ml_signal': 0.0,
    },
    'mtf_momentum_v1': {
        'momentum_technical': 0.25, 'volume_strength': 0.08,
        'multi_timeframe': 0.30, 'fundamental_quality': 0.10,
        'risk_adjustment': -0.12, 'growth': 0.08, 'value': 0.07, 'ml_signal': 0.0,
    },
    'mtf_momentum_v2': {
        'momentum_technical': 0.28, 'volume_strength': 0.05,
        'multi_timeframe': 0.32, 'fundamental_quality': 0.10,
        'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.07, 'ml_signal': 0.0,
    },
    'mtf_dominant': {
        'momentum_technical': 0.20, 'volume_strength': 0.05,
        'multi_timeframe': 0.38, 'fundamental_quality': 0.10,
        'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.09, 'ml_signal': 0.0,
    },
    'mtf_mom_quality': {
        'momentum_technical': 0.25, 'volume_strength': 0.05,
        'multi_timeframe': 0.28, 'fundamental_quality': 0.15,
        'risk_adjustment': -0.08, 'growth': 0.10, 'value': 0.09, 'ml_signal': 0.0,
    },
    'mtf_mom_balanced': {
        'momentum_technical': 0.22, 'volume_strength': 0.10,
        'multi_timeframe': 0.28, 'fundamental_quality': 0.12,
        'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.10, 'ml_signal': 0.0,
    },
    'pure_mtf': {
        'momentum_technical': 0.15, 'volume_strength': 0.05,
        'multi_timeframe': 0.45, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.10, 'growth': 0.08, 'value': 0.09, 'ml_signal': 0.0,
    },
    'momentum_mtf_equal': {
        'momentum_technical': 0.30, 'volume_strength': 0.05,
        'multi_timeframe': 0.30, 'fundamental_quality': 0.08,
        'risk_adjustment': -0.12, 'growth': 0.08, 'value': 0.07, 'ml_signal': 0.0,
    },
}


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
    print('=' * 95)
    print('MTF+MOMENTUM CALIBRATION TEST — Is MTF the real alpha, not volume?')
    print('=' * 95)

    df_all = load_snapshots()
    prices = PriceCache(refresh_days=1)
    print(f'Data: {df_all["date"].nunique()} weeks, {df_all["symbol"].nunique()} stocks, '
          f'{df_all["date"].min().date()} -> {df_all["date"].max().date()}\n')

    rows = []
    for label, weights in STRATEGIES.items():
        try:
            snaps = rescore(df_all, weights)
            s = run_bt(snaps, label, prices)
            row = {
                'strategy': label,
                'mom': weights['momentum_technical'],
                'vol': weights['volume_strength'],
                'mtf': weights['multi_timeframe'],
                'fund': weights['fundamental_quality'],
                'return': s['total_return_pct'],
                'cagr': s['cagr_pct'],
                'sharpe': s['sharpe'],
                'sortino': s['sortino'],
                'max_dd': s['max_drawdown_pct'],
                'win_rate': s['trades_win_rate_pct'],
                'pf': s['profit_factor'],
                'trades': s['trades_total'],
                'alpha': s.get('excess_return_pct', 0),
            }
            rows.append(row)
            print(f'  {label:<25} Mom={weights["momentum_technical"]:.2f} Vol={weights["volume_strength"]:.2f} '
                  f'MTF={weights["multi_timeframe"]:.2f} | '
                  f'Ret={s["total_return_pct"]:+5.1f}% Sharpe={s["sharpe"]:5.2f} '
                  f'DD={s["max_drawdown_pct"]:5.1f}% PF={s["profit_factor"]:4.2f} '
                  f'Alpha={s.get("excess_return_pct",0):+5.1f}%')
        except Exception as e:
            print(f'  {label:<25} ERROR: {e}')

    df = pd.DataFrame(rows)

    print('\n\n' + '=' * 95)
    print('RANKED BY SHARPE (risk-adjusted return)')
    print('=' * 95)
    ranked = df.sort_values('sharpe', ascending=False)
    print(f'\n{"#":<3} {"Strategy":<25} {"Mom":>5} {"Vol":>5} {"MTF":>5} {"Fund":>5} | '
          f'{"Return":>8} {"Sharpe":>7} {"MaxDD":>8} {"PF":>6} {"Alpha":>8}')
    print('-' * 95)
    for i, (_, r) in enumerate(ranked.iterrows(), 1):
        marker = ' <<<' if i == 1 else (' (current)' if r['strategy'] == 'flow_chaser_current' else '')
        print(f'{i:<3} {r["strategy"]:<25} {r["mom"]:>5.2f} {r["vol"]:>5.2f} {r["mtf"]:>5.2f} {r["fund"]:>5.2f} | '
              f'{r["return"]:>+7.1f}% {r["sharpe"]:>7.2f} {r["max_dd"]:>+7.1f}% '
              f'{r["pf"]:>5.2f} {r["alpha"]:>+7.1f}%{marker}')

    print('\n' + '=' * 95)
    print('KEY COMPARISON: Volume=0.25 vs Volume=0.05')
    print('=' * 95)
    high_vol = df[df['vol'] >= 0.20]['sharpe'].mean()
    low_vol = df[df['vol'] <= 0.10]['sharpe'].mean()
    high_mtf = df[df['mtf'] >= 0.28]['sharpe'].mean()
    low_mtf = df[df['mtf'] <= 0.18]['sharpe'].mean()
    print(f'  High Volume (>=0.20) avg Sharpe: {high_vol:.2f}')
    print(f'  Low Volume  (<=0.10) avg Sharpe: {low_vol:.2f}')
    print(f'  High MTF    (>=0.28) avg Sharpe: {high_mtf:.2f}')
    print(f'  Low MTF     (<=0.18) avg Sharpe: {low_mtf:.2f}')

    best = ranked.iloc[0]
    current = df[df['strategy'] == 'flow_chaser_current'].iloc[0]
    print(f'\n  CURRENT (flow_chaser):  Return={current["return"]:+.1f}% Sharpe={current["sharpe"]:.2f} DD={current["max_dd"]:.1f}%')
    print(f'  BEST    ({best["strategy"]}): Return={best["return"]:+.1f}% Sharpe={best["sharpe"]:.2f} DD={best["max_dd"]:.1f}%')
    improvement = best['sharpe'] - current['sharpe']
    print(f'  Sharpe improvement: {improvement:+.2f} ({improvement/current["sharpe"]*100:+.0f}%)')

    out = REPO / 'data' / 'mtf_momentum_backtest.json'
    with open(out, 'w') as f:
        json.dump(rows, f, indent=2, default=str)
    print(f'\nResults saved to {out}')


if __name__ == '__main__':
    main()
