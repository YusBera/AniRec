from __future__ import annotations

import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pytest

from errors import AuthError, AuthTimeoutError, CancelledError
from infrastructure.oauth_callback import OAuthCallbackServer


def _free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _run_callback_request(path, expected_state="fixture-state"):
    port = _free_port()
    redirect = f"http://127.0.0.1:{port}/callback"
    result = {}

    def wait():
        try:
            result["code"] = OAuthCallbackServer().wait_for_code(
                redirect,
                expected_state,
                timeout_seconds=2,
            )
        except Exception as error:
            result["error"] = error

    thread = threading.Thread(target=wait, daemon=True)
    thread.start()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        try:
            with urlopen(f"http://127.0.0.1:{port}{path}", timeout=0.2):
                break
        except HTTPError:
            break
        except URLError:
            time.sleep(0.02)
    thread.join(timeout=2)
    assert not thread.is_alive()
    return result


def test_callback_validates_path_state_and_returns_code():
    success = _run_callback_request(
        "/callback?code=fake-code&state=fixture-state"
    )
    assert success == {"code": "fake-code"}
    assert isinstance(
        _run_callback_request("/wrong?code=fake-code&state=fixture-state")["error"],
        AuthError,
    )
    assert isinstance(
        _run_callback_request("/callback?code=fake-code&state=wrong")["error"],
        AuthError,
    )


def test_callback_timeout_cancellation_and_port_in_use_cleanup():
    port = _free_port()
    redirect = f"http://127.0.0.1:{port}/callback"
    with pytest.raises(AuthTimeoutError):
        OAuthCallbackServer().wait_for_code(
            redirect,
            "state",
            timeout_seconds=0.05,
        )

    class Cancelled:
        is_cancelled = True

    with pytest.raises(CancelledError):
        OAuthCallbackServer().wait_for_code(
            redirect,
            "state",
            timeout_seconds=1,
            cancellation=Cancelled(),
        )

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1", port))
        occupied.listen(1)
        with pytest.raises(AuthError):
            OAuthCallbackServer().wait_for_code(redirect, "state", timeout_seconds=0.1)

    # All prior paths released the port; a new server can bind and time out normally.
    with pytest.raises(AuthTimeoutError):
        OAuthCallbackServer().wait_for_code(redirect, "state", timeout_seconds=0.05)
