#!/usr/bin/env python3
"""Keep QMST dashboard available at http://127.0.0.1:9876/ until Ctrl+C."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

DEFAULT_HTML = REPO_ROOT / 'frontend' / 'qmst-dashboard.html'


def main() -> int:
    parser = argparse.ArgumentParser(description='Serve QMST dashboard on localhost')
    parser.add_argument('--port', type=int, default=9876, help='Port (default 9876)')
    parser.add_argument('--open', action='store_true', help='Open browser after start')
    parser.add_argument('--rebuild', action='store_true', help='Rebuild HTML from latest report first')
    parser.add_argument('--report', type=str, default='', help='Report xlsx for --rebuild')
    parser.add_argument('--portfolio-amount', type=float, default=0)
    args = parser.parse_args()

    if args.rebuild:
        from src.analysis_dashboard import build_analysis_dashboard

        report = args.report
        if not report:
            files = sorted((REPO_ROOT / 'reports').glob('Enhanced_Stock_Report_*.xlsx'))
            if not files:
                print('No report found — build dashboard first or pass --report')
                return 1
            report = str(files[-1])
        path = build_analysis_dashboard(
            report,
            portfolio_amount=args.portfolio_amount,
            output_path=DEFAULT_HTML,
        )
        if not path:
            return 1
        print(f'[DASH] Rebuilt: {path}')

    if not DEFAULT_HTML.is_file():
        print(f'Missing {DEFAULT_HTML} — run: python3 scripts/build_analysis_dashboard.py')
        return 1

    from src.dashboard_browser import (
        extract_build_version_from_html,
        foreign_dashboard_server,
        ensure_dashboard_server,
        open_or_reload_dashboard,
    )

    foreign = foreign_dashboard_server(args.port)
    if foreign:
        print(f'[DASH] ERROR: Port {args.port} is already used by another checkout:')
        print(f'         {foreign}')
        print(f'         This repo: {REPO_ROOT}')
        print(f'         Stop it: kill $(lsof -ti :{args.port})')
        return 1

    html = DEFAULT_HTML.read_text(encoding='utf-8')
    version = extract_build_version_from_html(html)
    if not version:
        from src.dashboard_browser import dashboard_build_version

        version = dashboard_build_version({'runDate': ''}, DEFAULT_HTML)
    url = ensure_dashboard_server(html, version, port=args.port)
    print(f'[DASH] Serving {REPO_ROOT} at {url}')
    print('[DASH] Press Ctrl+C to stop')

    if args.open:
        action = open_or_reload_dashboard(url)
        print(f'[DASH] Browser {action}: {url}')

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        print('\n[DASH] Stopped')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
