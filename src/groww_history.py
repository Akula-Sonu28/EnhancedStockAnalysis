"""Groww historical-candle fetcher for backtest data.

Read-only. Standalone: does not touch live scoring, technical_analyzer,
recommendation history, allocator, or any config flag. Output: per-symbol CSV
under data/cache/groww/<SYMBOL>_1d.csv plus a _manifest.json summary.

Auth via environment variables only:
    GROWW_API_KEY, GROWW_API_SECRET

Backtest consumption:
    from src.groww_history import load_cached
    df = load_cached(Path("data/cache/groww"), "RELIANCE")
"""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd

logger = logging.getLogger(__name__)

# Groww caps daily candle requests at 180 days per call (see /backtesting docs).
_MAX_DAILY_WINDOW_DAYS = 180
_DEFAULT_REQUEST_DELAY_S = 0.5
_HIST_COLUMNS = ["open", "high", "low", "close", "volume"]


@dataclass(frozen=True)
class GrowwHistoryConfig:
    api_key: str
    api_secret: str
    cache_dir: Path
    request_delay_s: float = _DEFAULT_REQUEST_DELAY_S
    retry_attempts: int = 3

    @classmethod
    def from_env(cls, cache_dir: Path | None = None) -> "GrowwHistoryConfig":
        api_key = os.environ.get("GROWW_API_KEY")
        api_secret = os.environ.get("GROWW_API_SECRET")
        if not api_key or not api_secret:
            raise RuntimeError(
                "Set GROWW_API_KEY and GROWW_API_SECRET environment variables. "
                "Never put credentials in config.json or commit them."
            )
        if cache_dir is None:
            try:
                from config import get_config
                cache_dir = Path(get_config().CACHE_DIR) / "groww"
            except Exception:
                cache_dir = Path("data/cache/groww")
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cls(api_key=api_key, api_secret=api_secret, cache_dir=cache_dir)


class GrowwHistoryClient:
    """Fetches daily OHLCV via Groww's get_historical_candles SDK call."""

    def __init__(self, cfg: GrowwHistoryConfig) -> None:
        self._cfg = cfg
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return self._client
        try:
            from growwapi import GrowwAPI
        except ImportError as exc:
            raise RuntimeError(
                "growwapi is not installed. Run: pip install growwapi"
            ) from exc
        access_token = GrowwAPI.get_access_token(
            api_key=self._cfg.api_key, secret=self._cfg.api_secret
        )
        self._client = GrowwAPI(access_token)
        return self._client

    def fetch_daily(
        self, trading_symbol: str, start: date, end: date
    ) -> pd.DataFrame:
        if start > end:
            return _empty_frame()
        client = self._ensure_client()
        groww_symbol = f"NSE-{trading_symbol.upper()}"
        frames: list[pd.DataFrame] = []
        cursor = start
        while cursor <= end:
            chunk_end = min(cursor + timedelta(days=_MAX_DAILY_WINDOW_DAYS - 1), end)
            chunk = self._fetch_chunk(client, groww_symbol, cursor, chunk_end)
            if not chunk.empty:
                frames.append(chunk)
            cursor = chunk_end + timedelta(days=1)
            time.sleep(self._cfg.request_delay_s)
        if not frames:
            return _empty_frame()
        df = pd.concat(frames).sort_index() if len(frames) > 1 else frames[0]
        return df[~df.index.duplicated(keep="last")]

    def _fetch_chunk(
        self, client, groww_symbol: str, start: date, end: date
    ) -> pd.DataFrame:
        start_str = f"{start.isoformat()} 09:15:00"
        end_str = f"{end.isoformat()} 15:30:00"
        last_err: Exception | None = None
        for attempt in range(self._cfg.retry_attempts):
            try:
                resp = client.get_historical_candles(
                    exchange=client.EXCHANGE_NSE,
                    segment=client.SEGMENT_CASH,
                    groww_symbol=groww_symbol,
                    start_time=start_str,
                    end_time=end_str,
                    candle_interval=client.CANDLE_INTERVAL_DAY,
                )
                return _candles_to_frame(resp.get("candles") or [])
            except Exception as exc:
                last_err = exc
                backoff = self._cfg.request_delay_s * (2 ** attempt)
                logger.warning(
                    "Groww fetch %s [%s..%s] attempt %d failed: %s; backoff %.2fs",
                    groww_symbol, start, end, attempt + 1, exc, backoff,
                )
                time.sleep(backoff)
        logger.error(
            "Giving up on %s [%s..%s]: %s", groww_symbol, start, end, last_err
        )
        return _empty_frame()


