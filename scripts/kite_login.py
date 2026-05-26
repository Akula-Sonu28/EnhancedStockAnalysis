#!/usr/bin/env python3
"""Kite Connect login — reuse, renew, or browser auto-capture.

Usage:
    python3 scripts/kite_login.py              # paste request_token
    python3 scripts/kite_login.py --auto       # open browser, capture redirect
    python3 scripts/kite_login.py --check      # only validate current token

For --auto, set Kite Redirect URL to http://127.0.0.1:8765/ (or KITE_REDIRECT_PORT).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Zerodha Kite session")
    parser.add_argument("--auto", action="store_true", help="Browser login + local redirect capture")
    parser.add_argument("--check", action="store_true", help="Validate existing token only")
    parser.add_argument("--request-token", help="Exchange this request_token")
    args = parser.parse_args()

    from src.kite_session import ensure_access_token, token_is_valid, _credentials

    api_key, _, access = _credentials()
    if not api_key:
        print("Set KITE_API_KEY and KITE_API_SECRET in .env")
        return 1

    if args.check:
        ok = bool(access) and token_is_valid(api_key, access)
        print("Token valid." if ok else "Token missing or expired.")
        return 0 if ok else 1

    try:
        token = ensure_access_token(
            auto_browser=args.auto,
            request_token=args.request_token,
        )
        print(f"OK — access token ready ({len(token)} chars). Valid until ~6 AM IST tomorrow.")
        print("Optional: KITE_USE_HOLDINGS=true  KITE_AUTO_LOGIN=true in .env")
        return 0
    except RuntimeError as e:
        if not args.auto and not args.request_token:
            from kiteconnect import KiteConnect
            print(e)
            print("\nManual paste mode:")
            print(KiteConnect(api_key=api_key).login_url())
            req = input("\nPaste request_token: ").strip()
            if req:
                ensure_access_token(request_token=req)
                print("OK — token saved.")
                return 0
        print(e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
