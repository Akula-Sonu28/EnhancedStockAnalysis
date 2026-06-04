"""Tests for dashboard browser helpers and localhost server."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.dashboard_browser import (
    DEFAULT_DASHBOARD_HOST,
    DASHBOARD_HTML_PATH,
    ensure_dashboard_server,
    extract_build_version_from_html,
    is_dashboard_port_open,
    open_analysis_dashboard,
    open_or_reload_chrome_incognito,
    open_or_reload_dashboard,
)


class TestDashboardBrowser(unittest.TestCase):
    def tearDown(self):
        import src.dashboard_browser as db

        if db._server is not None:
            db._server.shutdown()
            db._server = None
            db._server_port = None

    @patch('src.dashboard_browser.DASHBOARD_HTML_PATH', Path('/nonexistent/qmst-dashboard.html'))
    def test_ensure_dashboard_server_serves_html_and_version(self):
        html = '<html><body>QMST test</body></html>'
        version = '2026-06-01|report.xlsx|123'
        url = ensure_dashboard_server(html, version, port=19876)
        self.assertTrue(url.startswith(f'http://{DEFAULT_DASHBOARD_HOST}:'))

        import urllib.request

        with urllib.request.urlopen(url, timeout=3) as resp:
            self.assertIn(b'QMST test', resp.read())

        with urllib.request.urlopen(url + 'api/version', timeout=3) as resp:
            payload = json.loads(resp.read().decode())
        self.assertEqual(payload['version'], version)

        url2 = ensure_dashboard_server('<html>v2</html>', 'v2', port=19876)
        self.assertEqual(url.split(':')[-1].rstrip('/'), url2.split(':')[-1].rstrip('/'))

    @patch('src.dashboard_browser._reload_any_dashboard_tab_mac', return_value=True)
    def test_open_or_reload_prefers_reload(self, _reload):
        action = open_or_reload_dashboard('http://127.0.0.1:9876/')
        self.assertEqual(action, 'reloaded')

    @patch('src.dashboard_browser._reload_any_dashboard_tab_mac', return_value=False)
    @patch('src.dashboard_browser._open_chrome_incognito', return_value=True)
    def test_open_or_reload_opens_incognito_when_no_tab(self, _open, _reload):
        from src.dashboard_browser import open_or_reload_dashboard

        action = open_or_reload_dashboard('http://127.0.0.1:9876/')
        self.assertEqual(action, 'opened-incognito')
        _open.assert_called_once()

    def test_dashboard_build_version(self):
        from src.dashboard_browser import dashboard_build_version

        v = dashboard_build_version({'runDate': '01 Jun 2026'}, Path('Enhanced_Stock_Report.xlsx'))
        self.assertTrue(v.startswith('01 Jun 2026|Enhanced_Stock_Report.xlsx|'))

    def test_extract_build_version_from_html(self):
        html = '{"buildVersion":"03 Jun 2026|report.xlsx|99"}'
        self.assertEqual(extract_build_version_from_html(html), '03 Jun 2026|report.xlsx|99')

    def test_api_meta_and_version_from_embedded_build(self):
        html = (
            '<html><script>window.DASHBOARD_DATA='
            '{"buildVersion":"01 Jun 2026|report.xlsx|42"};</script></html>'
        )
        path = DASHBOARD_HTML_PATH
        backup = path.read_text(encoding='utf-8') if path.is_file() else None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding='utf-8')
            import src.dashboard_browser as db

            db._cached_file_version = None
            db._cached_file_mtime = 0.0
            url = ensure_dashboard_server('<html>stale</html>', 'stale', port=19879)
            import urllib.request

            with urllib.request.urlopen(url + 'api/version', timeout=3) as resp:
                payload = json.loads(resp.read().decode())
            self.assertEqual(payload['version'], '01 Jun 2026|report.xlsx|42')
            with urllib.request.urlopen(url + 'api/meta', timeout=3) as resp:
                meta = json.loads(resp.read().decode())
            self.assertIn('repo', meta)
            self.assertIn('htmlPath', meta)
        finally:
            import src.dashboard_browser as db

            db._cached_file_version = None
            db._cached_file_mtime = 0.0
            if backup is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(backup, encoding='utf-8')

    def test_read_dashboard_html_prefers_file(self):
        html = '<html><body>from file</body></html>'
        path = DASHBOARD_HTML_PATH
        backup = path.read_text(encoding='utf-8') if path.is_file() else None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(html, encoding='utf-8')
            url = ensure_dashboard_server('<html>stale</html>', 'stale', port=19878)
            import urllib.request

            with urllib.request.urlopen(url, timeout=3) as resp:
                self.assertIn(b'from file', resp.read())
        finally:
            if backup is None:
                path.unlink(missing_ok=True)
            else:
                path.write_text(backup, encoding='utf-8')

    @patch('src.dashboard_browser.open_or_reload_dashboard', return_value='opened-incognito')
    @patch('src.dashboard_browser.foreign_dashboard_server', return_value=None)
    @patch('src.dashboard_browser.is_dashboard_port_open', return_value=True)
    def test_open_analysis_dashboard_when_server_up(self, _port, _foreign, _open):
        action = open_analysis_dashboard(port=9876)
        self.assertEqual(action, 'opened-incognito')
        _open.assert_called_once_with('http://127.0.0.1:9876/')

    @patch('src.dashboard_browser.open_or_reload_dashboard', return_value='opened-incognito')
    @patch('src.dashboard_browser.foreign_dashboard_server', return_value=None)
    @patch('src.dashboard_browser.is_dashboard_port_open', side_effect=[False, True])
    @patch('src.dashboard_browser.subprocess.Popen')
    def test_open_analysis_dashboard_spawns_server(self, popen, _port, _foreign, _open):
        DASHBOARD_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
        DASHBOARD_HTML_PATH.write_text('<html></html>', encoding='utf-8')
        action = open_analysis_dashboard(port=9876)
        self.assertEqual(action, 'opened-incognito')
        popen.assert_called_once()


    def test_serve_dashboard_script_has_module_repo_root(self):
        text = (REPO_ROOT / 'scripts' / 'serve_dashboard.py').read_text(encoding='utf-8')
        self.assertIn('REPO_ROOT = Path(__file__)', text)
        self.assertNotIn('REPO_ROOT,\n    )', text)


if __name__ == '__main__':
    unittest.main()
