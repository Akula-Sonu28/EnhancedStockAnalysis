#!/usr/bin/env python3
"""Head-to-head strategy arena on identical Nifty 200 / monthly / ₹10L / costs.

Compares chat strategies (LowVol→Mom, RSI>60, regime switch) plus v2 weight
blends from backtest_strategy_explorer.STRATEGIES on the same window.

Usage:
    python3 scripts/strategy_arena.py --months 120
    python3 scripts/strategy_arena.py --months 60 --skip-v2
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from backtest.data.indicators import build_stock_data, rsi_14
from backtest.data.path1_loader import DateSnapshot, _synthesise_v2_score, first_sector_lookup
from backtest.data.path2_rescore import Path2Rescorer, _regime_at_date
from backtest.data.prices import PriceCache
from backtest.engine import BacktestEngine, EngineConfig
from backtest.lvm_strategy import LVMStrategyAdapter
from backtest.metrics import summarize
from scripts.backtest_strategy_explorer import STRATEGIES as V2_STRATEGIES

logging.basicConfig(level=logging.INFO, format='[arena] %(message)s')

LVM_CACHE = REPO / 'backtest' / 'cache' / 'lvm_snapshots' / 'lvm_{start}_{end}_monthly_n200_12m.pkl'
ENRICHED_CACHE = REPO / 'backtest' / 'cache' / 'lvm_snapshots' / 'arena_panel_enriched.pkl'
OUT_JSON = REPO / 'data' / 'strategy_arena_results.json'

TOP_N = 10
POOL = 40
SECTOR_CAP = 3


def _pick_top_n(
    pool: pd.DataFrame,
    rank_col: str,
    top_n: int = TOP_N,
    sector_cap: int = SECTOR_CAP,
    ascending: bool = False,
) -> pd.Index:
    """Sector-capped top-N by rank_col (same logic as lowvol_momentum)."""
    if pool.empty:
        return pd.Index([])
    pool = pool.copy()
    pool['_rk'] = pool[rank_col].rank(ascending=ascending, method='min')
    pool = pool.sort_values('_rk', ascending=ascending)
    keep: List = []
    counts: Dict[str, int] = {}
    for idx in pool.index:
        sec = str(pool.at[idx, 'sector'])
        counts.setdefault(sec, 0)
        if counts[sec] >= sector_cap:
            continue
        keep.append(idx)
        counts[sec] += 1
        if len(keep) >= top_n:
            break
    return pd.Index(keep)


def _apply_picks(g: pd.DataFrame, eligible, rank) -> pd.DataFrame:
    out = g.copy()
    if not isinstance(eligible, pd.Series):
        eligible = pd.Series(eligible, index=out.index)
    if not isinstance(rank, pd.Series):
        rank = pd.Series(rank, index=out.index)
    out['pick_eligible'] = eligible.fillna(False).astype(bool)
    out['pick_rank'] = pd.to_numeric(rank, errors='coerce').fillna(-9999.0)
    out.loc[~out['pick_eligible'], 'pick_rank'] = -9999.0
    return out


def _lowvol_mom_picks(g: pd.DataFrame) -> pd.DataFrame:
    from config import get_config
    from src.lowvol_momentum import compute_lowvol_mom_score

    out = compute_lowvol_mom_score(g, get_config())
    return _apply_picks(
        out,
        out['lowvol_mom_eligible'].fillna(False),
        out['lowvol_mom_score'].fillna(0),
    )


def _mom_sma50_picks(g: pd.DataFrame) -> pd.DataFrame:
    above = g['current_price'] >= g['legacy_sma_50']
    pool = g[above & g['price_change_1y'].between(-500, 500)]
    idx = _pick_top_n(pool, 'price_change_1y', ascending=False)
    elig = g.index.isin(idx)
    rank = g['price_change_1y'].fillna(-999)
    return _apply_picks(g, elig, rank)


def _rsi60_picks(g: pd.DataFrame) -> pd.DataFrame:
    above = g['current_price'] >= g['legacy_sma_50']
    pool = g[above & (g['rsi_14'] > 60)]
    idx = _pick_top_n(pool, 'price_change_1y', ascending=False)
    elig = g.index.isin(idx)
    rank = g['price_change_1y'].fillna(-999)
    return _apply_picks(g, elig, rank)


def _low_vol_only_picks(g: pd.DataFrame) -> pd.DataFrame:
    above = g['current_price'] >= g['legacy_sma_50']
    sub = g[above].nsmallest(POOL, 'volatility_6m')
    idx = _pick_top_n(sub, 'volatility_6m', ascending=True)
    elig = g.index.isin(idx)
    rank = -g['volatility_6m'].fillna(999)
    return _apply_picks(g, elig, rank)


def _pure_mom_picks(g: pd.DataFrame) -> pd.DataFrame:
    pool = g[g['price_change_1y'].between(-500, 500)]
    idx = _pick_top_n(pool, 'price_change_1y', ascending=False)
    elig = g.index.isin(idx)
    return _apply_picks(g, elig, g['price_change_1y'])


def _risk_adj_mom_picks(g: pd.DataFrame) -> pd.DataFrame:
    """Momentum / volatility (Sharpe-like rank)."""
    vol = g['volatility_6m'].replace(0, np.nan)
    g = g.copy()
    g['_ram'] = g['price_change_1y'] / vol
    pool = g[g['current_price'] >= g['legacy_sma_50']]
    idx = _pick_top_n(pool, '_ram', ascending=False)
    elig = g.index.isin(idx)
    return _apply_picks(g, elig, g['_ram'].fillna(-999))


def _regime_switch_picks(g: pd.DataFrame) -> pd.DataFrame:
    regime = str(g['regime'].iloc[0]) if 'regime' in g.columns else 'SIDEWAYS'
    if regime in ('BULL', 'BEARISH', 'BEAR'):
        return _lowvol_mom_picks(g)
    if regime == 'SIDEWAYS':
        return _rsi60_picks(g)
    return _lowvol_mom_picks(g)


CHAT_STRATEGIES: Dict[str, Callable[[pd.DataFrame], pd.DataFrame]] = {
    'lowvol_mom': _lowvol_mom_picks,
    'rsi60_only': _rsi60_picks,
    'mom_sma50_top10': _mom_sma50_picks,
    'low_vol_only': _low_vol_only_picks,
    'pure_momentum_top10': _pure_mom_picks,
    'risk_adj_momentum': _risk_adj_mom_picks,
    'regime_switch': _regime_switch_picks,
}


def load_lvm_panel(start: date, end: date) -> pd.DataFrame:
    path = Path(str(LVM_CACHE).format(start=start, end=end))
    if not path.exists():
        from backtest.lvm_snapshot_builder import LvmSnapshotBuilder

        logging.info('Building LVM panel %s -> %s (first run, slow)', start, end)
        b = LvmSnapshotBuilder(vol_mode='12m')
        b.warmup_prices(start, end)
        snaps = b.build_snapshots(start, end, cadence='monthly')
        frames = [s.df.assign(date=pd.Timestamp(s.decision_date)) for s in snaps]
        panel = pd.concat(frames, ignore_index=True)
        panel.to_pickle(path)
    else:
        panel = pd.read_pickle(path)
    panel['date'] = pd.to_datetime(panel['date'])
    return panel


def enrich_panel(panel: pd.DataFrame, prices: PriceCache) -> pd.DataFrame:
    if ENRICHED_CACHE.exists():
        logging.info('Loading enriched panel cache')
        out = pd.read_pickle(ENRICHED_CACHE)
        out['date'] = pd.to_datetime(out['date'])
        return out

    nifty = prices.get('^NSEI', panel['date'].min().date() - timedelta(days=400),
                       panel['date'].max().date() + timedelta(days=2))
    nifty_close = nifty['Close'].astype(float) if not nifty.empty else pd.Series(dtype=float)

    parts = []
    dates = sorted(panel['date'].unique())
    t0 = time.time()
    for i, d in enumerate(dates):
        grp = panel[panel['date'] == d].copy()
        rsis = []
        regimes = []
        for _, row in grp.iterrows():
            sym = str(row['symbol'])
            ohlcv = prices.get(sym, pd.Timestamp(d).date() - timedelta(days=400),
                               pd.Timestamp(d).date() + timedelta(days=2))
            if ohlcv.empty or len(ohlcv) < 60:
                rsis.append(50.0)
                continue
            cutoff = pd.Timestamp(d)
            sub = ohlcv[ohlcv.index <= cutoff]
            rsis.append(rsi_14(sub['Close'].astype(float)))
        reg = _regime_at_date(nifty, pd.Timestamp(d).date())
        grp['rsi_14'] = rsis
        grp['regime'] = reg
        parts.append(grp)
        if (i + 1) % 20 == 0 or i == len(dates) - 1:
            logging.info('Enriched %d/%d dates (%.0fs)', i + 1, len(dates), time.time() - t0)

    out = pd.concat(parts, ignore_index=True)
    out.to_pickle(ENRICHED_CACHE)
    return out


def panel_to_snapshots(panel: pd.DataFrame, pick_fn: Callable) -> List[DateSnapshot]:
    snaps = []
    for d, grp in panel.groupby('date'):
        g = pick_fn(grp.copy())
        if g['pick_eligible'].sum() == 0:
            continue
        snaps.append(DateSnapshot(decision_date=pd.Timestamp(d).date(), df=g.reset_index(drop=True)))
    return snaps


def _top10_eligible(g: pd.DataFrame, rank_col: str = 'pick_rank') -> pd.DataFrame:
    g = g.copy()
    g['pick_eligible'] = False
    idx = _pick_top_n(g, rank_col, ascending=False)
    g.loc[idx, 'pick_eligible'] = True
    return g


def run_backtest(
    snapshots: List[DateSnapshot],
    label: str,
    prices: PriceCache,
    capital: float,
    stop_pct: float,
) -> dict:
    cfg = EngineConfig(
        initial_capital=capital,
        target_positions=TOP_N,
        max_positions=TOP_N + 5,
        rebalance='monthly',
        selection_mode='rank',
        apply_min_entry_score=False,
        allow_rotation=False,
        rank_column='pick_rank',
        lvm_eligible_column='pick_eligible',
        lvm_full_rebalance=True,
        momentum_exhaustion_enabled=False,
    )
    strategy = LVMStrategyAdapter(stop_pct=stop_pct)
    engine = BacktestEngine(engine_label=label, cfg=cfg, strategy=strategy, price_cache=prices)
    result = engine.run(snapshots)
    summary = summarize(
        result.equity_curve,
        result.trades,
        capital,
        benchmark=result.benchmark_curve,
    )
    summary['strategy'] = label
    summary['start_date'] = str(result.start_date)
    summary['end_date'] = str(result.end_date)
    research = [
        ('Jul23-Jun24', '2023-07-01', '2024-06-30'),
        ('Jan24-Jun24', '2024-01-01', '2024-06-30'),
        ('Jul24-May26', '2024-07-01', '2026-05-31'),
        ('Jan25-May26', '2025-01-01', '2026-05-31'),
    ]
    wins = 0
    for _, s, e in research:
        ts, te = pd.Timestamp(s), pd.Timestamp(e)
        sub = result.equity_curve.loc[(result.equity_curve.index >= ts) & (result.equity_curve.index <= te)]
        if len(sub) < 2 or result.benchmark_curve is None:
            continue
        bsub = result.benchmark_curve.reindex(sub.index).ffill()
        ret = (sub.iloc[-1] / sub.iloc[0] - 1) * 100
        bret = (bsub.iloc[-1] / bsub.iloc[0] - 1) * 100 if len(bsub.dropna()) >= 2 else 0
        if ret > bret:
            wins += 1
    summary['beat_nifty_4p'] = wins
    return summary


def _apply_value_trap_filter(df: pd.DataFrame, d) -> pd.DataFrame:
    """Remove stocks with negative equity or interest coverage < 1.5."""
    from backtest.data.fundamentals_pit import get_fundamental_lookup
    fl = get_fundamental_lookup()
    as_of = pd.Timestamp(d).date() if hasattr(d, 'date') and callable(d.date) else d
    if not isinstance(as_of, date):
        as_of = pd.Timestamp(as_of).date()
    mask = []
    for _, row in df.iterrows():
        sym = str(row.get('symbol', ''))
        price = float(row.get('current_price', 0))
        is_trap = fl.is_value_trap(sym, as_of, price)
        mask.append(not is_trap)
    return df[mask].copy()


def _nifty_below_sma200(prices: PriceCache, d) -> bool:
    """True if Nifty 50 close on date d is below its 200-day SMA."""
    if not isinstance(d, date) or hasattr(d, 'hour'):
        d = pd.Timestamp(d).date()
    nifty = prices.get('^NSEI', d - timedelta(days=300), d + timedelta(days=2))
    if nifty.empty or len(nifty) < 200:
        return False
    cutoff = pd.Timestamp(d)
    sub = nifty[nifty.index <= cutoff]
    if len(sub) < 200:
        return False
    close = float(sub['Close'].iloc[-1])
    sma200 = float(sub['Close'].iloc[-200:].mean())
    return close < sma200


def run_v2_strategies(
    start: date,
    end: date,
    prices: PriceCache,
    capital: float,
    stop_pct: float,
    value_trap_filter: bool = False,
    regime_gate: bool = False,
) -> List[dict]:
    logging.info('Building Path2 hybrid snapshots for v2 weight strategies (PIT fundamentals)...')
    rescorer = Path2Rescorer(use_pit_fundamentals=True)
    raw = rescorer.build_snapshots(start, end, cadence='monthly', use_cache=True)
    df_all = pd.concat(
        [s.df.assign(date=pd.Timestamp(s.decision_date)) for s in raw],
        ignore_index=True,
    )
    sec_map = first_sector_lookup()
    df_all['sector'] = df_all['symbol'].astype(str).map(lambda s: sec_map.get(s, 'Unknown'))
    rows = []
    for label, weights in V2_STRATEGIES.items():
        try:
            df = df_all.copy()
            df['pick_rank'] = _synthesise_v2_score(df, weights)
            valid = df.dropna(subset=['pick_rank', 'current_price'])
            frames = []
            for d, grp in valid.groupby('date'):
                g = grp.copy()
                if value_trap_filter:
                    g = _apply_value_trap_filter(g, d)
                d_date = pd.Timestamp(d).date()
                if regime_gate and _nifty_below_sma200(prices, d_date):
                    g = g.head(0)
                frames.append(_top10_eligible(g))
            if not frames:
                continue
            snaps = [
                DateSnapshot(decision_date=pd.Timestamp(d).date(), df=grp.reset_index(drop=True))
                for d, grp in pd.concat(frames).groupby('date')
            ]
            s = run_backtest(snaps, f'v2_{label}', prices, capital, stop_pct)
            rows.append(s)
            logging.info('  v2 %-22s CAGR %+.1f%%  MaxDD %+.1f%%',
                         label, s['cagr_pct'], s['max_drawdown_pct'])
        except Exception as e:
            import traceback
            logging.warning('  v2 %s failed: %s\n%s', label, e, traceback.format_exc())
    return rows


def period_beats(equity_path: Path, periods: List[Tuple[str, str, str]]) -> Dict[str, dict]:
    eq = pd.read_csv(equity_path, parse_dates=[0], index_col=0).sort_index()
    out = {}
    for name, s, e in periods:
        sub = eq.loc[(eq.index >= s) & (eq.index <= e)]
        if len(sub) < 2:
            continue
        lvm = (sub.iloc[-1]['equity'] / sub.iloc[0]['equity'] - 1) * 100
        nif = (sub.iloc[-1]['benchmark'] / sub.iloc[0]['benchmark'] - 1) * 100
        out[name] = {'lvm': lvm, 'nifty': nif, 'beat': lvm > nif}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description='Strategy head-to-head arena')
    ap.add_argument('--months', type=int, default=120)
    ap.add_argument('--capital', type=float, default=1_000_000.0)
    ap.add_argument('--stop-pct', type=float, default=10.0)
    ap.add_argument('--skip-v2', action='store_true', help='Skip 20 v2 weight strategies')
    ap.add_argument('--v2-only', action='store_true', help='Only run v2 weight strategies')
    ap.add_argument('--rebuild-enriched', action='store_true')
    ap.add_argument('--test-only', action='store_true',
                    help='Run only on test set (second half of window) for train/test validation')
    ap.add_argument('--regime-gate', action='store_true',
                    help='Enable regime circuit breaker (skip buys when Nifty < SMA200)')
    ap.add_argument('--value-trap-filter', action='store_true',
                    help='Filter out value traps (negative equity or interest coverage < 1.5)')
    args = ap.parse_args()

    end = date.today()
    start = end - timedelta(days=int(args.months * 30.5))
    if args.test_only:
        mid = start + (end - start) / 2
        logging.info('TRAIN/TEST mode: test set only %s -> %s (train was %s -> %s)',
                     mid, end, start, mid)
        start = mid

    if args.rebuild_enriched and ENRICHED_CACHE.exists():
        ENRICHED_CACHE.unlink()

    prices = PriceCache(refresh_days=9999)
    panel = load_lvm_panel(start, end)
    panel = enrich_panel(panel, prices)

    results: List[dict] = []
    t0 = time.time()

    if not args.v2_only:
        for name, pick_fn in CHAT_STRATEGIES.items():
            snaps = panel_to_snapshots(panel, pick_fn)
            if not snaps:
                logging.warning('No snapshots for %s', name)
                continue
            s = run_backtest(snaps, name, prices, args.capital, args.stop_pct)
            results.append(s)
            logging.info('  %-22s CAGR %+.1f%%  Sharpe %+.2f  MaxDD %+.1f%%  vs Nifty %+.1fpp',
                         name, s['cagr_pct'], s.get('sharpe', 0),
                         s['max_drawdown_pct'], s.get('excess_return_pct', 0))

    if args.v2_only and OUT_JSON.exists():
        results = json.loads(OUT_JSON.read_text())

    if not args.skip_v2:
        results.extend(run_v2_strategies(
            start, end, prices, args.capital, args.stop_pct,
            value_trap_filter=args.value_trap_filter,
            regime_gate=args.regime_gate,
        ))

    df = pd.DataFrame(results)
    df = df.sort_values('cagr_pct', ascending=False)

    print('\n' + '=' * 100)
    print(f'STRATEGY ARENA — {start} -> {end}  |  ₹{args.capital:,.0f}  |  monthly Top-{TOP_N}')
    print('=' * 100)
    cols = ['strategy', 'cagr_pct', 'total_return_pct', 'sharpe', 'max_drawdown_pct',
              'excess_return_pct', 'beat_nifty_4p', 'trades_total', 'profit_factor']
    cols = [c for c in cols if c in df.columns]
    print(df[cols].head(35).to_string(index=False, float_format=lambda x: f'{x:,.2f}'))

    print('\n--- Beat Nifty count (4 research windows) — top 15 ---')
    if 'beat_nifty_4p' in df.columns:
        top_beat = df.nlargest(15, 'beat_nifty_4p')[['strategy', 'beat_nifty_4p', 'cagr_pct']]
        print(top_beat.to_string(index=False))

    if not args.skip_v2 and not args.v2_only:
        _print_ic_report(start, end, prices)

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(results, indent=2, default=str))
    print(f'\nSaved {OUT_JSON}')
    print(f'Elapsed {time.time()-t0:.0f}s')
    return 0


def _print_ic_report(start: date, end: date, prices: PriceCache):
    """Cross-sectional IC of mean_reversion score vs 30-day forward return."""
    from scipy import stats as sp_stats

    logging.info('Computing walk-forward IC for mean_reversion...')
    rescorer = Path2Rescorer(use_pit_fundamentals=True)
    raw = rescorer.build_snapshots(start, end, cadence='monthly', use_cache=True)

    MR_W = V2_STRATEGIES.get('mean_reversion')
    if not MR_W or not raw:
        return

    ics = []
    for snap in raw:
        df = snap.df.copy()
        df['mr_score'] = _synthesise_v2_score(df, MR_W)
        fwd = []
        for _, r in df.iterrows():
            sym = str(r['symbol'])
            p0 = float(r.get('current_price', 0))
            if p0 <= 0:
                fwd.append(np.nan)
                continue
            ohlcv = prices.get(sym,
                               snap.decision_date + timedelta(days=1),
                               snap.decision_date + timedelta(days=35))
            if ohlcv is None or ohlcv.empty:
                fwd.append(np.nan)
                continue
            p1 = float(ohlcv['Close'].iloc[-1])
            fwd.append((p1 / p0 - 1) * 100)
        df['fwd_30d'] = fwd
        valid = df.dropna(subset=['mr_score', 'fwd_30d'])
        if len(valid) < 20:
            continue
        ic, _ = sp_stats.spearmanr(valid['mr_score'], valid['fwd_30d'])
        ics.append(ic)

    if not ics:
        print('\n--- IC: no valid periods ---')
        return

    ic_arr = np.array(ics)
    print(f'\n--- Walk-forward IC: mean_reversion score vs 30d fwd return ---')
    print(f'  Periods:  {len(ic_arr)}')
    print(f'  Mean IC:  {ic_arr.mean():.4f}')
    print(f'  Median:   {np.median(ic_arr):.4f}')
    print(f'  Std:      {ic_arr.std():.4f}')
    print(f'  IC > 0:   {(ic_arr > 0).sum()}/{len(ic_arr)} ({100*(ic_arr>0).mean():.0f}%)')
    print(f'  IC >= 0.05: {(ic_arr >= 0.05).sum()}/{len(ic_arr)}')
    print(f'  ICIR:     {ic_arr.mean()/ic_arr.std():.3f}' if ic_arr.std() > 0 else '  ICIR: n/a')


if __name__ == '__main__':
    sys.exit(main())
