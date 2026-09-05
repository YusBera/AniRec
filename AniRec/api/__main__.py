"""Launch the AniRec API as a supervised local service.

Two callers, one entry point:

* a developer running ``python -m AniRec.api`` for browser work, who wants a
  fixed, memorable port and no ceremony;
* the desktop shell, which spawns this as a child process, needs to be told
  which port the OS actually handed out, and must be able to stop it cleanly.

The second is what shapes this module. Everything the shell needs to know
comes back on stdout as a single line of JSON, because stdout is the one
channel a parent process can read reliably across platforms without agreeing
on a file location first::

    {"ready": true, "port": 51734, "pid": 21044}
    {"ready": false, "error": "already_running"}

The shell reads until it sees that line, then stops reading and talks HTTP.
A failure line is emitted for every startup path that cannot serve, so the
shell shows an error instead of waiting out a timeout on a process that is
never going to answer.

What is deliberately *not* on stdout: the token. The shell generates it and
passes it in, so echoing it back would only widen where it can leak - a
captured log, a crash report, a developer's terminal scrollback.
"""

from __future__ import annotations

import argparse
import json
import logging
import socket
import sys
import threading

import uvicorn

from ..infrastructure.logging_config import close_logger, configure_logging
from ..infrastructure.paths import app_paths
from ..infrastructure.single_instance import InstanceLock, LockHeld
from .app import create_app

# Loopback only, and not configurable. A --host flag would be one typo away
# from publishing a service that holds a MyAnimeList token to the local
# network, and nothing about this application wants to listen off-machine.
HOST = "127.0.0.1"

# 0 asks the OS for any free port. The desktop shell always uses this: a
# fixed port in a shipped product is a fixed target, and two installs or a
# stale process would collide on it.
EPHEMERAL = 0

DEV_PORT = 8770


def _announce(payload: dict[str, object]) -> None:
    """One JSON line, flushed. The shell's entire startup protocol."""
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()


def _bind(port: int) -> socket.socket:
    """Bind before serving so the real port is known before anyone waits.

    uvicorn can be handed an already-bound socket, which removes the race
    between "announce a port" and "actually listen on it". With port 0 there
    is no other way to learn the number without asking the socket.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    sock.bind((HOST, port))
    sock.listen(128)
    return sock


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="AniRec.api")
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=(
            f"TCP port on {HOST}. Defaults to {DEV_PORT} for development; "
            "pass 0 to let the OS choose, which is what the desktop shell does."
        ),
    )
    parser.add_argument(
        "--root-override",
        default=None,
        help="Point the whole service graph at a different data directory.",
    )
    parser.add_argument(
        "--log-level",
        default="info",
        choices=("critical", "error", "warning", "info", "debug"),
    )
    arguments = parser.parse_args(argv)
    port = DEV_PORT if arguments.port is None else arguments.port

    logger = configure_logging(
        root_override=arguments.root_override, logger_name="AniRec.api"
    )
    paths = app_paths(arguments.root_override).ensure_exists()
    lock = InstanceLock(paths.root)

    try:
        lock.acquire()
    except LockHeld as held:
        # Not a crash: the shell can tell the user something useful, and a
        # developer sees why their second terminal refused to start.
        logger.warning("Refusing to start: %s", held)
        _announce({"ready": False, "error": "already_running"})
        close_logger(logger)
        return 3

    try:
        sock = _bind(port)
    except OSError:
        logger.exception("Could not bind %s:%s", HOST, port)
        _announce({"ready": False, "error": "port_unavailable"})
        lock.release()
        close_logger(logger)
        return 4

    bound_port = sock.getsockname()[1]

    try:
        server = _build_server(arguments, sock, logger)
    except Exception:
        # A configuration or service-wiring failure. The traceback goes to
        # the redacted log; the shell gets a stable code and nothing else,
        # for the same reason gui_main shows a generic startup dialog.
        logger.exception("AniRec API startup failed.")
        _announce({"ready": False, "error": "startup_failed"})
        sock.close()
        lock.release()
        close_logger(logger)
        return 1

    _announce_when_ready(server, bound_port)

    try:
        server.run([sock])
        return 0
    except Exception:
        logger.exception("AniRec API stopped unexpectedly.")
        return 1
    finally:
        sock.close()
        lock.release()
        close_logger(logger)


def _build_server(arguments, sock: socket.socket, logger: logging.Logger) -> uvicorn.Server:
    """Wire the app, including the hook that lets a request stop the server."""
    # Set after the Server exists; the route closes over this list so the
    # callable can be handed to create_app before the server it controls has
    # been constructed.
    holder: list[uvicorn.Server] = []

    def request_shutdown() -> None:
        if holder:
            # The documented way to stop a uvicorn Server from inside a
            # handler: the serving loop notices between iterations, finishes
            # in-flight responses (this one included) and runs the ASGI
            # lifespan shutdown before the process exits.
            holder[0].should_exit = True
            logger.info("Shutdown requested over HTTP.")

    app = create_app(
        root_override=arguments.root_override,
        on_shutdown_requested=request_shutdown,
    )
    config = uvicorn.Config(
        app,
        log_level=arguments.log_level,
        # The socket is already bound and passed to run(); these are recorded
        # for uvicorn's own logging only.
        host=HOST,
        port=sock.getsockname()[1],
        # Access logs on a service that receives a request per keystroke of
        # filtering would be noise, and the useful events are already logged
        # by the application.
        access_log=False,
    )
    server = uvicorn.Server(config)
    holder.append(server)
    return server


def _announce_when_ready(server: uvicorn.Server, port: int) -> None:
    """Emit the ready line once uvicorn is actually serving.

    The socket is already listening by this point, so a client that connects
    the moment it reads this line will be accepted rather than refused. The
    wait is for uvicorn's own startup - lifespan hooks, worker setup - so
    that "ready" means the app can answer, not merely that a port is open.
    """

    def watch() -> None:
        while not server.started and not getattr(server, "should_exit", False):
            if not _sleep(0.02):
                return
        _announce({"ready": True, "port": port, "pid": _pid()})

    threading.Thread(target=watch, name="AniRecApiReady", daemon=True).start()


def _sleep(seconds: float) -> bool:
    import time

    time.sleep(seconds)
    return True


def _pid() -> int:
    import os

    return os.getpid()


if __name__ == "__main__":
    raise SystemExit(main())
