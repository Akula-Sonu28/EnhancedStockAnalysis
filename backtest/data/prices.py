"""OHLCV price cache.

Single responsibility: given (symbol, date) return the next-trading-day open
price (and other utilities). Backed by a local parquet/pickle cache that is
populated from yfinance on first access.

The cache key is per-symbol and stores a DataFrame indexed by date with
columns: Open, High, Low, Close, Volume, AdjClose. yfinance auto-adjusts for
splits and dividends; we keep both raw Close and AdjClose for transparency.
"""

from __future__ import annotations

import logging
import os
import pickle
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / 'backtest' / 'cache' / 'prices'
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _safe_filename(symbol: str) -> str:
    return symbol.replace('/', '_').replace('\\', '_')


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f'{_safe_filename(symbol)}.pkl'


def _yf_history(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Wrapper around yfinance with NSE suffix and graceful failure.

    Symbols starting with `^` (e.g. `^NSEI`) are indices and use no suffix.
    """
    import yfinance as yf
    ticker = symbol if symbol.startswith('^') else f'{symbol}.NS'
    try:
        df = yf.Ticker(ticker).history(
            start=start.isoformat(),
            end=(end + timedelta(days=1)).isoformat(),
            auto_adjust=False,
        )
    except Exception as e:
        logging.warning(f'[prices] yfinance failed for {symbol}: {e}')
        return pd.DataFrame()
    if df is None or df.empty:
        return pd.DataFrame()
    df = df.rename(columns={'Adj Close': 'AdjClose'})
    cols = ['Open', 'High', 'Low', 'Close', 'AdjClose', 'Volume']
    df = df[[c for c in cols if c in df.columns]].copy()
    df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
    return df


class PriceCache:
    """Per-symbol price cache. Lazy + persistent."""

    def __init__(self, cache_dir: Path = CACHE_DIR, refresh_days: int = 1):
        """
        Args:
            cache_dir: where pickled per-symbol frames live.
            refresh_days: if cache is older than this many days, refresh.
                Set very high (e.g. 9999) for fully offline runs.
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.refresh_days = refresh_days
        self._mem: dict[str, pd.DataFrame] = {}

    def _load_from_disk(self, symbol: str) -> Optional[pd.DataFrame]:
        p = _cache_path(symbol)
        if not p.exists():
            return None
        try:
            with open(p, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logging.warning(f'[prices] cache corrupt for {symbol}: {e}')
            try:
                p.unlink()
            except OSError:
                pass
            return None

    def _save_to_disk(self, symbol: str, df: pd.DataFrame) -> None:
        p = _cache_path(symbol)
        try:
            with open(p, 'wb') as f:
                pickle.dump(df, f)
        except Exception as e:
            logging.warning(f'[prices] cache write failed for {symbol}: {e}')

    def _is_fresh_enough(self, df: pd.DataFrame, end: date) -> bool:
        """Cache is fresh if it covers up to (end - refresh_days)."""
        if df is None or df.empty:
            return False
        last = df.index.max().date()
        return last >= end - timedelta(days=self.refresh_days)

    def get(self, symbol: str, start: date, end: date) -> pd.DataFrame:
        """Return OHLCV frame for symbol between [start, end] (inclusive).

        Frame is indexed by normalized date (tz-naive). Empty frame if no data.
        """
        df = self._mem.get(symbol)
        if df is None:
            df = self._load_from_disk(symbol)
        need_fetch = (df is None or df.empty
                      or df.index.min().date() > start
                      or not self._is_fresh_enough(df, end))
        if need_fetch:
            wide_start = start - timedelta(days=30)  # buffer for indicators
            wide_end = max(end, date.today())
            fresh = _yf_history(symbol, wide_start, wide_end)
            if fresh.empty and (df is None or df.empty):
                self._mem[symbol] = pd.DataFrame()
                return pd.DataFrame()
            if fresh.empty:
                pass  # keep existing cache
            else:
                if df is None or df.empty:
                    df = fresh
                else:
                    df = pd.concat([df, fresh])
                    df = df[~df.index.duplicated(keep='last')].sort_index()
                self._save_to_disk(symbol, df)
        self._mem[symbol] = df
        mask = (df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))
        return df.loc[mask]

    # --- Convenience lookups used by the engine ---------------------------

    def next_trading_day_open(self, symbol: str, after: date,
                              max_skip: int = 7) -> Optional[float]:
        """Open price on the first trading day strictly AFTER `after`."""
        df = self.get(symbol, after - timedelta(days=5), after + timedelta(days=max_skip + 5))
        if df.empty:
            return None
        future = df[df.index > pd.Timestamp(after)]
        if future.empty:
            return None
        return float(future.iloc[0]['Open'])

    def close_on(self, symbol: str, d: date) -> Optional[float]:
        """Close on a specific trading day, or None if not a trading day."""
        df = self.get(symbol, d - timedelta(days=5), d + timedelta(days=5))
        if df.empty:
            return None
        row = df[df.index == pd.Timestamp(d)]
        if row.empty:
            return None
        return float(row.iloc[0]['Close'])

    def last_close_at_or_before(self, symbol: str, d: date,
                                max_skip: int = 7) -> Optional[float]:
        """Most recent close at or before `d`."""
        df = self.get(symbol, d - timedelta(days=max_skip + 5), d + timedelta(days=2))
        if df.empty:
            return None
        past = df[df.index <= pd.Timestamp(d)]
        if past.empty:
            return None
        return float(past.iloc[-1]['Close'])

    def slice(self, symbol: str, end_inclusive: date, lookback_days: int) -> pd.DataFrame:
        """Lookback slice for indicator computation (Path 2 re-scoring)."""
        start = end_inclusive - timedelta(days=lookback_days)
        df = self.get(symbol, start, end_inclusive)
        return df


# --- Bulk warm-up helper --------------------------------------------------

def warmup(symbols: Iterable[str], start: date, end: date,
           cache: Optional[PriceCache] = None,
           sleep_between: float = 0.05) -> dict[str, bool]:
    """Eagerly fetch and cache prices for a universe. Returns success map."""
    cache = cache or PriceCache()
    out = {}
    for i, s in enumerate(symbols):
        try:
            df = cache.get(s, start, end)
            out[s] = not df.empty
        except Exception as e:
            logging.warning(f'[prices.warmup] {s} failed: {e}')
            out[s] = False
        if sleep_between:
            time.sleep(sleep_between)
        if (i + 1) % 25 == 0:
            ok = sum(1 for v in out.values() if v)
            logging.info(f'[prices.warmup] {i+1} done, {ok} successful')
    return out
