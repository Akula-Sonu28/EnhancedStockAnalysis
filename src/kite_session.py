"""Kite Connect session helpers: validate, renew, and semi-automatic login.

Fully unattended login is not supported by Zerodha for Personal apps (no
refresh_token; daily 6 AM IST expiry). This module:

1. Reuses a valid ``KITE_ACCESS_TOKEN`` if still active.
2. Renews via ``KITE_REFRESH_TOKEN`` when present (approved platforms only).
3. ``--auto`` login: opens browser + local redirect listener (no paste).

Redirect URL on your Kite app must match the listener, e.g.
``http://127.0.0.1:8765/`` (set ``KITE_REDIRECT_PORT=8765`` in .env).
"""
from __future__ import annotations

import logging
import os
import re
import socket
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"


def _update_env(key: str, value: str) -> None:
    line_re = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    new_line = f"{key}={value}"
    text = _ENV_PATH.read_text(encoding="utf-8") if _ENV_PATH.exists() else ""
    text = line_re.sub(new_line, text) if line_re.search(text) else text.rstrip() + "\n" + new_line + "\n"
    _ENV_PATH.write_text(text, encoding="utf-8")
    os.environ[key] = value


def _credentials() -> tuple[str, str, str]:
    api_key = os.environ.get("KITE_API_KEY", "").strip()
    api_secret = os.environ.get("KITE_API_SECRET", "").strip()
    access = os.environ.get("KITE_ACCESS_TOKEN", "").strip()
    return api_key, api_secret, access


def _kite(api_key: str, access_token: str | None = None):
    from kiteconnect import KiteConnect

    kite = KiteConnect(api_key=api_key)
    if access_token:
        kite.set_access_token(access_token)
    return kite


def token_is_valid(api_key: str, access_token: str) -> bool:
    try:
        _kite(api_key, access_token).profile()
        return True
    except Exception:
        return False


def renew_from_refresh(api_key: str, api_secret: str, refresh_token: str) -> str:
    kite = _kite(api_key)
    resp = kite.renew_access_token(refresh_token=refresh_token, api_secret=api_secret)
    access = resp.get("access_token") or ""
    if not access:
        raise RuntimeError("renew_access_token returned no access_token")
    _update_env("KITE_ACCESS_TOKEN", access)
    if resp.get("refresh_token"):
        _update_env("KITE_REFRESH_TOKEN", resp["refresh_token"])
    return access


def exchange_request_token(api_key: str, api_secret: str, request_token: str) -> dict[str, Any]:
    kite = _kite(api_key)
    session = kite.generate_session(request_token, api_secret=api_secret)
    access = session.get("access_token", "")
    if access:
        _update_env("KITE_ACCESS_TOKEN", access)
    refresh = session.get("refresh_token")
    if refresh:
        _update_env("KITE_REFRESH_TOKEN", refresh)
        logger.info("Refresh token saved (renewal supported until revoked).")
    return session


def _capture_request_token_via_browser(api_key: str, port: int, timeout_s: int = 180) -> str:
    login_url = _kite(api_key).login_url()
    captured: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            qs = parse_qs(urlparse(self.path).query)
            token = (qs.get("request_token") or [""])[0]
            status = (qs.get("status") or [""])[0]
            if token:
                captured["request_token"] = token
                body = b"<html><body><h2>Kite login OK.</h2><p>You can close this tab.</p></body></html>"
                self.send_response(200)
            else:
                body = f"<html><body><h2>Login failed</h2><p>status={status}</p></body></html>".encode()
                self.send_response(400)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.timeout = 1
    print(f"Listening on http://127.0.0.1:{port}/ for redirect...")
    print(f"If login fails, set Kite app Redirect URL to: http://127.0.0.1:{port}/")
    print(f"Opening browser...\n{login_url}\n")
    webbrowser.open(login_url)

    import time

    deadline = time.time() + timeout_s
    while time.time() < deadline and "request_token" not in captured:
        server.handle_request()
    server.server_close()

    token = captured.get("request_token", "")
    if not token:
        raise TimeoutError(
            f"No request_token within {timeout_s}s. "
            f"Ensure Kite Redirect URL is http://127.0.0.1:{port}/"
        )
    return token


def ensure_access_token(
    *,
    auto_browser: bool = False,
    request_token: str | None = None,
) -> str:
    """Return a valid access token, refreshing or logging in if needed."""
    api_key, api_secret, access = _credentials()
    if not api_key or not api_secret:
        raise RuntimeError("Set KITE_API_KEY and KITE_API_SECRET in .env")

    if access and token_is_valid(api_key, access):
        return access

    refresh = os.environ.get("KITE_REFRESH_TOKEN", "").strip()
    if refresh:
        try:
            access = renew_from_refresh(api_key, api_secret, refresh)
            if token_is_valid(api_key, access):
                print("[KITE] Access token renewed from refresh_token.")
                return access
        except Exception as exc:
            logger.warning("Refresh token renewal failed: %s", exc)

    if request_token:
        exchange_request_token(api_key, api_secret, request_token)
        access = os.environ.get("KITE_ACCESS_TOKEN", "")
        if access and token_is_valid(api_key, access):
            return access
        raise RuntimeError("request_token exchange failed")

    if auto_browser or os.environ.get("KITE_AUTO_LOGIN", "").lower() in ("1", "true", "yes"):
        port = int(os.environ.get("KITE_REDIRECT_PORT", "8765"))
        req = _capture_request_token_via_browser(api_key, port)
        exchange_request_token(api_key, api_secret, req)
        access = os.environ.get("KITE_ACCESS_TOKEN", "")
        if access and token_is_valid(api_key, access):
            print("[KITE] Logged in via browser redirect.")
            return access
        raise RuntimeError("Browser login completed but token invalid")

    raise RuntimeError(
        "Kite access token missing or expired. Fix one of:\n"
        "  1. python3 scripts/kite_login.py --auto\n"
        "  2. python3 scripts/kite_login.py  (paste request_token)\n"
        "  3. Set KITE_ACCESS_TOKEN after manual login\n"
        "Personal apps cannot auto-login without browser (SEBI rule)."
    )
