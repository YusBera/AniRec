"""The backend must be safe to spawn, discover, and stop from a shell.

These cover the contract the desktop shell depends on, at the level it
actually depends on it: the startup handshake on stdout, the per-launch
token, the refusal to run twice against one profile directory, and a
shutdown that ends the process rather than merely closing a socket.

The subprocess tests launch the real module. They are slower than a
TestClient, and that is the point - a readiness protocol that only works
in-process is not a readiness protocol.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from AniRec.api import create_app  # noqa: E402
from AniRec.api.security import TOKEN_HEADER, generate_token  # noqa: E402
from AniRec.infrastructure.single_instance import (  # noqa: E402
    InstanceLock,
    LockHeld,
    is_process_alive,
)

READY_TIMEOUT = 45.0


# -- the single-instance lock ------------------------------------------------


def test_a_lock_is_held_against_a_second_acquirer(tmp_path):
    first = InstanceLock(tmp_path)
    first.acquire()
    try:
        with pytest.raises(LockHeld):
            InstanceLock(tmp_path).acquire()
    finally:
        first.release()


def test_a_released_lock_can_be_taken_again(tmp_path):
    with InstanceLock(tmp_path):
        pass
    second = InstanceLock(tmp_path)
    second.acquire()
    second.release()


def test_a_stale_lock_from_a_dead_process_does_not_block_startup(tmp_path):
    """An unclean shutdown must not brick the application permanently."""
    # A PID that cannot be live: the maximum is far below this on every
    # platform this ships to.
    (tmp_path / "api.lock").write_text(json.dumps({"pid": 4_000_000_000}), encoding="utf-8")
    lock = InstanceLock(tmp_path)
    lock.acquire()
    lock.release()


def test_a_corrupt_lock_file_is_treated_as_absent(tmp_path):
    (tmp_path / "api.lock").write_text("not json at all", encoding="utf-8")
    lock = InstanceLock(tmp_path)
    lock.acquire()
    lock.release()


def test_release_does_not_delete_a_lock_owned_by_someone_else(tmp_path):
    lock = InstanceLock(tmp_path)
    lock.acquire()
    # A newer process overwrites the file; this one must not remove it.
    (tmp_path / "api.lock").write_text(json.dumps({"pid": os.getpid() + 1}), encoding="utf-8")
    lock.release()
    assert (tmp_path / "api.lock").exists()


def test_liveness_is_asked_of_the_operating_system():
    assert is_process_alive(os.getpid())
    assert not is_process_alive(4_000_000_000)
    assert not is_process_alive(0)
    assert not is_process_alive(-1)


# -- the token ----------------------------------------------------------------


def test_without_a_token_the_api_is_open(tmp_path):
    """Development behaviour is unchanged: no token configured, no gate."""
    with TestClient(create_app(root_override=str(tmp_path))) as client:
        assert client.get("/api/health").status_code == 200


def test_with_a_token_every_api_route_requires_it(tmp_path):
    token = generate_token()
    app = create_app(root_override=str(tmp_path), token=token)
    with TestClient(app) as client:
        for path in ("/api/health", "/api/system/state", "/api/discover/feed"):
            assert client.get(path).status_code == 401, path
            assert (
                client.get(path, headers={TOKEN_HEADER: token}).status_code == 200
            ), path


def test_a_wrong_token_is_refused(tmp_path):
    app = create_app(root_override=str(tmp_path), token=generate_token())
    with TestClient(app) as client:
        response = client.get("/api/health", headers={TOKEN_HEADER: generate_token()})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthorized"


def test_state_mutating_routes_are_covered_too(tmp_path):
    """The routes that matter most for a blind cross-origin write."""
    token = generate_token()
    app = create_app(root_override=str(tmp_path), token=token)
    with TestClient(app) as client:
        assert (
            client.post(
                "/api/discover/feedback",
                json={"profile_id": "someone", "mal_id": 1, "action": "hidden"},
            ).status_code
            == 401
        )
        assert client.post("/api/operations/sync", json={}).status_code == 401
        assert client.post("/api/system/shutdown").status_code == 401


def test_the_schema_is_not_served_when_a_token_is_required(tmp_path):
    app = create_app(root_override=str(tmp_path), token=generate_token())
    with TestClient(app) as client:
        assert client.get("/openapi.json").status_code == 404
        assert client.get("/docs").status_code == 404


def test_tokens_are_unpredictable():
    assert len({generate_token() for _ in range(64)}) == 64
    assert len(generate_token()) >= 32


# -- the shutdown hook ---------------------------------------------------------


def test_the_shutdown_route_invokes_the_launcher_hook(tmp_path):
    called: list[bool] = []
    app = create_app(
        root_override=str(tmp_path), on_shutdown_requested=lambda: called.append(True)
    )
    with TestClient(app) as client:
        assert client.post("/api/system/shutdown").status_code == 202
    assert called == [True]


def test_the_shutdown_route_answers_without_a_hook(tmp_path):
    """A test harness has no uvicorn Server; the route must not require one."""
    with TestClient(create_app(root_override=str(tmp_path))) as client:
        assert client.post("/api/system/shutdown").json() == {"accepted": True}


# -- the real process ----------------------------------------------------------


class Backend:
    """A spawned ``python -m AniRec.api``, read the way the shell reads it."""

    def __init__(self, root, token=None, port=0):
        env = dict(os.environ)
        env.pop("ANIREC_API_TOKEN", None)
        if token:
            env["ANIREC_API_TOKEN"] = token
        self.token = token
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "AniRec.api",
                "--port",
                str(port),
                "--root-override",
                str(root),
                "--log-level",
                "warning",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self.handshake = self._read_handshake()

    def _read_handshake(self) -> dict:
        deadline = time.monotonic() + READY_TIMEOUT
        while time.monotonic() < deadline:
            line = self.process.stdout.readline()
            if line.strip():
                return json.loads(line)
            if self.process.poll() is not None:
                raise AssertionError("backend exited before announcing itself")
        raise AssertionError("backend never announced itself")

    def get(self, path: str, token: str | None = ...) -> int:
        used = self.token if token is ... else token
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.handshake['port']}{path}"
        )
        if used:
            request.add_header(TOKEN_HEADER, used)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def post(self, path: str) -> int:
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.handshake['port']}{path}", method="POST", data=b""
        )
        if self.token:
            request.add_header(TOKEN_HEADER, self.token)
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def close(self):
        if self.process.poll() is None:
            self.process.kill()
        try:
            self.process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            pass


@pytest.fixture()
def backend(tmp_path):
    running = Backend(tmp_path, token=generate_token())
    try:
        yield running
    finally:
        running.close()


def test_the_process_announces_a_usable_port_on_stdout(backend):
    assert backend.handshake["ready"] is True
    assert backend.handshake["port"] > 0
    # Ephemeral: never the development default.
    assert backend.handshake["port"] != 8770
    assert backend.get("/api/health") == 200


def test_the_announced_port_is_bound_to_loopback_only(backend):
    """A service holding a MAL token must not be reachable off-machine."""
    import socket

    port = backend.handshake["port"]
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.settimeout(2)
    # Connecting via the machine's routable address must fail; only 127.0.0.1
    # is listening.
    outward = socket.gethostbyname(socket.gethostname())
    if outward.startswith("127."):
        pytest.skip("host resolves to loopback; nothing to prove")
    with pytest.raises((ConnectionRefusedError, TimeoutError, OSError)):
        probe.connect((outward, port))
    probe.close()


def test_the_spawned_process_enforces_its_token(backend):
    assert backend.get("/api/health", token=None) == 401
    assert backend.get("/api/health", token="wrong-token") == 401


def test_the_token_is_never_echoed_in_the_handshake(backend):
    assert backend.token not in json.dumps(backend.handshake)


def test_a_second_process_refuses_to_share_a_profile_directory(tmp_path):
    first = Backend(tmp_path, token=generate_token())
    try:
        assert first.handshake["ready"] is True
        second = subprocess.run(
            [
                sys.executable,
                "-m",
                "AniRec.api",
                "--port",
                "0",
                "--root-override",
                str(tmp_path),
                "--log-level",
                "warning",
            ],
            capture_output=True,
            text=True,
            timeout=READY_TIMEOUT,
        )
        assert second.returncode == 3
        assert json.loads(second.stdout.strip()) == {
            "ready": False,
            "error": "already_running",
        }
    finally:
        first.close()


def test_a_graceful_shutdown_ends_the_process(backend):
    """Not just "stops answering" - the child must actually exit."""
    assert backend.post("/api/system/shutdown") == 202
    assert backend.process.wait(timeout=30) == 0


def test_a_failed_start_reports_rather_than_hanging(tmp_path):
    """The shell must get an answer even when the port cannot be taken."""
    import socket

    blocker = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    blocker.bind(("127.0.0.1", 0))
    blocker.listen(1)
    taken = blocker.getsockname()[1]
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "AniRec.api",
                "--port",
                str(taken),
                "--root-override",
                str(tmp_path),
                "--log-level",
                "warning",
            ],
            capture_output=True,
            text=True,
            timeout=READY_TIMEOUT,
        )
        assert result.returncode == 4
        assert json.loads(result.stdout.strip())["error"] == "port_unavailable"
        # A traceback must not reach the shell's pipe.
        assert "Traceback" not in result.stdout
    finally:
        blocker.close()
