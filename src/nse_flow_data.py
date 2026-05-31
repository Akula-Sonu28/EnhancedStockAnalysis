"""
NSE bhavcopy flow data (shadow layer) — delivery % and turnover.

Batch-fetches once per run; enriches results with shadow columns for IC study.
Does not drive actions until ORACLE_PICK_METRIC promotes fq_score_nse.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from io import StringIO
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import requests

logger = logging.getLogger(__name__)

_NSE_HOME = "https://www.nseindia.com"
_BHAV_URL = (
    "https://nsearchives.nseindia.com/products/content/"
    "sec_bhavdata_full_{ddmmyyyy}.csv"
)
_CACHE_PATH = Path("data/nse_bhavcopy_latest.csv")
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


def _cfg(cfg, key: str, default):
    if cfg is None:
        try:
            from config import get_config
            cfg = get_config()
        except Exception:
            return default
    return getattr(cfg, key, default)


def nse_flow_shadow_enabled(cfg=None) -> bool:
    return bool(_cfg(cfg, "ORACLE_USE_NSE_FLOW_SHADOW", True))


def _fetch_bhavcopy_for_date(day: datetime) -> Optional[pd.DataFrame]:
    ddmmyyyy = day.strftime("%d%m%Y")
    url = _BHAV_URL.format(ddmmyyyy=ddmmyyyy)
    try:
        session = requests.Session()
        session.headers.update(_HEADERS)
        session.get(_NSE_HOME, timeout=15)
        resp = session.get(url, timeout=30)
        if resp.status_code != 200 or not resp.text.strip():
            return None
        df = pd.read_csv(StringIO(resp.text))
        df.columns = [str(c).strip().upper() for c in df.columns]
        if "SYMBOL" not in df.columns:
            return None
        df["SYMBOL"] = df["SYMBOL"].astype(str).str.strip().str.upper()
        df["_bhav_date"] = day.strftime("%Y-%m-%d")
        return df
    except Exception as exc:
        logger.debug("NSE bhavcopy fetch failed for %s: %s", ddmmyyyy, exc)
        return None


def load_bhavcopy(force_refresh: bool = False, max_lookback_days: int = 7) -> pd.DataFrame:
    """Load cached bhavcopy or fetch the latest available trading day."""
    if not force_refresh and _CACHE_PATH.exists():
        try:
            age_h = (datetime.now().timestamp() - _CACHE_PATH.stat().st_mtime) / 3600.0
            if age_h < 24:
                cached = pd.read_csv(_CACHE_PATH)
                if not cached.empty and "SYMBOL" in cached.columns:
                    return cached
        except Exception:
            pass

    for offset in range(max_lookback_days + 1):
        day = datetime.now() - timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        df = _fetch_bhavcopy_for_date(day)
        if df is not None and not df.empty:
            try:
                _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                df.to_csv(_CACHE_PATH, index=False)
            except Exception:
                pass
            return df
    return pd.DataFrame()


def build_flow_lookup(bhav: pd.DataFrame) -> Dict[str, dict]:
    """Symbol -> delivery_pct, turnover_cr, close."""
    if bhav is None or bhav.empty:
        return {}
    lookup: Dict[str, dict] = {}
    for _, row in bhav.iterrows():
        sym = str(row.get("SYMBOL", "")).strip().upper()
        if not sym or sym in lookup:
            continue
        deliv = pd.to_numeric(row.get("DELIV_PER", row.get("DELIV QTY")), errors="coerce")
        turnover_lacs = pd.to_numeric(
            row.get("TURNOVER_LACS", row.get("TURNOVER RS.")),
            errors="coerce",
        )
        close = pd.to_numeric(row.get("CLOSE PRICE", row.get("CLOSE")), errors="coerce")
        lookup[sym] = {
            "nse_delivery_pct": float(deliv) if pd.notna(deliv) else None,
            "nse_turnover_cr": float(turnover_lacs / 100.0) if pd.notna(turnover_lacs) else None,
            "nse_close": float(close) if pd.notna(close) else None,
        }
    return lookup


def compute_nse_volume_strength(delivery_pct: float, turnover_cr: float) -> float:
    """Shadow volume strength 0-100 from NSE delivery % and turnover (₹ Cr)."""
    d = max(0.0, min(float(delivery_pct or 0), 100.0))
    t = max(0.0, float(turnover_cr or 0))
    deliv_score = min(d / 60.0, 1.0) * 55.0
    turn_score = min(t / 500.0, 1.0) * 45.0
    return float(max(0.0, min(100.0, deliv_score + turn_score)))


def enrich_nse_flow_shadow_columns(df: pd.DataFrame, cfg=None) -> pd.DataFrame:
    """Add nse_* shadow columns and fq_score_nse (does not replace fq_score)."""
    if df is None or df.empty or not nse_flow_shadow_enabled(cfg):
        return df
    out = df.copy()
    bhav = load_bhavcopy()
    lookup = build_flow_lookup(bhav)
    if not lookup:
        out["nse_flow_status"] = "UNAVAILABLE"
        return out

    from src.flow_quality_oracle import compute_flow_quality_adapt

    deliv_col = []
    turn_col = []
    vol_nse = []
    fq_nse = []
    for _, row in out.iterrows():
        sym = str(row.get("symbol", "")).strip().upper().replace(".NS", "")
        meta = lookup.get(sym, {})
        d = meta.get("nse_delivery_pct")
        t = meta.get("nse_turnover_cr")
        deliv_col.append(d)
        turn_col.append(t)
        if d is not None and t is not None:
            vs = compute_nse_volume_strength(d, t)
            mom = row.get("hybrid_momentum_technical", 50)
            fq_nse.append(compute_flow_quality_adapt(vs, mom, cfg))
            vol_nse.append(vs)
        else:
            fq_nse.append(None)
            vol_nse.append(None)

    out["nse_delivery_pct"] = deliv_col
    out["nse_turnover_cr"] = turn_col
    out["nse_volume_strength"] = vol_nse
    out["fq_score_nse"] = fq_nse
    out["nse_flow_status"] = "OK"
    return out
