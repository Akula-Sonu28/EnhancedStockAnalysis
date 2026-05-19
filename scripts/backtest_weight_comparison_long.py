"""Long-horizon weight comparison backtest (2+ years).

Uses Path2Rescorer to build OHLCV-derived snapshots from scratch,
then re-scores with three weight sets and runs the portfolio engine.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backtest.data.path1_loader import _synthesise_v2_score, DateSnapshot
from backtest.data.path2_rescore import Path2Rescorer
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
    'v2_fixed': {
        'fundamental_quality': 0.15,
        'momentum_technical': 0.20,
        'volume_strength': 0.10,
        'multi_timeframe': 0.18,
        'ml_signal': 0.00,
        'risk_adjustment': -0.05,
        'growth': 0.12,
        'value': 0.10,
    },
    'v1_baseline': {
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

START = date(2024, 1, 1)
END = date(2026, 5, 13)
CADENCE = 'weekly'


def build_or_load_snapshots(prices: PriceCache) -> pd.DataFrame:
    """Build component-level snapshots for the full window."""
    cache_path = REPO / 'backtest' / 'cache' / 'scores' / \
        f'snapshots_{START.isoformat()}_{END.isoformat()}_{CADENCE}_n200_long.pkl'

    if cache_path.exists():
        logging.info(f'Loading cached long snapshots: {cache_path.name}')
        df = pd.read_pickle(cache_path)
        df['date'] = pd.to_datetime(df['date'])
        logging.info(f'  {len(df)} rows, {df["date"].nunique()} dates')
        return df

    logging.info(f'Building snapshots from OHLCV: {START} -> {END} ({CADENCE})')
    logging.info('This may take 3-5 minutes...')

    rescorer = Path2Rescorer(prices=prices)
    t0 = time.time()
    snapshots = rescorer.build_snapshots(START, END, cadence=CADENCE, use_cache=False)
    elapsed = time.time() - t0
    logging.info(f'Built {len(snapshots)} snapshots in {elapsed:.0f}s')

    if not snapshots:
        raise RuntimeError('No snapshots built')

    frames = [s.df for s in snapshots]
    df_all = pd.concat(frames, ignore_index=True)
    df_all['date'] = pd.to_datetime(df_all['date'])

    try:
        df_all.to_pickle(cache_path)
        logging.info(f'Cached to {cache_path.name}')
    except Exception as e:
        logging.warning(f'Cache write failed: {e}')

    return df_all


def rescore(df_all: pd.DataFrame, weights: dict, label: str) -> list[DateSnapshot]:
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


def ic_analysis(df_all: pd.DataFrame, weights: dict) -> dict:
    from scipy.stats import spearmanr

    df = df_all.copy()
    df['score'] = _synthesise_v2_score(df, weights)
    dates = sorted(df['date'].unique())
    ics, spreads = [], []

    for i, d in enumerate(dates):
        fwd = [fd for fd in dates if fd > d]
        if len(fwd) < 4:
            continue
        fwd_d = fwd[min(3, len(fwd)-1)]

        today = df[df['date'] == d][['symbol', 'score', 'current_price']].copy()
        future = df[df['date'] == fwd_d][['symbol', 'current_price']].copy()
        future.columns = ['symbol', 'future_price']
        merged = today.merge(future, on='symbol', how='inner')
        merged = merged.dropna(subset=['score', 'current_price', 'future_price'])
        if len(merged) < 20:
            continue

        merged['return'] = (merged['future_price'] / merged['current_price'] - 1) * 100
        rho, _ = spearmanr(merged['score'], merged['return'])
        if not np.isnan(rho):
            ics.append(rho)

        q80, q20 = merged['score'].quantile(0.80), merged['score'].quantile(0.20)
        top = merged[merged['score'] >= q80]['return'].mean()
        bot = merged[merged['score'] <= q20]['return'].mean()
        if not np.isnan(top) and not np.isnan(bot):
            spreads.append(top - bot)

    return {
        'mean_ic': float(np.mean(ics)) if ics else 0,
        'std_ic': float(np.std(ics)) if ics else 0,
        'n_periods': len(ics),
        'mean_spread_pp': float(np.mean(spreads)) if spreads else 0,
        'pct_positive_ic': sum(1 for x in ics if x > 0) / max(len(ics), 1) * 100,
    }


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
        result.equity_curve, result.trades, cfg.initial_capital,
        benchmark=result.benchmark_curve,
    )
    return result.summary


def main():
    print('=' * 80)
    print(f'LONG-HORIZON WEIGHT COMPARISON BACKTEST')
    print(f'Period: {START} -> {END} ({(END - START).days / 365.25:.1f} years)')
    print(f'Cadence: {CADENCE}')
    print('=' * 80)

    prices = PriceCache(refresh_days=1)
    df_all = build_or_load_snapshots(prices)

    date_range = df_all['date']
    print(f'\nData: {len(df_all)} rows, {date_range.nunique()} dates, '
          f'{df_all["symbol"].nunique()} symbols')
    print(f'Range: {date_range.min().date()} -> {date_range.max().date()}')

    results = {}

    for label, weights in WEIGHT_SETS.items():
        print(f'\n{"="*60}')
        print(f'ENGINE: {label}')
        print(f'{"="*60}')
        active = {k: v for k, v in weights.items() if v != 0}
        print(f'  Active weights: {active}')

        snapshots = rescore(df_all, weights, label)
        print(f'  Snapshots: {len(snapshots)} rebalance dates')

        ic = ic_analysis(df_all, weights)
        print(f'\n  IC Analysis ({ic["n_periods"]} periods):')
        print(f'    Mean IC:       {ic["mean_ic"]:+.4f} (std {ic["std_ic"]:.4f})')
        print(f'    Mean Spread:   {ic["mean_spread_pp"]:+.2f} pp')
        print(f'    % Positive IC: {ic["pct_positive_ic"]:.0f}%')

        try:
            summary = run_engine(snapshots, label, prices)
            results[label] = {**summary, **ic}

            print(f'\n  Portfolio Performance:')
            print(f'    Total Return:   {summary["total_return_pct"]:+.2f}%')
            print(f'    CAGR:           {summary["cagr_pct"]:+.2f}%')
            print(f'    Sharpe:         {summary["sharpe"]:.2f}')
            print(f'    Sortino:        {summary["sortino"]:.2f}')
            print(f'    Max Drawdown:   {summary["max_drawdown_pct"]:.2f}%')
            print(f'    Win Rate:       {summary["trades_win_rate_pct"]:.1f}%')
            print(f'    Profit Factor:  {summary["profit_factor"]:.2f}')
            print(f'    Trades:         {summary["trades_total"]}')
            if summary.get('excess_return_pct') is not None:
                print(f'    Excess vs Nifty:{summary["excess_return_pct"]:+.2f}%')
        except Exception as e:
            logging.error(f'  ENGINE ERROR: {e}')
            import traceback; traceback.print_exc()
            results[label] = ic

    print('\n\n' + '=' * 80)
    print(f'FINAL COMPARISON ({START} -> {END})')
    print('=' * 80)

    metrics = ['total_return_pct', 'cagr_pct', 'sharpe', 'sortino',
               'max_drawdown_pct', 'trades_win_rate_pct', 'profit_factor',
               'mean_ic', 'mean_spread_pp']

    header = f'{"Metric":<22} | {"v2_current":>14} | {"v2_fixed":>14} | {"v1_baseline":>14}'
    print(header)
    print('-' * len(header))

    for m in metrics:
        row = f'{m:<22}'
        for label in WEIGHT_SETS:
            val = results.get(label, {}).get(m)
            if val is not None:
                row += f' | {val:>14.2f}'
            else:
                row += f' | {"N/A":>14}'
        print(row)

    winner = max(results.items(),
                 key=lambda x: x[1].get('sharpe', 0))
    print(f'\nBest risk-adjusted: {winner[0]} (Sharpe {winner[1].get("sharpe", 0):.2f})')

    out = REPO / 'data' / 'weight_comparison_backtest_long.json'
    with open(out, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f'Results saved to {out}')


if __name__ == '__main__':
    main()
