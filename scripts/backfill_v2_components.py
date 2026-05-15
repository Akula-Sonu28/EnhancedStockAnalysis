"""One-shot backfill of v2 component scores into recommendation history.

For each row in `data/recommendation_history.csv`, look up the corresponding
cached comprehensive snapshot (`data/cache/{SYMBOL}_comprehensive_{YYYYMMDD}.json`)
and copy the 6 hybrid_* component scores into the history row. Falls back to
the nearest prior cache file within 7 days when an exact-date match is missing.

This is a one-time bootstrap; routine recording is now done in
`recommendation_history.record_recommendation` via the `components` kwarg.

Exit codes:
    0 - history backfilled (rows updated written back to CSV)
    1 - nothing to backfill (no rows or no cache hits)
    2 - error
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
HISTORY_PATH = REPO_ROOT / 'data' / 'recommendation_history.csv'
CACHE_DIR = REPO_ROOT / 'data' / 'cache'

HYBRID_COLS = (
    'hybrid_fundamental_quality',
    'hybrid_momentum_technical',
    'hybrid_volume_strength',
    'hybrid_multi_timeframe',
    'hybrid_ml_signal',
    'hybrid_risk_adjustment',
)
MAX_BACKFILL_AGE_DAYS = 7


def _find_cache(symbol: str, date: pd.Timestamp) -> Path | None:
    """Return the cache file with the latest mtime within MAX_BACKFILL_AGE_DAYS
    on or before `date`, else None."""
    target = date.strftime('%Y%m%d')
    exact = CACHE_DIR / f'{symbol}_comprehensive_{target}.json'
    if exact.exists():
        return exact
    candidates = sorted(CACHE_DIR.glob(f'{symbol}_comprehensive_*.json'))
    target_dt = date.normalize()
    earliest = target_dt - pd.Timedelta(days=MAX_BACKFILL_AGE_DAYS)
    best: Path | None = None
    best_dt: pd.Timestamp | None = None
    for c in candidates:
        try:
            stamp = c.stem.split('_')[-1]
            cdt = pd.Timestamp(datetime.strptime(stamp, '%Y%m%d'))
        except Exception:
            continue
        if earliest <= cdt <= target_dt and (best_dt is None or cdt > best_dt):
            best, best_dt = c, cdt
    return best


def _load_components(path: Path) -> dict:
    try:
        with open(path) as fp:
            data = json.load(fp)
        out = {}
        for k in HYBRID_COLS:
            v = data.get(k)
            if isinstance(v, (int, float)):
                out[k] = float(v)
        return out
    except Exception as e:
        logging.debug(f'failed to read {path}: {e}')
        return {}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format='[backfill v2] %(message)s')

    if not HISTORY_PATH.exists():
        print(f'ERROR: {HISTORY_PATH} missing')
        return 2
    if not CACHE_DIR.exists():
        print(f'ERROR: {CACHE_DIR} missing')
        return 2

    df = pd.read_csv(HISTORY_PATH)
    if df.empty:
        print('history empty, nothing to backfill')
        return 1
    df['date'] = pd.to_datetime(df['date'], errors='coerce')

    print(f'Loaded {len(df)} history rows; scanning cache in {CACHE_DIR}')
    for c in HYBRID_COLS:
        if c not in df.columns:
            df[c] = None

    hits = 0
    misses = 0
    for idx, row in df.iterrows():
        sym = str(row.get('symbol') or '').upper()
        when = row.get('date')
        if not sym or pd.isna(when):
            misses += 1
            continue
        # Skip rows already populated.
        if all(pd.notna(row.get(c)) for c in HYBRID_COLS):
            continue
        cache_path = _find_cache(sym, when)
        if cache_path is None:
            misses += 1
            continue
        comps = _load_components(cache_path)
        if not comps:
            misses += 1
            continue
        for k, v in comps.items():
            df.at[idx, k] = v
        hits += 1

    print(f'Backfill summary: hits={hits}, misses={misses}, rows_total={len(df)}')

    # Component-coverage by-column
    for c in HYBRID_COLS:
        nn = df[c].notna().sum()
        print(f'  {c:34s} non-null after backfill: {nn:>4}/{len(df)}')

    if hits == 0:
        print('no cache hits; not rewriting CSV')
        return 1

    # Write back; preserve datetime serialization
    df_out = df.copy()
    df_out['date'] = pd.to_datetime(df_out['date'], errors='coerce')
    df_out.to_csv(HISTORY_PATH, index=False)
    print(f'wrote {HISTORY_PATH} with {hits} backfilled rows')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
