"""
Upstox API v2 — market data only (read-only).

Fetches OHLC / LTP / historical candles. Does NOT call portfolio, holdings,
positions, or order endpoints.

Auth via environment only (never config.json or git):
    UPSTOX_ACCESS_TOKEN   — required when enabled
    UPSTOX_DATA_ENABLED   — true/1/yes to prefer Upstox over yfinance in get_ohlcv
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_API_BASE_V2 = "https://api.upstox.com/v2"
_API_BASE_V3 = "https://api.upstox.com/v3"
_INSTRUMENTS_URL = (
    "https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz"
)
_CACHE_MAX_AGE_DAYS = 7
_PERIOD_DAYS = {
    "1d": 5,
    "5d": 10,
    "1mo": 35,
    "3mo": 100,
    "6mo": 200,
    "1y": 400,
    "2y": 800,
    "5y": 2000,
}

_SYMBOL_ALIASES = {
    "GVTD": "GVT&D",
    "AREM": "ARE&M",
    "BAJAJAUTO": "BAJAJ-AUTO",
    "JKBANK": "J&KBANK",
    "MM": "M&M",
    "MMFIN": "M&MFIN",
    "NAMINDIA": "NAM-INDIA",
}


def upstox_data_enabled() -> bool:
    return os.environ.get("UPSTOX_DATA_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def get_access_token() -> str:
    token = os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "UPSTOX_ACCESS_TOKEN is not set. Add it to .env (never commit or paste in chat)."
        )
    return token


def _headers() -> dict:
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Accept": "application/json",
    }


def _normalize_symbol(symbol: str) -> str:
    s = str(symbol or "").strip().upper().replace(".NS", "")
    return _SYMBOL_ALIASES.get(s, s)


def _cache_path(data_dir: str = "data") -> Path:
    return Path(data_dir) / "cache" / "upstox_instruments.json"


def _load_instrument_map(data_dir: str = "data", force_refresh: bool = False) -> Dict[str, str]:
    """Map NSE trading_symbol -> instrument_key (e.g. NSE_EQ|INE...)."""
    path = _cache_path(data_dir)
    if path.exists() and not force_refresh:
        age_days = (time.time() - path.stat().st_mtime) / 86400.0
        if age_days <= _CACHE_MAX_AGE_DAYS:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(raw, dict) and raw:
                    return {str(k).upper(): str(v) for k, v in raw.items()}
            except Exception as exc:
                logger.debug("Upstox instrument cache read failed: %s", exc)

    logger.info("Downloading Upstox instrument master (one-time / weekly cache)...")
    resp = requests.get(_INSTRUMENTS_URL, timeout=120)
    resp.raise_for_status()
    payload = gzip.decompress(resp.content)
    rows = json.loads(payload)
    mapping: Dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        seg = str(row.get("segment", "")).upper()
        if seg != "NSE_EQ":
            continue
        sym = str(row.get("trading_symbol") or row.get("symbol") or "").strip().upper()
        key = str(row.get("instrument_key") or "").strip()
        if sym and key:
            mapping[sym] = key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(mapping, indent=0), encoding="utf-8")
    logger.info("Upstox instrument map cached: %s symbols", len(mapping))
    return mapping


def _invalidate_symbol_instrument_cache(symbol: str, data_dir: str = "data") -> None:
    """Drop one symbol from cache (e.g. stale mock key) and refresh map on next resolve."""
    sym = _normalize_symbol(symbol)
    path = _cache_path(data_dir)
    if not path.exists():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and sym in raw:
            del raw[sym]
            if raw:
                path.write_text(json.dumps(raw, indent=0), encoding="utf-8")
            else:
                path.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("Upstox cache invalidate failed for %s: %s", sym, exc)


def resolve_instrument_key(
    symbol: str, data_dir: str = "data", *, force_refresh: bool = False
) -> Optional[str]:
    sym = _normalize_symbol(symbol)
    mapping = _load_instrument_map(data_dir=data_dir, force_refresh=force_refresh)
    if sym in mapping:
        return mapping[sym]
    # Try without special chars
    compact = sym.replace("&", "").replace("-", "")
    for k, v in mapping.items():
        if k.replace("&", "").replace("-", "") == compact:
            return v
    logger.warning("Upstox: no instrument_key for %s", sym)
    return None


def _period_to_dates(period: str) -> tuple[date, date]:
    p = str(period or "1y").lower().strip()
    days = _PERIOD_DAYS.get(p, 400)
    end = date.today()
    start = end - timedelta(days=days)
    return start, end


def fetch_historical_ohlcv(
    symbol: str,
    period: str = "1y",
    *,
    data_dir: str = "data",
    request_delay_s: float = 0.35,
) -> Optional[pd.DataFrame]:
    """
    Daily OHLCV via Upstox historical-candle API.
    Returns DataFrame indexed by date with Open, High, Low, Close, Volume columns.
    """
    sym = _normalize_symbol(symbol)
    start, end = _period_to_dates(period)
    for attempt in range(2):
        key = resolve_instrument_key(
            sym, data_dir=data_dir, force_refresh=(attempt > 0)
        )
        if not key:
            return None
        url = (
            f"{_API_BASE_V3}/historical-candle/{key}/days/1/"
            f"{end.isoformat()}/{start.isoformat()}"
        )
        try:
            time.sleep(request_delay_s)
            r = requests.get(url, headers=_headers(), timeout=30)
            if r.status_code == 401:
                logger.error(
                    "Upstox: unauthorized — rotate UPSTOX_ACCESS_TOKEN in .env"
                )
                return None
            if r.status_code in (400, 404) and attempt == 0:
                logger.warning(
                    "Upstox: bad instrument_key for %s — refreshing map", sym
                )
                _invalidate_symbol_instrument_cache(sym, data_dir=data_dir)
                continue
            r.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 0:
                _invalidate_symbol_instrument_cache(sym, data_dir=data_dir)
                continue
            raise
    else:
        return None
    try:
        body = r.json()
        candles = (body.get("data") or {}).get("candles") or []
        if not candles:
            logger.warning("Upstox: empty candles for %s", symbol)
            return None
        rows = []
        for c in candles:
            if not c or len(c) < 6:
                continue
            ts = c[0]
            if isinstance(ts, (int, float)):
                dt = pd.to_datetime(ts, unit="s")
            else:
                dt = pd.to_datetime(str(ts))
            rows.append(
                {
                    "Date": dt,
                    "Open": float(c[1]),
                    "High": float(c[2]),
                    "Low": float(c[3]),
                    "Close": float(c[4]),
                    "Volume": float(c[5]),
                }
            )
        if not rows:
            return None
        df = pd.DataFrame(rows).set_index("Date").sort_index()
        df.index = pd.to_datetime(df.index).tz_localize(None)
        return df
    except Exception as exc:
        logger.error("Upstox historical fetch failed for %s: %s", symbol, exc)
        return None


def fetch_ltp(symbols: Iterable[str], *, data_dir: str = "data") -> Dict[str, float]:
    """Last traded price for NSE EQ symbols."""
    keys: List[str] = []
    sym_for_key: Dict[str, str] = {}
    for sym in symbols:
        key = resolve_instrument_key(sym, data_dir=data_dir)
        if key:
            keys.append(key)
            sym_for_key[key] = _normalize_symbol(sym)
    if not keys:
        return {}
    out: Dict[str, float] = {}
    chunk_size = 50
    for i in range(0, len(keys), chunk_size):
        batch = keys[i : i + chunk_size]
        params = {"instrument_key": ",".join(batch)}
        try:
            r = requests.get(
                f"{_API_BASE_V2}/market-quote/ltp",
                headers=_headers(),
                params=params,
                timeout=20,
            )
            r.raise_for_status()
            data = (r.json().get("data") or {})
            for key, payload in data.items():
                sym = sym_for_key.get(key)
                if not sym and isinstance(key, str) and ":" in key:
                    sym = key.split(":", 1)[-1].strip().upper()
                if not sym:
                    sym = str(key)
                ltp = payload.get("last_price") if isinstance(payload, dict) else None
                if ltp is not None:
                    out[sym] = float(ltp)
        except Exception as exc:
            logger.error("Upstox LTP batch failed: %s", exc)
        time.sleep(0.2)
    return out


def fetch_ohlc_snapshot(symbols: Iterable[str], *, data_dir: str = "data") -> Dict[str, dict]:
    """OHLC snapshot (open/high/low/close/ltp) for confirm / chase guards."""
    keys: List[str] = []
    sym_for_key: Dict[str, str] = {}
    for sym in symbols:
        key = resolve_instrument_key(sym, data_dir=data_dir)
        if key:
            keys.append(key)
            sym_for_key[key] = _normalize_symbol(sym)
    if not keys:
        return {}
    out: Dict[str, dict] = {}
    chunk_size = 50
    for i in range(0, len(keys), chunk_size):
        batch = keys[i : i + chunk_size]
        params = {"instrument_key": ",".join(batch)}
        try:
            r = requests.get(
                f"{_API_BASE_V2}/market-quote/ohlc",
                headers=_headers(),
                params=params,
                timeout=20,
            )
            r.raise_for_status()
            data = (r.json().get("data") or {})
            for key, payload in data.items():
                sym = sym_for_key.get(key, key)
                if isinstance(payload, dict):
                    out[sym] = payload
        except Exception as exc:
            logger.error("Upstox OHLC snapshot failed: %s", exc)
        time.sleep(0.2)
    return out
