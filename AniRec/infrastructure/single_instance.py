"""A defense-in-depth guard against two API processes sharing one profile.

The primary guarantee that only one AniRec process ever runs belongs to the
desktop shell: Tauri's single-instance plugin refuses to launch a second app
window at all, and the shell owns the one Python child it spawns for the
life of that window. This module exists for the paths that guarantee does
not cover - chiefly, a developer running ``python -m AniRec.api`` by hand
while a packaged build (or another manual run) is already using the same
profile directory. Two writers to the same JSON files would still be safe
individually (``json_storage`` writes atomically), but two processes racing
to answer "what is the current recommendation state" can each be right and
still disagree with each other, which is a worse failure than refusing to
start.

The lock is a small JSON file naming the holding process's PID. Liveness is
checked by asking the operating system whether that PID still refers to a
running process - not by trusting the file's mere existence, which would
turn an unclean shutdown into a permanent refusal to start.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


LOCK_FILENAME = "api.lock"


@dataclass(frozen=True)
class LockHeld(Exception):
    """Raised by :func:`acquire` when a live process already holds the lock."""

    holder_pid: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"AniRec API is already running (pid {self.holder_pid})."


def lock_path(root: Path) -> Path:
    return root / LOCK_FILENAME


def is_process_alive(pid: int) -> bool:
    """Ask the OS, not the filesystem, whether ``pid`` is a live process."""
    if pid <= 0:
        return False
    if sys.platform == "win32":
        return _is_alive_windows(pid)
    return _is_alive_posix(pid)


def _is_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        # Exists, owned by someone else - still alive.
        return True
    return True


def _is_alive_windows(pid: int) -> bool:
    import ctypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong(0)
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


class InstanceLock:
    """Held for the life of one API process; released on clean shutdown.

    Usage::

        lock = InstanceLock(root)
        lock.acquire()  # raises LockHeld if another live process holds it
        try:
            ...
        finally:
            lock.release()
    """

    def __init__(self, root: Path) -> None:
        self._path = lock_path(root)
        self._acquired = False

    def acquire(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        existing = self._read()
        if existing is not None and is_process_alive(existing):
            raise LockHeld(existing)
        self._write(os.getpid())
        self._acquired = True

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            current = self._read()
            # Only remove a lock this process actually owns: a lock file
            # rewritten by a newer process (this one having lost a race, or
            # having been killed and restarted with a stale reference) must
            # not be deleted out from under its real, current owner.
            if current == os.getpid():
                self._path.unlink(missing_ok=True)
        finally:
            self._acquired = False

    def _read(self) -> int | None:
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        pid = payload.get("pid")
        return int(pid) if isinstance(pid, int) else None

    def _write(self, pid: int) -> None:
        # Not the atomic-replace helper in infrastructure.json_storage: this
        # file is transient process state, not durable user data, and does
        # not need the fsync+rename discipline that protects a profile.
        self._path.write_text(json.dumps({"pid": pid}), encoding="utf-8")

    def __enter__(self) -> "InstanceLock":
        self.acquire()
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()
