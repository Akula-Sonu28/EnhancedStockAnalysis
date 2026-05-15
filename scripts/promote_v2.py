"""
Promote V2 (Manual Flip)
========================

Promote v2 from shadow mode to active. This is a deliberate, irreversible-feeling
action that:

  1. Reads `data/v2_promotion_status.json` and aborts unless `promotion_ready=True`
     (override with --force).
  2. Updates `config.json` to set V2_SHADOW_MODE=False and V2_PROMOTION_DATE=today.
  3. Backs up the previous `config.json` to `config.json.pre_v2_promotion_<ts>.bak`.

After running, the next analyzer run will use v2 weights for live actions. To
roll back, restore the .bak config file.

Usage:
    python3 scripts/promote_v2.py            # safe: requires status to be ready
    python3 scripts/promote_v2.py --force    # bypass status check (e.g. emergency)
    python3 scripts/promote_v2.py --dry-run  # show what would change
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / 'config.json'
STATUS_PATH = REPO_ROOT / 'data' / 'v2_promotion_status.json'


def _load_json(p: Path) -> dict:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true',
                        help='Promote even if status is not ready')
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help='Show changes without writing')
    args = parser.parse_args()

    status = _load_json(STATUS_PATH)
    if not args.force:
        if not status.get('promotion_ready'):
            print('REFUSING TO PROMOTE: status not ready.')
            print(f"  Path: {STATUS_PATH}")
            print(f"  consecutive_eligible_days: {status.get('consecutive_eligible_days', 0)}")
            print(f"  days_required: {status.get('days_required_for_promotion', 30)}")
            print('Use --force to override, or wait for status to mature.')
            return 1
    else:
        print('--force: bypassing status check')

    cfg = _load_json(CONFIG_PATH)
    today = datetime.now().strftime('%Y-%m-%d')
    new_cfg = dict(cfg)
    new_cfg['V2_SHADOW_MODE'] = False
    new_cfg['V2_PROMOTION_DATE'] = today

    print('=== Promotion plan ===')
    print(f'  V2_SHADOW_MODE: {cfg.get("V2_SHADOW_MODE", True)} -> False')
    print(f'  V2_PROMOTION_DATE: {cfg.get("V2_PROMOTION_DATE", "")!r} -> {today!r}')

    if args.dry_run:
        print('DRY RUN: no changes written')
        return 0

    if CONFIG_PATH.exists():
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup = CONFIG_PATH.with_suffix(f'.json.pre_v2_promotion_{ts}.bak')
        shutil.copy2(CONFIG_PATH, backup)
        print(f'Backup written: {backup}')

    CONFIG_PATH.write_text(json.dumps(new_cfg, indent=2))
    print(f'Wrote {CONFIG_PATH}')
    print('PROMOTION COMPLETE. Next analyzer run will use v2.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
