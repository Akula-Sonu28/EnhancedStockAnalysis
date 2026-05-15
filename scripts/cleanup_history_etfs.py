"""
One-time cleanup: Remove ETF/REIT/InvIT rows from data/recommendation_history.csv.

Creates a timestamped backup before mutating. Uses the canonical exclusion list
in src/universe_filter.py so this script and the live filter stay in sync.
"""
from __future__ import annotations

import sys
import shutil
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.universe_filter import is_excluded_instrument  # noqa: E402

HISTORY_PATH = REPO_ROOT / 'data' / 'recommendation_history.csv'


def main(dry_run: bool = False) -> int:
    if not HISTORY_PATH.exists():
        print(f"[cleanup] {HISTORY_PATH} does not exist; nothing to do")
        return 0

    df = pd.read_csv(HISTORY_PATH)
    total = len(df)
    if total == 0:
        print(f"[cleanup] {HISTORY_PATH} is empty")
        return 0

    excluded_mask = df['symbol'].astype(str).map(lambda s: is_excluded_instrument(s)[0])
    n_excluded = int(excluded_mask.sum())
    print(f"[cleanup] Total rows: {total}")
    print(f"[cleanup] Rows to drop (ETF/REIT/InvIT): {n_excluded}")
    if n_excluded:
        print(f"[cleanup] Symbols dropped: {sorted(df.loc[excluded_mask, 'symbol'].unique().tolist())}")

    if n_excluded == 0:
        print("[cleanup] No ETF rows found; nothing to do")
        return 0

    if dry_run:
        print("[cleanup] DRY RUN: no changes written")
        return 0

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = HISTORY_PATH.with_suffix(f'.csv.pre_etf_cleanup_{ts}.bak')
    shutil.copy2(HISTORY_PATH, backup_path)
    print(f"[cleanup] Backup written: {backup_path}")

    cleaned = df.loc[~excluded_mask].copy()
    cleaned.to_csv(HISTORY_PATH, index=False)
    print(f"[cleanup] Wrote cleaned history: {len(cleaned)} rows (was {total})")
    return 0


if __name__ == '__main__':
    dry = '--dry-run' in sys.argv or '-n' in sys.argv
    raise SystemExit(main(dry_run=dry))
