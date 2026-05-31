"""Path 2 re-scorer: produce DateSnapshots for any historical window using
OHLCV-only inputs (no point-in-time fundamentals needed).

Justified by the live v2 weights: only momentum_technical, volume_strength,
multi_timeframe, ml_signal, and risk_adjustment have non-zero weight, and
fundamentals/growth/value have ZERO weight. Of the non-zero set:
    - momentum_technical, volume_strength, multi_timeframe, risk_adjustment
      are 100% computable from daily OHLCV.
    - ml_signal: no historical model available → suppressed (returns 50).
      Effective contribution = weight * (50-50) = 0. This is the only true
      compromise vs. the live engine.

Universe: today's Nifty 200 from `stock_list_template.csv` (survivorship-
biased — companies that delisted/merged within the window are absent).

OHLCV: yfinance via backtest.data.prices.PriceCache (cached locally).

Output: same DateSnapshot shape as Path1Loader, so the engine code is
identical.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterator, Optional

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from hybrid_optimized_scoring import HybridOptimizedScoringEngine  # noqa: E402

from .indicators import build_stock_data
from .path1_loader import (
    DateSnapshot, COMPONENT_TO_WEIGHT_KEY, _synthesise_v2_score,
)
from .prices import PriceCache, warmup


UNIVERSE_PATH = REPO_ROOT / 'stock_list_template.csv'
V2_WEIGHTS = REPO_ROOT / 'data' / 'calibrated_weights_v2.json'
CACHE_DIR = REPO_ROOT / 'backtest' / 'cache' / 'scores'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _load_universe(path: Path = UNIVERSE_PATH) -> list[str]:
    df = pd.read_csv(path)
    col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
    return [str(s).strip() for s in df[col].dropna().tolist()]


def _trading_dates(prices: PriceCache, anchor: str, start: date, end: date) -> list[date]:
    """Get the trading-day calendar from one liquid symbol (default RELIANCE)."""
    df = prices.get(anchor, start - timedelta(days=10), end + timedelta(days=2))
    if df.empty:
        return []
    dates = [d.date() for d in df.index if start <= d.date() <= end]
    return sorted(set(dates))


def _rebalance_dates(all_trading: list[date], cadence: str) -> list[date]:
    """Pick rebalance decision dates from the trading calendar."""
    if not all_trading:
        return []
    if cadence == 'daily':
        return list(all_trading)
    if cadence == 'weekly':
        df = pd.DataFrame({'d': pd.to_datetime(all_trading)})
        df['key'] = df['d'].dt.isocalendar().year * 100 + df['d'].dt.isocalendar().week
        picks = df.groupby('key')['d'].min()
        return [p.date() for p in picks.tolist()]
    if cadence == 'monthly':
        df = pd.DataFrame({'d': pd.to_datetime(all_trading)})
        df['ym'] = df['d'].dt.to_period('M')
        picks = df.groupby('ym')['d'].min()
        return [p.date() for p in picks.tolist()]
    raise ValueError(f'unknown cadence: {cadence}')


def _load_v2_weights() -> dict:
    data = json.loads(V2_WEIGHTS.read_text())
    return data.get('weights') or {}


def _cache_key(start: date, end: date, cadence: str, universe_size: int) -> Path:
    return CACHE_DIR / f'snapshots_{start.isoformat()}_{end.isoformat()}_{cadence}_n{universe_size}_rg1.pkl'


def _regime_at_date(nifty_df: pd.DataFrame, d: date) -> str:
    """Historical regime label for backtest (BULL/BEAR/SIDEWAYS)."""
    if nifty_df is None or nifty_df.empty:
        return 'SIDEWAYS'
    sub = nifty_df[nifty_df.index <= pd.Timestamp(d)]
    if sub.empty or len(sub) < 50:
        return 'SIDEWAYS'
    from backtest_engine import BacktestEngine
    return BacktestEngine._detect_regime_from_data(sub)


class Path2Rescorer:
    """Build engine-ready DateSnapshots for any historical window."""

    def __init__(self, universe: Optional[list[str]] = None,
                 prices: Optional[PriceCache] = None,
                 weights: Optional[dict] = None,
                 nifty_symbol: str = '^NSEI'):
        self.universe = universe or _load_universe()
        self.prices = prices or PriceCache(refresh_days=1)
        self.weights = weights if weights is not None else _load_v2_weights()
        self.nifty_symbol = nifty_symbol
        self.engine = HybridOptimizedScoringEngine()

    def _component_scores(self, stock_data: dict) -> dict:
        """Compute all 8 v2 components (OHLCV + fundamentals where available)."""
        mom = self.engine.calculate_momentum_technical_score(stock_data)
        vol = self.engine.calculate_volume_strength_score(stock_data)
        mtf = self.engine.calculate_multi_timeframe_score(stock_data)
        risk = self.engine.calculate_risk_adjustment_score(stock_data)
        ml = self.engine.calculate_ml_signal_score(stock_data)
        fund = self.engine.calculate_fundamental_quality_score(stock_data)
        growth = self.engine.calculate_growth_score(stock_data)
        value = self.engine.calculate_value_score(stock_data)
        return {
            'hybrid_fundamental_quality': float(fund) if fund is not None else 50.0,
            'hybrid_growth':              float(growth) if growth is not None else 50.0,
            'hybrid_value':               float(value) if value is not None else 50.0,
            'hybrid_momentum_technical':  float(mom) if mom is not None else 50.0,
            'hybrid_volume_strength':     float(vol) if vol is not None else 50.0,
            'hybrid_multi_timeframe':     float(mtf) if mtf is not None else 50.0,
            'hybrid_ml_signal':           float(ml) if ml is not None else 50.0,
            'hybrid_risk_adjustment':     float(risk) if risk is not None else 50.0,
        }

    def _build_snapshot(self, d: date,
                        nifty_df: pd.DataFrame) -> Optional[pd.DataFrame]:
        nifty_close = nifty_df['Close'].astype(float) if not nifty_df.empty else pd.Series(dtype=float)
        regime = _regime_at_date(nifty_df, d)
        rows = []
        for sym in self.universe:
            df = self.prices.get(sym, d - timedelta(days=400), d + timedelta(days=2))
            if df.empty or len(df) < 60:
                continue
            sd = build_stock_data(sym, df, nifty_close, d)
            if sd is None:
                continue
            comps = self._component_scores(sd)
            rows.append({
                'date': pd.Timestamp(d),
                'symbol': sym,
                'current_price': sd['current_price'],
                'regime': regime,
                **comps,
            })
        if not rows:
            return None
        out = pd.DataFrame(rows)
        out['score_v2'] = _synthesise_v2_score(out, self.weights)
        # No v1 score available — leave blank
        out['score'] = np.nan
        return out

    def build_snapshots(self, start: date, end: date,
                        cadence: str = 'weekly',
                        use_cache: bool = True) -> list[DateSnapshot]:
        """Return DateSnapshots from scratch for a window. Cached on disk."""
        cache_path = _cache_key(start, end, cadence, len(self.universe))
        if use_cache and cache_path.exists():
            try:
                df_all = pd.read_pickle(cache_path)
                df_all['date'] = pd.to_datetime(df_all['date'])
                logging.info(f'[path2] loaded cached snapshots: {cache_path}')
                return self._slice_into_snapshots(df_all)
            except Exception as e:
                logging.warning(f'[path2] cache read failed: {e}')

        logging.info(f'[path2] building snapshots from scratch: '
                     f'{start} -> {end}, cadence={cadence}, '
                     f'universe={len(self.universe)}')
        anchor = 'RELIANCE' if 'RELIANCE' in self.universe else self.universe[0]
        trading = _trading_dates(self.prices, anchor, start, end)
        rebal = _rebalance_dates(trading, cadence)
        logging.info(f'[path2] {len(trading)} trading days, '
                     f'{len(rebal)} rebalance dates')

        nifty_df = self.prices.get(self.nifty_symbol,
                                    start - timedelta(days=400),
                                    end + timedelta(days=2))

        snapshot_frames = []
        t0 = time.time()
        for i, d in enumerate(rebal):
            snap_df = self._build_snapshot(d, nifty_df)
            if snap_df is None:
                continue
            snapshot_frames.append(snap_df)
            if (i + 1) % 5 == 0 or i == len(rebal) - 1:
                elapsed = time.time() - t0
                logging.info(f'[path2] {i+1}/{len(rebal)} rebalances scored '
                             f'({elapsed:.1f}s)')

        if not snapshot_frames:
            logging.warning('[path2] no snapshots built')
            return []

        df_all = pd.concat(snapshot_frames, ignore_index=True)
        try:
            df_all.to_pickle(cache_path)
            logging.info(f'[path2] cached snapshots: {cache_path}')
        except Exception as e:
            logging.warning(f'[path2] cache write failed: {e}')

        return self._slice_into_snapshots(df_all)

    def _slice_into_snapshots(self, df_all: pd.DataFrame) -> list[DateSnapshot]:
        out = []
        for d, grp in df_all.groupby('date'):
            grp = grp.dropna(subset=['score_v2', 'current_price'])
            if grp.empty:
                continue
            g = grp.copy()
            g['score_engine'] = g['score_v2']
            out.append(DateSnapshot(decision_date=d.date(), df=g.reset_index(drop=True)))
        return out

    # Universe warmup convenience
    def warmup_prices(self, start: date, end: date) -> dict[str, bool]:
        return warmup(self.universe + [self.nifty_symbol], start, end,
                      cache=self.prices, sleep_between=0.0)
