#!/usr/bin/env python3
"""Fetch live holdings from Zerodha Kite and write Holding/holdings_latest.csv.

Does not run analysis. Use before a run if you prefer CSV + fresh API data.

    python3 scripts/fetch_zerodha_holdings.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass

print("Use scripts/fetch_zerodha_portfolio.py for holdings + orders.")
import subprocess

def main() -> int:
    return subprocess.call(
        [sys.executable, str(_ROOT / "scripts" / "fetch_zerodha_portfolio.py"), *sys.argv[1:]]
    )


if __name__ == "__main__":
    raise SystemExit(main())
