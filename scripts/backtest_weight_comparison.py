"""Compare v2 current weights vs suggested fix weights via backtest.

Uses the cached Path2 snapshot data (OHLCV-derived component scores) and
re-scores with three weight sets:
  1. v2_current  — the live GLOBAL calibrated weights
  2. v2_fixed    — suggested medium-aggressive investor weights
  3. v1_baseline — the v1 regime defaults (neutral/SIDEWAYS)

All three share the same component scores and price data — only the
weight-to-score mapping differs, giving a clean apples-to-apples
comparison of ranking quality.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backtest.data.path1_loader import _synthesise_v2_score, DateSnapshot
from backtest.data.prices import PriceCache
from backtest.engine import BacktestEngine, EngineConfig
from backtest.metrics import summarize

logging.basicConfig(level=logging.INFO, format='%(message)s')

WEIGHT_SETS = {
    'v2_current': {
        'momentum_technical': 0.1026,
        'volume_strength': 0.0803,
        'multi_timeframe': 0.1329,
        'ml_signal': -0.2287,
        'risk_adjustment': -0.45,
        'fundamental_quality': 0.0,
        'growth': 0.0,
        'value': 0.0,
    },
    'v2_fixed_medium_aggressive': {
        'fundamental_quality': 0.15,
        'momentum_technical': 0.20,
        'volume_strength': 0.10,
        'multi_timeframe': 0.18,
        'ml_signal': 0.00,
        'risk_adjustment': -0.05,
        'growth': 0.12,
        'value': 0.10,
    },
    'v1_baseline_sideways': {
        'fundamental_quality': 0.15,
        'momentum_technical': 0.25,
        'volume_strength': 0.05,
        'multi_timeframe': 0.15,
        'ml_signal': 0.00,
        'risk_adjustment': 0.40,
        'growth': 0.00,
        'value': 0.00,
    },
}


def load_cached_snapshots() -> pd.DataFrame:
    cache_dir = REPO / 'backtest' / 'cache' / 'scores'
    pkl_files = sorted(cache_dir.glob('snapshots_*.pkl'))
    if not pkl_files:
        raise FileNotFoundError(f'No cached snapshot files in {cache_dir}')
    path = pkl_files[-1]
    logging.info(f'Loading cached snapshots: {path.name}')
    df = pd.read_pickle(path)
    df['date'] = pd.to_datetime(df['date'])
    logging.info(f'  {len(df)} rows, {df["date"].nunique()} dates, '
                 f'{df["symbol"].nunique()} symbols')
    logging.info(f'  Date range: {df["date"].min().date()} -> {df["date"].max().date()}')
    return df


def rescore_snapshots(df_all: pd.DataFrame, weights: dict,
                      label: str) -> list[DateSnapshot]:
    df = df_all.copy()
    df['score_engine'] = _synthesise_v2_score(df, weights)
    valid = df.dropna(subset=['score_engine', 'current_price'])
    snapshots = []
    for d, grp in valid.groupby('date'):
        snapshots.append(DateSnapshot(
            decision_date=d.date() if hasattr(d, 'date') else d,
            df=grp.reset_index(drop=True),
        ))
    logging.info(f'  [{label}] {len(snapshots)} rebalance dates, '
                 f'avg {len(valid)//max(len(snapshots),1)} stocks/date')
    return snapshots


def run_engine(snapshots: list[DateSnapshot], label: str,
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
        result.equity_curve,
        result.trades,
        cfg.initial_capital,
        benchmark=result.benchmark_curve,
    )
    return result.summary


def ic_analysis(df_all: pd.DataFrame, weights: dict, label: str) -> dict:
    """Compute Spearman IC between score and forward 30d return."""
    from scipy.stats import spearmanr

    df = df_all.copy()
    df['score'] = _synthesise_v2_score(df, weights)

    dates = sorted(df['date'].unique())
    ics = []
    spreads = []

    for i, d in enumerate(dates):
        fwd_dates = [fd for fd in dates if fd > d]
        if len(fwd_dates) < 4:
            continue
        fwd_d = fwd_dates[min(3, len(fwd_dates)-1)]

        today = df[df['date'] == d][['symbol', 'score', 'current_price']].copy()
        future = df[df['date'] == fwd_d][['symbol', 'current_price']].copy()
        future.columns = ['symbol', 'future_price']

        merged = today.merge(future, on='symbol', how='inner')
        merged = merged.dropna(subset=['score', 'current_price', 'future_price'])
        if len(merged) < 20:
            continue

        merged['return'] = (merged['future_price'] / merged['current_price'] - 1) * 100

        rho, p = spearmanr(merged['score'], merged['return'])
        if not np.isnan(rho):
            ics.append(rho)

        q80 = merged['score'].quantile(0.80)
        q20 = merged['score'].quantile(0.20)
        top = merged[merged['score'] >= q80]['return'].mean()
        bot = merged[merged['score'] <= q20]['return'].mean()
        if not np.isnan(top) and not np.isnan(bot):
            spreads.append(top - bot)

    return {
        'label': label,
        'mean_ic': float(np.mean(ics)) if ics else 0.0,
        'std_ic': float(np.std(ics)) if ics else 0.0,
        'n_periods': len(ics),
        'mean_spread_pp': float(np.mean(spreads)) if spreads else 0.0,
        'pct_positive_ic': sum(1 for x in ics if x > 0) / max(len(ics), 1) * 100,
    }


def score_distribution_sample(df_all: pd.DataFrame, weights: dict,
                              label: str) -> None:
    """Show score distribution for the LATEST date."""
    df = df_all.copy()
    df['score'] = _synthesise_v2_score(df, weights)
    latest = df[df['date'] == df['date'].max()].copy()
    latest = latest.dropna(subset=['score']).sort_values('score', ascending=False)

    print(f'\n  [{label}] Top 10 stocks (latest date):')
    print(f'  {"Rank":<5} {"Symbol":<12} {"Score":>6} {"Risk_Adj":>9} {"Fund":>6} '
          f'{"Mom":>6} {"Growth":>7} {"Value":>6}')
    print(f'  {"-"*60}')
    for i, (_, r) in enumerate(latest.head(10).iterrows()):
        print(f'  {i+1:<5} {r["symbol"]:<12} {r["score"]:>6.1f} '
              f'{r.get("hybrid_risk_adjustment", 0):>9.1f} '
              f'{r.get("hybrid_fundamental_quality", 0):>6.1f} '
              f'{r.get("hybrid_momentum_technical", 0):>6.1f} '
              f'{r.get("hybrid_growth", 0):>7.1f} '
              f'{r.get("hybrid_value", 0):>6.1f}')

    print(f'\n  [{label}] Bottom 5 stocks:')
    for i, (_, r) in enumerate(latest.tail(5).iterrows()):
        print(f'  {len(latest)-4+i:<5} {r["symbol"]:<12} {r["score"]:>6.1f} '
              f'{r.get("hybrid_risk_adjustment", 0):>9.1f} '
              f'{r.get("hybrid_fundamental_quality", 0):>6.1f}')


def main():
    print('=' * 80)
    print('V2 WEIGHT COMPARISON BACKTEST')
    print('Current v2 vs Suggested Fix vs v1 Baseline')
    print('=' * 80)

    df_all = load_cached_snapshots()
    prices = PriceCache(refresh_days=1)

    results = {}

    for label, weights in WEIGHT_SETS.items():
        print(f'\n{"="*60}')
        print(f'ENGINE: {label}')
        print(f'{"="*60}')
        print(f'  Weights: { {k: v for k, v in weights.items() if v != 0} }')

        snapshots = rescore_snapshots(df_all, weights, label)

        print(f'\n  --- IC Analysis ---')
        ic = ic_analysis(df_all, weights, label)
        print(f'  Mean IC:          {ic["mean_ic"]:+.4f}')
        print(f'  IC Std:           {ic["std_ic"]:.4f}')
        print(f'  Periods:          {ic["n_periods"]}')
        print(f'  Mean Spread (pp): {ic["mean_spread_pp"]:+.2f}')
        print(f'  % Positive IC:    {ic["pct_positive_ic"]:.0f}%')

        score_distribution_sample(df_all, weights, label)

        print(f'\n  --- Portfolio Backtest ---')
        try:
            summary = run_engine(snapshots, label, prices)
            results[label] = {**summary, **ic}
            print(f'  Total Return:     {summary["total_return_pct"]:+.2f}%')
            print(f'  CAGR:             {summary["cagr_pct"]:+.2f}%')
            print(f'  Sharpe:           {summary["sharpe"]:.2f}')
            print(f'  Sortino:          {summary["sortino"]:.2f}')
            print(f'  Max Drawdown:     {summary["max_drawdown_pct"]:.2f}%')
            print(f'  Win Rate:         {summary["trades_win_rate_pct"]:.1f}%')
            print(f'  Profit Factor:    {summary["profit_factor"]:.2f}')
            print(f'  Trades:           {summary["trades_total"]}')
            if summary.get('excess_return_pct') is not None:
                print(f'  Excess vs Nifty:  {summary["excess_return_pct"]:+.2f}%')
        except Exception as e:
            print(f'  ENGINE ERROR: {e}')
            results[label] = ic

    print('\n\n' + '=' * 80)
    print('COMPARISON SUMMARY')
    print('=' * 80)

    metrics = ['total_return_pct', 'cagr_pct', 'sharpe', 'sortino',
               'max_drawdown_pct', 'trades_win_rate_pct', 'profit_factor',
               'mean_ic', 'mean_spread_pp', 'pct_positive_ic']
    header = f'{"Metric":<22}'
    for label in WEIGHT_SETS:
        header += f' | {label:<28}'
    print(header)
    print('-' * len(header))

    for m in metrics:
        row = f'{m:<22}'
        for label in WEIGHT_SETS:
            val = results.get(label, {}).get(m)
            if val is not None:
                row += f' | {val:>28.2f}'
            else:
                row += f' | {"N/A":>28}'
        print(row)

    out_path = REPO / 'data' / 'weight_comparison_backtest.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f'\nResults saved to {out_path}')


if __name__ == '__main__':
    main()
