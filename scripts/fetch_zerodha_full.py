#!/usr/bin/env python3
"""Fetch all available read-only Zerodha Kite account data.

Writes:
  data/zerodha/latest/          — always refreshed
  data/zerodha/snapshots/<ts>/   — timestamped archive + Excel summary
  Holding/holdings_latest.csv, Holding/orders_latest.csv

    python3 scripts/fetch_zerodha_full.py
    python3 scripts/fetch_zerodha_full.py --request-token TOKEN
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request-token", help="Daily Kite login token")
    args = parser.parse_args()

    if args.request_token:
        import os
        import re
        from kiteconnect import KiteConnect

        api_key = os.environ.get("KITE_API_KEY", "").strip()
        api_secret = os.environ.get("KITE_API_SECRET", "").strip()
        kite = KiteConnect(api_key=api_key)
        session = kite.generate_session(args.request_token.strip(), api_secret=api_secret)
        env_path = _ROOT / ".env"
        text = env_path.read_text(encoding="utf-8")
        text = re.sub(r"^KITE_ACCESS_TOKEN=.*$", f"KITE_ACCESS_TOKEN={session['access_token']}", text, flags=re.M)
        env_path.write_text(text, encoding="utf-8")
        print(f"Logged in: {session.get('user_name')}")

    from src.zerodha_export import fetch_all, save_export

    print("Fetching all available Kite data...")
    bundle = fetch_all()
    out = save_export(bundle)

    m = bundle.get("errors") or {}
    print(f"\nSaved snapshot: {out}")
    print(f"Latest copy:    {_ROOT / 'data/zerodha/latest'}")
    print(f"Excel summary:  {out / 'zerodha_full_export.xlsx'}")
    print("\nCounts:")
    print(f"  Holdings: {len(bundle.get('holdings_raw') or [])}")
    print(f"  Orders:   {len(bundle.get('orders_raw') or [])}")
    print(f"  Trades:   {len(bundle.get('trades') or [])}")
    print(f"  Positions day/net: "
          f"{len((bundle.get('positions') or {}).get('day') or [])}/"
          f"{len((bundle.get('positions') or {}).get('net') or [])}")
    if m:
        print(f"\nPartial errors ({len(m)}):")
        for k, v in m.items():
            print(f"  - {k}: {v}")
    else:
        print("\nAll endpoints OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
