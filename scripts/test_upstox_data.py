#!/usr/bin/env python3
"""Smoke test Upstox market data (requires UPSTOX_ACCESS_TOKEN in .env)."""
from __future__ import annotations

import os
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from dotenv import load_dotenv

load_dotenv(REPO / ".env")


def main() -> int:
    if not os.environ.get("UPSTOX_ACCESS_TOKEN", "").strip():
        print("Set UPSTOX_ACCESS_TOKEN in .env (do not paste in chat).")
        return 1
    os.environ["UPSTOX_DATA_ENABLED"] = "true"
    from src.upstox_data import fetch_historical_ohlcv, fetch_ltp

    sym = "RELIANCE"
    df = fetch_historical_ohlcv(sym, period="3mo")
    if df is None or df.empty:
        print(f"FAIL: no OHLCV for {sym}")
        return 1
    print(f"OK: {sym} rows={len(df)} last_close={df['Close'].iloc[-1]:.2f}")
    ltp = fetch_ltp([sym, "TCS"])
    print(f"LTP: {ltp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
