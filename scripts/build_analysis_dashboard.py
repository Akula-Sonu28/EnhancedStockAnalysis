#!/usr/bin/env python3
"""Build Tape & Ledger HTML dashboard from latest or specified Excel report."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.analysis_dashboard import build_analysis_dashboard, DEFAULT_OUTPUT


def main() -> int:
    parser = argparse.ArgumentParser(description='Build QMST analysis dashboard (HTML)')
    parser.add_argument('--report', type=str, default='', help='Path to Enhanced_Stock_Report xlsx')
    parser.add_argument('--output', type=str, default='', help='Output HTML path')
    parser.add_argument('--portfolio-amount', type=float, default=0)
    parser.add_argument('--regime', type=str, default='Sideways')
    parser.add_argument('--open', action='store_true', help='Open in browser after build')
    parser.add_argument(
        '--no-sync-canvas',
        action='store_true',
        help='Skip Cursor canvas refresh (HTML only)',
    )
    args = parser.parse_args()

    report = args.report
    if not report:
        files = sorted((REPO_ROOT / 'reports').glob('Enhanced_Stock_Report_*.xlsx'))
        if not files:
            print('No Enhanced_Stock_Report_*.xlsx in reports/')
            return 1
        report = str(files[-1])

    out = Path(args.output) if args.output else DEFAULT_OUTPUT
    path = build_analysis_dashboard(
        report,
        portfolio_amount=args.portfolio_amount,
        regime=args.regime,
        output_path=out,
        open_browser=args.open,
        sync_canvas=not args.no_sync_canvas,
    )
    return 0 if path else 1


if __name__ == '__main__':
    raise SystemExit(main())
