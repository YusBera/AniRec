from __future__ import annotations

import socket
import threading
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest

import oauth_handler


def test_get_access_token_uses_valid_cached_token(monkeypatch):
    monkeypatch.setattr(oauth_handler.time, "time", lambda: 1_000)
    monkeypatch.setattr(
        oauth_handler,
        "load_token_from_file",
        lambda: {"access_token": "fake-access-token", "expires_at": 2_000},
    )
    monkeypatch.setattr(
        oauth_handler,
        "refresh_access_token",
        lambda _token: pytest.fail("valid token must not refresh"),
    )
    monkeypatch.setattr(
        oauth_handler,
        "initiate_oauth_flow",
        lambda: pytest.fail("valid token must not start OAuth"),
    )

    assert oauth_handler.get_access_token() == "fake-access-token"


def test_get_access_token_refreshes_expired_token(monkeypatch):
    monkeypatch.setattr(oauth_handler.time, "time", lambda: 2_000)
    monkeypatch.setattr(
        oauth_handler,
        "load_token_from_file",
        lambda: {
            "access_token": "fake-expired-token",
            "refresh_token": "fake-refresh-token",
            "expires_at": 1_000,
        },
    )
    monkeypatch.setattr(
        oauth_handler,
        "refresh_access_token",
        lambda token: "fake-refreshed-token" if token == "fake-refresh-token" else None,
    )

    assert oauth_handler.get_access_token() == "fake-refreshed-token"


@pytest.mark.parametrize("token_data", [None, {"access_token": "expired", "expires_at": 0}])
def test_get_access_token_falls_back_to_oauth(monkeypatch, token_data):
    monkeypatch.setattr(oauth_handler.time, "time", lambda: 1_000)
    monkeypatch.setattr(oauth_handler, "load_token_from_file", lambda: token_data)
    monkeypatch.setattr(oauth_handler, "initiate_oauth_flow", lambda: "fake-oauth-token")
    assert oauth_handler.get_access_token() == "fake-oauth-token"


def test_token_round_trip_and_expiration_use_isolated_temp_file(monkeypatch, system_temp_dir):
    token_path = system_temp_dir / "tokens" / "fixture-token.json"
    monkeypatch.setenv("MAL_TOKEN_FILE", str(token_path))
    monkeypatch.setattr(oauth_handler.time, "time", lambda: 1_000)

    token_data = oauth_handler._add_expiration(
        {
            "access_token": "fake-access-token",
            "refresh_token": "fake-refresh-token",
            "expires_in": 3_600,
        }
    )
    oauth_handler.save_token_to_file(token_data)

    assert token_data["expires_at"] == 4_540
    assert oauth_handler.load_token_from_file() == token_data
    assert token_path.is_file()


def _unused_local_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def test_local_callback_captures_code_in_isolated_server():
    port = _unused_local_port()
    redirect_uri = f"http://127.0.0.1:{port}/callback"
    result = {}

    thread = threading.Thread(
        target=lambda: result.setdefault(
            "code", oauth_handler.start_http_server(redirect_uri)
        ),
        daemon=True,
    )
    thread.start()

    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            with urlopen(
                f"http://127.0.0.1:{port}/fixture?code=fake-authorization-code",
                timeout=0.25,
            ) as response:
                assert response.status == 200
                break
        except URLError:
            time.sleep(0.02)
    else:
        pytest.fail("fixture callback server did not become ready")

    thread.join(timeout=2)
    assert not thread.is_alive()
    assert result["code"] == "fake-authorization-code"