def _candles_to_frame(candles: list) -> pd.DataFrame:
    if not candles:
        return _empty_frame()
    rows = []
    for c in candles:
        ts_raw = c[0]
        if isinstance(ts_raw, (int, float)):
            ts = datetime.utcfromtimestamp(ts_raw)
        else:
            ts = pd.to_datetime(ts_raw).to_pydatetime()
        rows.append(
            {
                "date": pd.Timestamp(ts).normalize(),
                "open": float(c[1]),
                "high": float(c[2]),
                "low": float(c[3]),
                "close": float(c[4]),
                "volume": int(c[5]) if len(c) > 5 and c[5] is not None else 0,
            }
        )
    return pd.DataFrame(rows).set_index("date").sort_index()


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=_HIST_COLUMNS, index=pd.DatetimeIndex([], name="date")
    )


def _cache_path(cache_dir: Path, symbol: str) -> Path:
    return cache_dir / f"{symbol.upper()}_1d.csv"


def load_cached(cache_dir: Path, symbol: str) -> pd.DataFrame:
    path = _cache_path(cache_dir, symbol)
    if not path.exists():
        return _empty_frame()
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    return df[_HIST_COLUMNS]


def upsert_cache(
    cache_dir: Path, symbol: str, new_df: pd.DataFrame
) -> pd.DataFrame:
    if new_df.empty:
        return load_cached(cache_dir, symbol)
    existing = load_cached(cache_dir, symbol)
    if existing.empty:
        merged = new_df.sort_index()
    else:
        merged = pd.concat([existing, new_df]).sort_index()
    merged = merged[~merged.index.duplicated(keep="last")]
    cache_dir.mkdir(parents=True, exist_ok=True)
    merged.to_csv(_cache_path(cache_dir, symbol))
    return merged


def fetch_and_cache_universe(
    client: GrowwHistoryClient,
    symbols: Iterable[str],
    start: date,
    end: date,
    cache_dir: Path,
) -> dict[str, dict]:
    """Fetch every symbol incrementally; resumes from last cached date.

    Per-symbol exceptions are caught so one bad symbol does not abort the run.
    """
    manifest: dict[str, dict] = {}
    for sym in symbols:
        sym = sym.upper()
        try:
            cached = load_cached(cache_dir, sym)
            if cached.empty:
                fetch_start = start
            else:
                last_cached = (cached.index.max() + pd.Timedelta(days=1)).date()
                fetch_start = max(start, last_cached)
            if fetch_start > end:
                manifest[sym] = {
                    "rows": int(len(cached)),
                    "last_date": str(cached.index.max().date())
                    if not cached.empty
                    else None,
                    "status": "up_to_date",
                }
                _write_manifest(cache_dir, manifest)
                continue
            new_df = client.fetch_daily(sym, fetch_start, end)
            merged = upsert_cache(cache_dir, sym, new_df)
            manifest[sym] = {
                "rows": int(len(merged)),
                "last_date": str(merged.index.max().date())
                if not merged.empty
                else None,
                "status": "ok" if not new_df.empty else "no_new_data",
            }
        except Exception as exc:
            logger.exception("Failed %s", sym)
            manifest[sym] = {
                "rows": 0,
                "last_date": None,
                "status": f"error: {exc}",
            }
        _write_manifest(cache_dir, manifest)
    return manifest


def _write_manifest(cache_dir: Path, manifest: dict) -> None:
    path = cache_dir / "_manifest.json"
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True))
