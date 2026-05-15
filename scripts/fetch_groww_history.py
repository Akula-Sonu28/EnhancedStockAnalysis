"""Backfill daily OHLCV from Groww for the top-200 universe (or any list).

Standalone backfill: writes per-symbol CSVs to data/cache/groww/ and a
_manifest.json. Does not touch live scoring, technical_analyzer, or any
config flag. Re-running is idempotent (resumes from last cached date).

Examples:
    python3 scripts/fetch_groww_history.py                       # top-200, last 2y
    python3 scripts/fetch_groww_history.py --years 3
    python3 scripts/fetch_groww_history.py --symbols RELIANCE TCS INFY
    python3 scripts/fetch_groww_history.py --symbols-file my_universe.txt
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    pass

from src.groww_history import (  # noqa: E402
    GrowwHistoryClient,
    GrowwHistoryConfig,
    fetch_and_cache_universe,
)


def _resolve_symbols(args) -> list[str]:
    if args.symbols:
        return [s.upper() for s in args.symbols]
    if args.symbols_file:
        return [
            s.strip().upper()
            for s in Path(args.symbols_file).read_text().splitlines()
            if s.strip()
        ]
    return _default_top200()


def _default_top200() -> list[str]:
    """Resolve the default universe from existing repo artefacts.

    Preference order:
        1. data/top200_universe.json (if produced by the analyzer)
        2. distinct symbols from data/recommendation_history.csv
    """
    universe_json = _PROJECT_ROOT / "data" / "top200_universe.json"
    if universe_json.exists():
        data = json.loads(universe_json.read_text())
        symbols = data.get("symbols") if isinstance(data, dict) else data
        return sorted({str(s).upper() for s in symbols})
    history_csv = _PROJECT_ROOT / "data" / "recommendation_history.csv"
    if history_csv.exists():
        import pandas as pd
        df = pd.read_csv(history_csv, usecols=["symbol"])
        return sorted({str(s).upper() for s in df["symbol"].dropna().unique().tolist()})
    raise SystemExit(
        "No universe found. Pass --symbols or --symbols-file, or create "
        "data/top200_universe.json."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--years", type=int, default=2, help="Lookback years (default 2)")
    parser.add_argument("--end", help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--symbols", nargs="*", help="Explicit NSE trading symbols")
    parser.add_argument("--symbols-file", help="Path to newline-separated symbols file")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    log = logging.getLogger(__name__)

    end = date.fromisoformat(args.end) if args.end else date.today()
    start = end - timedelta(days=args.years * 365)
    symbols = _resolve_symbols(args)
    log.info("Fetching %d symbols, %s .. %s", len(symbols), start, end)

    cfg = GrowwHistoryConfig.from_env()
    client = GrowwHistoryClient(cfg)
    manifest = fetch_and_cache_universe(client, symbols, start, end, cfg.cache_dir)

    summary: dict[str, int] = {}
    for v in manifest.values():
        key = (
            v["status"]
            if v["status"] in {"ok", "up_to_date", "no_new_data"}
            else "error"
        )
        summary[key] = summary.get(key, 0) + 1
    print(f"Done. {summary} cache_dir={cfg.cache_dir}")
    return 0 if summary.get("error", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
