#!/usr/bin/env python3
"""Turbo MTF cadence backtest — live-proxy vs original assumptions.

Compares:
  - original: fixed Turbo weights + rank selection (prior cadence JSON)
  - live_proxy: regime-conditional v2 weights + threshold (BUY gate) selection

Weekly vs biweekly rebalance on the same N200 snapshot window.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backtest.cooldown import CooldownPolicy, resolve_policy
from backtest.data.path1_loader import DateSnapshot, _synthesise_v2_score
from backtest.data.prices import PriceCache
from backtest.engine import BacktestEngine, EngineConfig
from backtest.metrics import summarize
from config import get_config

COOLDOWN_VARIANTS = (
    ('off', resolve_policy('off')),
    ('prod_5d', resolve_policy('prod_5d')),
)

logging.basicConfig(level=logging.WARNING)

DEFAULT_CAPITAL = 1_000_000.0  # ₹10L — matches live book scale
TURBO_FIXED = get_config().DUAL_STRATEGY_PROFILES['turbo_mtf']['weights']


def biweekly_rebalance_dates(all_dates: list[date]) -> list[date]:
    df = pd.DataFrame({'d': pd.to_datetime(all_dates)})
    df['iso_week'] = df['d'].dt.isocalendar().week
    df['iso_year'] = df['d'].dt.isocalendar().year
    weekly = df.groupby(['iso_year', 'iso_week'])['d'].min().tolist()
    return [d.date() for i, d in enumerate(weekly) if i % 2 == 0]


def load_snapshots() -> pd.DataFrame:
    cache_dir = REPO / 'backtest' / 'cache' / 'scores'
    for p in sorted(cache_dir.glob('snapshots_*_long.pkl'), reverse=True):
        return pd.read_pickle(p).assign(date=lambda d: pd.to_datetime(d['date']))
    for p in sorted(cache_dir.glob('snapshots_*.pkl'), reverse=True):
        return pd.read_pickle(p).assign(date=lambda d: pd.to_datetime(d['date']))
    raise FileNotFoundError('No cached snapshots')


def load_regime_weights() -> dict[str, dict]:
    weights: dict[str, dict] = {}
    for regime in ('BULL', 'BEAR', 'SIDEWAYS'):
        path = REPO / 'data' / f'calibrated_weights_v2_{regime}.json'
        with open(path, encoding='utf-8') as f:
            weights[regime] = json.load(f)['weights']
    return weights


def infer_regime_by_date(dates: list[date]) -> dict[date, str]:
    """Point-in-time NIFTY regime labels for snapshot dates."""
    if not dates:
        return {}
    start = min(dates) - timedelta(days=400)
    end = max(dates) + timedelta(days=5)
    hist = yf.Ticker('^NSEI').history(start=start.isoformat(), end=end.isoformat())
    if hist is None or hist.empty:
        return {d: 'SIDEWAYS' for d in dates}
    close = hist['Close'].dropna()
    close.index = pd.to_datetime(close.index).tz_localize(None)

    regimes: dict[date, str] = {}
    for d in sorted(set(dates)):
        sub = close.loc[:pd.Timestamp(d)]
        if len(sub) < 200:
            regimes[d] = 'SIDEWAYS'
            continue
        cur = float(sub.iloc[-1])
        ma50 = float(sub.tail(50).mean())
        ma200 = float(sub.tail(200).mean())
        ret_3m = (cur / float(sub.iloc[-63]) - 1.0) if len(sub) >= 63 else 0.0
        if cur > ma200 and ma50 > ma200 and ret_3m > 0.03:
            regimes[d] = 'BULL'
        elif cur < ma200 and ret_3m < -0.03:
            regimes[d] = 'BEAR'
        else:
            regimes[d] = 'SIDEWAYS'
    return regimes


def rescore_fixed(df_all: pd.DataFrame, weights: dict) -> list[DateSnapshot]:
    df = df_all.copy()
    df['score_engine'] = _synthesise_v2_score(df, weights)
    valid = df.dropna(subset=['score_engine', 'current_price'])
    return [
        DateSnapshot(
            decision_date=d.date() if hasattr(d, 'date') else d,
            df=grp.reset_index(drop=True),
        )
        for d, grp in valid.groupby('date')
    ]


def rescore_regime_conditional(
    df_all: pd.DataFrame,
    regime_by_date: dict[date, str],
    regime_weights: dict[str, dict],
    fallback: dict,
) -> list[DateSnapshot]:
    df = df_all.copy()
    df['_regime'] = pd.to_datetime(df['date']).dt.date.map(regime_by_date).fillna('SIDEWAYS')
    scores = pd.Series(index=df.index, dtype='float64')
    for regime, weights in regime_weights.items():
        mask = df['_regime'] == regime
        if mask.any():
            scores.loc[mask] = _synthesise_v2_score(df.loc[mask], weights)
    missing = scores.isna()
    if missing.any():
        scores.loc[missing] = _synthesise_v2_score(df.loc[missing], fallback)
    df['score_engine'] = scores
    df['regime'] = df['_regime']
    valid = df.dropna(subset=['score_engine', 'current_price'])
    return [
        DateSnapshot(
            decision_date=d.date() if hasattr(d, 'date') else d,
            df=grp.reset_index(drop=True),
        )
        for d, grp in valid.groupby('date')
    ]


def filter_biweekly_snapshots(snapshots: list[DateSnapshot]) -> list[DateSnapshot]:
    dates = sorted({s.decision_date for s in snapshots})
    bi_dates = set(biweekly_rebalance_dates(dates))
    return [s for s in snapshots if s.decision_date in bi_dates]


def run_bt(
    snapshots: list[DateSnapshot],
    label: str,
    prices: PriceCache,
    rebalance: str,
    selection_mode: str,
    initial_capital: float,
    cooldown_policy: CooldownPolicy,
    biweekly_snapshot_mode: bool = False,
):
    if biweekly_snapshot_mode:
        snapshots = filter_biweekly_snapshots(snapshots)
        rebalance = 'weekly'

    cfg = EngineConfig(
        initial_capital=initial_capital,
        target_positions=10,
        max_positions=15,
        sector_cap_pct=30.0,
        rebalance=rebalance,
        selection_mode=selection_mode,
        min_entry_score=45.0,
        cooldown_policy=cooldown_policy,
        daily_exit_checks=True,
        momentum_exhaustion_enabled=True,
    )
    engine = BacktestEngine(engine_label=label, cfg=cfg, price_cache=prices)
    return engine.run(snapshots), cfg


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--capital', type=float, default=DEFAULT_CAPITAL,
        help='Initial capital in INR (default: 1000000 = ₹10L)',
    )
    args = parser.parse_args()
    initial_capital = args.capital
    df_all = load_snapshots()
    dates = [d.date() if hasattr(d, 'date') else d for d in df_all['date'].unique()]
    regime_by_date = infer_regime_by_date(dates)
    regime_weights = load_regime_weights()
    prices = PriceCache(refresh_days=1)

    regime_counts = pd.Series(regime_by_date.values()).value_counts().to_dict()

    long_pkls = sorted((REPO / 'backtest' / 'cache' / 'scores').glob('snapshots_*_long.pkl'))
    meta = {
        'initial_capital': initial_capital,
        'snapshot_file': long_pkls[-1].name if long_pkls else 'snapshots_*.pkl',
        'date_range': {
            'start': str(df_all['date'].min().date()),
            'end': str(df_all['date'].max().date()),
        },
        'weekly_snapshots': int(df_all['date'].nunique()),
        'symbols': int(df_all['symbol'].nunique()),
        'biweekly_method': 'subsample every-other ISO week snapshots (matches turbo_mtf_cadence_comparison.json)',
        'regime_inference': 'NIFTY point-in-time (MA50/MA200 + 3m return)',
        'regime_counts_by_date': regime_counts,
        'selection_modes': {
            'original': 'rank (min score 45)',
            'live_proxy': 'threshold (BUY >= 60 / STRONG_BUY >= 70)',
        },
        'weights': {
            'original': TURBO_FIXED,
            'live_proxy': regime_weights,
        },
        'cooldown_policies': {
            name: {
                'enabled': pol.enabled,
                'cooldown_days': pol.cooldown_days,
                'profit_bypass_pct': pol.profit_bypass_pct,
            }
            for name, pol in COOLDOWN_VARIANTS
        },
        'scenario_key_format': '<base>__<cooldown>',
        'daily_exit_checks': True,
        'momentum_exhaustion_enabled': True,
    }

    scenarios = [
        ('original_fixed_rank_weekly', TURBO_FIXED, 'rank', 'weekly', False, False),
        ('original_fixed_rank_biweekly', TURBO_FIXED, 'rank', 'weekly', False, True),
        ('live_regime_threshold_weekly', None, 'threshold', 'weekly', True, False),
        ('live_regime_threshold_biweekly', None, 'threshold', 'weekly', True, True),
    ]

    results: dict[str, dict] = {'meta': meta}
    trades_dir = REPO / 'data' / 'turbo_mtf_cadence_trades'
    trades_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}

    for key, fixed_w, sel_mode, rebalance, regime_cond, biweekly_snaps in scenarios:
        if regime_cond:
            snaps = rescore_regime_conditional(
                df_all, regime_by_date, regime_weights, TURBO_FIXED,
            )
        else:
            snaps = rescore_fixed(df_all, fixed_w)
        for cd_name, cd_policy in COOLDOWN_VARIANTS:
            run_key = f'{key}__{cd_name}'
            print(f'Running {run_key} ...', flush=True)
            result, cfg = run_bt(
                snaps, run_key, prices, rebalance, sel_mode, initial_capital,
                cooldown_policy=cd_policy,
                biweekly_snapshot_mode=biweekly_snaps,
            )
            summary = summarize(
                result.equity_curve,
                result.trades,
                cfg.initial_capital,
                benchmark=result.benchmark_curve,
            )
            summary['open_positions'] = len(result.final_positions)
            summary['cooldown_policy'] = cd_name
            summary['cooldown_suppressions'] = result.summary.get(
                'cooldown_suppressions', 0,
            )
            results[run_key] = summary
            print(
                f'  {run_key}: Ret={summary["total_return_pct"]:+.1f}% '
                f'Final=₹{summary["final_equity"]:,.0f} '
                f'Sharpe={summary["sharpe"]:.2f} '
                f'DD={summary["max_drawdown_pct"]:.1f}% '
                f'Trades={summary["trades_total"]} '
                f'CD-block={summary["cooldown_suppressions"]}',
                flush=True,
            )
            trades_df = pd.DataFrame(result.trades) if result.trades else pd.DataFrame()
            csv_path = trades_dir / f'{run_key}_trades.csv'
            trades_df.to_csv(csv_path, index=False)
            wins = int((trades_df['net_pl'] > 0).sum()) if not trades_df.empty else 0
            manifest[run_key] = {
                'file': str(csv_path.relative_to(REPO)),
                'trades': len(trades_df),
                'wins': wins,
                'total_net_pl': round(float(trades_df['net_pl'].sum()), 2) if not trades_df.empty else 0,
                'open_positions': len(result.final_positions),
                'cooldown_suppressions': summary['cooldown_suppressions'],
            }

    with open(trades_dir / 'manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    out = REPO / 'data' / 'turbo_mtf_cadence_comparison_live.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, default=str)
    print(f'\nSaved {out}', flush=True)


if __name__ == '__main__':
    main()
