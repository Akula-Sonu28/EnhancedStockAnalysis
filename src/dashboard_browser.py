"""Serve QMST dashboard over localhost and open/reload Chrome incognito."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD_HTML_PATH = REPO_ROOT / 'frontend' / 'qmst-dashboard.html'
SERVE_DASHBOARD_SCRIPT = REPO_ROOT / 'scripts' / 'serve_dashboard.py'
DEFAULT_DASHBOARD_PORT = 9876
DEFAULT_DASHBOARD_HOST = '127.0.0.1'

_state = {'html': '', 'version': ''}
_state_lock = threading.Lock()
_server: Optional[ThreadingHTTPServer] = None
_server_port: Optional[int] = None


def _read_dashboard_html() -> str:
    if DASHBOARD_HTML_PATH.is_file():
        return DASHBOARD_HTML_PATH.read_text(encoding='utf-8')
    with _state_lock:
        return _state['html']


_cached_file_version: Optional[str] = None
_cached_file_mtime: float = 0.0


def extract_build_version_from_html(html: str) -> str:
    import re

    m = re.search(r'"buildVersion"\s*:\s*"([^"]+)"', html)
    return m.group(1) if m else ''


def dashboard_meta() -> dict:
    return {
        'version': _dashboard_version(),
        'repo': str(REPO_ROOT.resolve()),
        'htmlPath': str(DASHBOARD_HTML_PATH.resolve()),
    }


def foreign_dashboard_server(port: int = DEFAULT_DASHBOARD_PORT) -> Optional[str]:
    """If localhost dashboard is another checkout, return its repo path."""
    if not is_dashboard_port_open(port):
        return None
    import urllib.error
    import urllib.request

    url = f'http://{DEFAULT_DASHBOARD_HOST}:{port}/api/meta'
    try:
        with urllib.request.urlopen(url, timeout=1.5) as resp:
            meta = json.loads(resp.read().decode())
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return 'unknown'
    other = str(meta.get('repo') or '').strip()
    if not other:
        return 'unknown'
    try:
        if Path(other).resolve() == REPO_ROOT.resolve():
            return None
    except OSError:
        pass
    return other


def _dashboard_version() -> str:
    global _cached_file_version, _cached_file_mtime
    if DASHBOARD_HTML_PATH.is_file():
        mtime = DASHBOARD_HTML_PATH.stat().st_mtime
        if _cached_file_version and mtime == _cached_file_mtime:
            return _cached_file_version
        try:
            import re as _re
            html = DASHBOARD_HTML_PATH.read_text(encoding='utf-8')
            m = _re.search(r'"buildVersion"\s*:\s*"([^"]+)"', html)
            if m:
                _cached_file_version = m.group(1)
                _cached_file_mtime = mtime
                return _cached_file_version
        except Exception:
            pass
        _cached_file_version = f'{int(mtime)}|{DASHBOARD_HTML_PATH.name}'
        _cached_file_mtime = mtime
        return _cached_file_version
    with _state_lock:
        return _state['version']


class _DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args) -> None:
        return

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == '/api/version':
            body = json.dumps({'version': _dashboard_version()}, separators=(',', ':')).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return

        if path == '/api/meta':
            body = json.dumps(dashboard_meta(), separators=(',', ':')).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)
            return

        if path not in ('/', '/index.html'):
            self.send_error(404)
            return

        html = _read_dashboard_html()
        if not html:
            self.send_error(503, 'Dashboard not ready')
            return
        payload = html.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(payload)


def _bind_server(host: str, port: int) -> Tuple[ThreadingHTTPServer, int]:
    last_err: Optional[OSError] = None
    for candidate in range(port, port + 8):
        try:
            server = ThreadingHTTPServer((host, candidate), _DashboardHandler)
            return server, candidate
        except OSError as err:
            last_err = err
    raise RuntimeError(f'Could not bind dashboard server on {host}:{port}+') from last_err


def ensure_dashboard_server(html: str, version: str, port: int = DEFAULT_DASHBOARD_PORT) -> str:
    """Publish dashboard HTML on localhost; start server once per process."""
    global _server, _server_port
    with _state_lock:
        _state['html'] = html
        _state['version'] = version

    if _server is None:
        server, bound_port = _bind_server(DEFAULT_DASHBOARD_HOST, port)
        thread = threading.Thread(target=server.serve_forever, daemon=True, name='qmst-dashboard')
        thread.start()
        _server = server
        _server_port = bound_port

    return f'http://{DEFAULT_DASHBOARD_HOST}:{_server_port}/'


def _chrome_mac_paths() -> list[Path]:
    paths = [
        Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
        Path.home() / 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    ]
    return [p for p in paths if p.is_file()]


def _reload_browser_tab_mac(app_name: str, url: str) -> bool:
    host = urlparse(url).netloc
    if not host:
        return False
    script = f'''
set targetHost to "{host}"
set found to false
tell application "{app_name}"
    repeat with w in windows
        repeat with t in tabs of w
            if (URL of t as text) contains targetHost then
                reload t
                set index of w to 1
                activate
                set found to true
                exit repeat
            end if
        end repeat
        if found then exit repeat
    end repeat
end tell
return found
'''
    try:
        proc = subprocess.run(
            ['osascript', '-e', script],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.stdout.strip().lower() == 'true'


def _reload_chrome_tab_mac(url: str) -> bool:
    return _reload_browser_tab_mac('Google Chrome', url)


def _reload_safari_tab_mac(url: str) -> bool:
    return _reload_browser_tab_mac('Safari', url)


def _reload_any_dashboard_tab_mac(url: str) -> bool:
    for fn in (_reload_chrome_tab_mac, _reload_safari_tab_mac):
        if fn(url):
            return True
    return False


def _open_chrome_incognito(url: str) -> bool:
    if sys.platform == 'darwin':
        for chrome in _chrome_mac_paths():
            subprocess.Popen(
                [str(chrome), '--incognito', url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        try:
            subprocess.Popen(
                ['open', '-na', 'Google Chrome', '--args', '--incognito', url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
        except OSError:
            return False

    for binary in ('google-chrome', 'google-chrome-stable', 'chromium', 'chromium-browser'):
        exe = shutil.which(binary)
        if exe:
            subprocess.Popen(
                [exe, '--incognito', url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return True
    return False


def open_or_reload_dashboard(url: str) -> str:
    """Reload an open dashboard tab (Chrome/Safari on macOS), or open the URL."""
    if sys.platform == 'darwin' and _reload_any_dashboard_tab_mac(url):
        return 'reloaded'
    if _open_chrome_incognito(url):
        return 'opened-incognito'
    webbrowser.open(url)
    return 'opened'


def open_or_reload_chrome_incognito(url: str) -> str:
    """Backward-compatible alias for open_or_reload_dashboard."""
    return open_or_reload_dashboard(url)


def is_dashboard_port_open(port: int = DEFAULT_DASHBOARD_PORT) -> bool:
    import socket

    try:
        with socket.create_connection((DEFAULT_DASHBOARD_HOST, port), timeout=0.4):
            return True
    except OSError:
        return False


def ensure_persistent_dashboard_server(port: int = DEFAULT_DASHBOARD_PORT) -> str:
    """Return dashboard URL; start detached serve_dashboard.py if not already listening."""
    url = f'http://{DEFAULT_DASHBOARD_HOST}:{port}/'
    foreign = foreign_dashboard_server(port)
    if foreign:
        raise RuntimeError(
            f'Dashboard port {port} is served by another checkout ({foreign}). '
            f'Stop it: kill $(lsof -ti :{port}) then restart from {REPO_ROOT}'
        )
    if is_dashboard_port_open(port):
        return url
    if not SERVE_DASHBOARD_SCRIPT.is_file():
        raise FileNotFoundError(f'Missing {SERVE_DASHBOARD_SCRIPT}')
    if not DASHBOARD_HTML_PATH.is_file():
        raise FileNotFoundError(
            f'Missing {DASHBOARD_HTML_PATH} — build dashboard before opening browser'
        )
    subprocess.Popen(
        [sys.executable, str(SERVE_DASHBOARD_SCRIPT)],
        cwd=str(REPO_ROOT),
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(60):
        if is_dashboard_port_open(port):
            return url
        time.sleep(0.1)
    raise RuntimeError(f'Dashboard server did not start on port {port}')


def open_analysis_dashboard(port: int = DEFAULT_DASHBOARD_PORT) -> str:
    """After analysis: ensure localhost server stays up and open Chrome incognito."""
    url = ensure_persistent_dashboard_server(port)
    action = open_or_reload_dashboard(url)
    browser_note = {
        'reloaded': 'tab reloaded (Chrome or Safari)',
        'opened-incognito': 'Chrome incognito',
        'opened': 'default browser',
    }.get(action, action)
    print(f'[DASH] Browser {action}: {url} ({browser_note})')
    return action


def dashboard_build_version(slim: dict, report_path: Path) -> str:
    run_date = str(slim.get('runDate') or '')
    report_name = report_path.name
    return f'{run_date}|{report_name}|{int(time.time())}'
