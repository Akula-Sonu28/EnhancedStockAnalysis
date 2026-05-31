#!/usr/bin/env python3
"""One command: Kite session + holdings/orders refresh + analysis.

Examples:
    # Preview (no history writes)
    python3 scripts/run_analysis.py --dry-run --fast

    # Live weekly run (Kite sync + history commit)
    python3 scripts/run_analysis.py --kite-auto

    # Live with explicit flags
    python3 scripts/run_analysis.py --portfolio-amount 100000 --risk-profile aggressive

    # Skip Zerodha sync (use existing Holding/*.csv)
    python3 scripts/run_analysis.py --skip-kite --dry-run --fast

Env (.env):
    KITE_AUTO_LOGIN=true      — open browser if token expired (--kite-auto)
    KITE_USE_HOLDINGS=true    — skip CSV refresh; analyzer pulls API directly
    ANALYSIS_LIVE_DEFAULT=true — bare `run_analysis.py` writes history (no --dry-run)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
except ImportError:
    pass


def _sync_kite(*, auto_browser: bool) -> None:
    from src.kite_session import ensure_access_token

    print("=" * 60)
    print("STEP 1/2 — Zerodha Kite sync")
    print("=" * 60)
    ensure_access_token(auto_browser=auto_browser)

    if os.environ.get("KITE_USE_HOLDINGS", "").lower() in ("1", "true", "yes"):
        print("[KITE] KITE_USE_HOLDINGS=true — CSV refresh skipped (analyzer uses API).")
        return

    from src.zerodha_holdings import (
        fetch_holdings_dataframe,
        fetch_orders_dataframe,
        save_holdings_snapshot,
        save_orders_snapshot,
    )

    hdf = fetch_holdings_dataframe()
    odf = fetch_orders_dataframe()
    hp = save_holdings_snapshot(hdf)
    op = save_orders_snapshot(odf)
    print(f"[KITE] Holdings: {len(hdf)} -> {hp}")
    print(f"[KITE] Orders:   {len(odf)} -> {op}")


def _default_analyzer_argv(*, kite_auto: bool) -> list[str]:
    """Live weekly defaults when using --kite-auto; preview otherwise."""
    from config import get_config

    cfg = get_config()
    amount = int(getattr(cfg, 'DEFAULT_PORTFOLIO_AMOUNT', 100000))
    live_default = kite_auto or os.environ.get('ANALYSIS_LIVE_DEFAULT', '').lower() in (
        '1', 'true', 'yes',
    )
    if live_default:
        return [
            '--portfolio-amount', str(amount),
            '--risk-profile', 'moderate',
        ]
    return ['--dry-run', '--fast']


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync Zerodha portfolio then run analyze_top200_stocks_enhanced.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--skip-kite", action="store_true", help="Skip Kite sync; use existing Holding/*.csv")
    parser.add_argument("--kite-only", action="store_true", help="Only sync Kite; do not run analysis")
    parser.add_argument(
        "--kite-auto",
        action="store_true",
        help="Open browser for login if token expired (or set KITE_AUTO_LOGIN=true)",
    )
    args, analyzer_argv = parser.parse_known_args()

    auto = args.kite_auto or os.environ.get("KITE_AUTO_LOGIN", "").lower() in ("1", "true", "yes")

    if not args.skip_kite:
        try:
            _sync_kite(auto_browser=auto)
        except Exception as exc:
            print(f"[KITE] Sync failed: {exc}")
            return 1
    else:
        print("[KITE] Skipped (--skip-kite). Using existing Holding/*.csv")

    if args.kite_only:
        return 0

    print("\n" + "=" * 60)
    print("STEP 2/2 — Stock analysis")
    print("=" * 60)

    if not analyzer_argv:
        analyzer_argv = _default_analyzer_argv(kite_auto=args.kite_auto)
        if '--dry-run' in analyzer_argv:
            print("[INFO] Preview mode (--dry-run --fast). "
                  "Use --kite-auto for live weekly run with history writes.")
        else:
            amt = next(
                (analyzer_argv[i + 1] for i, a in enumerate(analyzer_argv)
                 if a == '--portfolio-amount' and i + 1 < len(analyzer_argv)),
                '?',
            )
            print(f"[INFO] Live run — portfolio ₹{amt}, history will be written.")
    elif '--dry-run' not in analyzer_argv:
        print("[INFO] Live run — recommendation_history.csv will be updated.")

    cmd = [sys.executable, str(_ROOT / "analyze_top200_stocks_enhanced.py"), *analyzer_argv]
    print("Running:", " ".join(cmd), "\n")
    return subprocess.call(cmd, cwd=str(_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
