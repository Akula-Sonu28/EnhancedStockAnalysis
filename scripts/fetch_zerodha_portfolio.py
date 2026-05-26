#!/usr/bin/env python3
"""Fetch live holdings + orders from Zerodha Kite into Holding/.

    python3 scripts/fetch_zerodha_portfolio.py
    python3 scripts/fetch_zerodha_portfolio.py --request-token YOUR_TOKEN

Requires KITE_API_KEY, KITE_API_SECRET in .env. Access token from daily login
or pass --request-token once (exchanges and saves token automatically).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

import os


def _update_env(key: str, value: str) -> None:
    env_path = _ROOT / ".env"
    line_re = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    new_line = f"{key}={value}"
    text = env_path.read_text(encoding="utf-8") if env_path.exists() else ""
    text = line_re.sub(new_line, text) if line_re.search(text) else text.rstrip() + "\n" + new_line + "\n"
    env_path.write_text(text, encoding="utf-8")


def _exchange_request_token(request_token: str) -> None:
    api_key = os.environ.get("KITE_API_KEY", "").strip()
    api_secret = os.environ.get("KITE_API_SECRET", "").strip()
    if not api_key or not api_secret:
        raise RuntimeError("KITE_API_KEY and KITE_API_SECRET required in .env")
    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=api_key)
    session = kite.generate_session(request_token, api_secret=api_secret)
    _update_env("KITE_ACCESS_TOKEN", session["access_token"])
    os.environ["KITE_ACCESS_TOKEN"] = session["access_token"]
    print(f"Logged in as: {session.get('user_name', 'N/A')}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch Zerodha holdings and orders")
    parser.add_argument(
        "--request-token",
        help="One-time token from http://127.0.0.1/?request_token=... after browser login",
    )
    parser.add_argument("--login-url", action="store_true", help="Print Kite login URL and exit")
    args = parser.parse_args()

    api_key = os.environ.get("KITE_API_KEY", "").strip()
    if not api_key:
        print("Set KITE_API_KEY in .env")
        return 1

    if args.login_url:
        from kiteconnect import KiteConnect
        print(KiteConnect(api_key=api_key).login_url())
        return 0

    if args.request_token:
        _exchange_request_token(args.request_token.strip())

    from src.zerodha_holdings import (
        fetch_holdings_dataframe,
        fetch_orders_dataframe,
        save_holdings_snapshot,
        save_orders_snapshot,
    )

    try:
        hdf = fetch_holdings_dataframe()
        odf = fetch_orders_dataframe()
    except RuntimeError as e:
        if "KITE_ACCESS_TOKEN" in str(e):
            from kiteconnect import KiteConnect
            print("No access token. Steps:")
            print("1. Open:", KiteConnect(api_key=api_key).login_url())
            print("2. Re-run: python3 scripts/fetch_zerodha_portfolio.py --request-token TOKEN")
            return 1
        raise

    hpath = save_holdings_snapshot(hdf)
    opath = save_orders_snapshot(odf)

    print(f"\nHoldings: {len(hdf)} positions -> {hpath}")
    if not hdf.empty:
        print(hdf[["Instrument", "Qty.", "LTP", "Cur. val", "P&L"]].to_string(index=False))
    print(f"\nOrders: {len(odf)} rows -> {opath}")
    if not odf.empty:
        print(odf.head(20).to_string(index=False))
    print(f"\nAlso: Holding/holdings_latest.csv, Holding/orders_latest.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
