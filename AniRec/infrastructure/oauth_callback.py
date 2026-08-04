"""Bounded local OAuth callback server with path/state validation."""

from __future__ import annotations

import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

try:
    from ..errors import AuthError, AuthTimeoutError, CancelledError
except ImportError:  # Compatibility with the S01 top-level import path.
    from errors import AuthError, AuthTimeoutError, CancelledError


class OAuthCallbackServer:
    def __init__(self, *, server_factory=HTTPServer, monotonic=time.monotonic) -> None:
        self._server_factory = server_factory
        self._monotonic = monotonic

    def wait_for_code(
        self,
        redirect_uri: str,
        expected_state: str,
        *,
        timeout_seconds: float = 180,
        cancellation=None,
    ) -> str:
        parsed = urlparse(redirect_uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8080
        expected_path = parsed.path or "/callback"
        handler = _handler_factory(expected_path, expected_state)
        try:
            server = self._server_factory((host, port), handler)
        except OSError as error:
            raise AuthError("OAuth callback port could not be opened.") from error

        server.timeout = min(max(timeout_seconds, 0.05), 0.2)
        deadline = self._monotonic() + max(timeout_seconds, 0)
        try:
            while self._monotonic() < deadline:
                if _is_cancelled(cancellation):
                    raise CancelledError("OAuth callback cancelled.")
                server.handle_request()
                callback_error = getattr(server, "callback_error", None)
                if callback_error is not None:
                    raise callback_error
                code = getattr(server, "authorization_code", None)
                if code:
                    return code
            raise AuthTimeoutError("OAuth callback timed out.")
        finally:
            server.server_close()


def _handler_factory(expected_path: str, expected_state: str):
    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            if parsed.path != expected_path:
                self.server.callback_error = AuthError("OAuth callback path did not match.")
                self._respond(404, b"Invalid callback path.")
                return
            state = params.get("state", [None])[0]
            if state != expected_state:
                self.server.callback_error = AuthError("OAuth callback state did not match.")
                self._respond(400, b"Invalid authorization state.")
                return
            code = params.get("code", [None])[0]
            if not code:
                self.server.callback_error = AuthError("OAuth callback code was missing.")
                self._respond(400, b"Authorization code missing.")
                return
            self.server.authorization_code = code
            self._respond(200, b"Authorization received. You can close this tab.")

        def _respond(self, status: int, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            return

    return OAuthCallbackHandler


def _is_cancelled(cancellation) -> bool:
    if cancellation is None:
        return False
    value = getattr(cancellation, "is_cancelled", cancellation)
    return bool(value() if callable(value) else value)
