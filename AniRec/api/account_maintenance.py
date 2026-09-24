"""Deleting accounts and pruning abandoned guests, on disk (D-021).

``AccountService.delete_account`` makes a deletion final for the reader in one
transaction; this module does the steps around it that involve the operation
registry and the filesystem, and the sweep that finishes whatever a failure
left behind. See ``docs/ACCOUNTS.md``, "Account management".
"""

from __future__ import annotations

import logging
import shutil
import threading
import time
from pathlib import Path

from ..infrastructure.paths import profile_dir, profiles_dir
from ..services.account_service import AccountError, Deletion, is_web_import
from .container import ApiContainer
from .operations import OperationRegistry

LOGGER = logging.getLogger(__name__)

# An unowned web list untouched this long is a write that raced a deletion
# (an import in progress is owned within milliseconds of its directory).
STRAY_AGE_SECONDS = 3600
SWEEP_INTERVAL_SECONDS = 3600


class AccountMaintenance:
    def __init__(self, services: ApiContainer, operations: OperationRegistry) -> None:
        self._services = services
        self._operations = operations
        self._root = services.profiles.root_override
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # -- deleting an account -------------------------------------------------------

    def delete_account(self, account_id: str) -> Deletion:
        """Close the lists, delete the account, then remove the directories."""
        accounts = self._services.accounts
        owned = accounts.owned_profile_ids(account_id)
        # Step 1: no operation may start on these lists from here on.
        if not self._operations.close(owned):
            raise AccountError("operation-running")
        try:
            # Step 2: final for the reader, in one transaction. The desktop
            # tool's active list is released, never deleted.
            deletion = accounts.delete_account(account_id, keep=self._desktop_active())
        except BaseException:
            self._operations.reopen(owned)
            raise
        self._operations.reopen(deletion.released)
        # Step 3: whatever fails here stays pending for the sweep.
        self._remove(deletion.pending)
        return deletion

    def _desktop_active(self) -> tuple[str, ...]:
        active = self._services.profiles.desktop_active_profile_id()
        return () if active is None else (active,)

    def _remove(self, profile_ids) -> None:
        for profile_id in profile_ids:
            try:
                directory = profile_dir(profile_id, self._root)
                if directory.exists():
                    shutil.rmtree(directory)
                self._services.tokens.delete(profile_id)
                self._services.accounts.deletion_done(profile_id)
            except (OSError, ValueError, AccountError):
                # Kept pending; the sweep tries again. Logged without the
                # reader's identity: the id is a server-made name.
                LOGGER.warning("A deleted list's files could not be removed yet; will retry.")

    # -- the sweep -----------------------------------------------------------------

    def sweep(self) -> None:
        """Finish pending deletions, remove stray web lists, prune guests."""
        accounts = self._services.accounts
        try:
            pending = accounts.pending_deletions()
            self._operations.close(pending)
            self._remove(pending)
            self._remove_strays()
            if accounts.claim_prune_run():
                for guest_id, _lists in accounts.prunable_guests():
                    try:
                        self.delete_account(guest_id)
                    except AccountError:
                        continue   # a busy list: skip this guest whole, retry next run
        except (AccountError, OSError):
            LOGGER.warning("Account maintenance could not run; will retry.")

    def _remove_strays(self) -> None:
        root = profiles_dir(self._root)
        if not root.is_dir():
            return
        now = time.time()
        accounts = self._services.accounts
        for directory in root.iterdir():
            name = directory.name
            if not directory.is_dir() or not is_web_import(name):
                continue
            if accounts.is_owned(name) or accounts.is_pending(name):
                continue
            if now - _last_touched(directory) < STRAY_AGE_SECONDS:
                continue
            if self._operations.close((name,)):
                self._remove((name,))

    # -- the background thread ------------------------------------------------------

    def start(self) -> None:
        if self._thread is not None:
            return

        def loop() -> None:
            while not self._stop.is_set():
                self.sweep()
                self._stop.wait(SWEEP_INTERVAL_SECONDS)

        self._thread = threading.Thread(target=loop, name="AniRecAccountMaintenance", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None


def _last_touched(directory: Path) -> float:
    newest = directory.stat().st_mtime
    for path in directory.rglob("*"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue
    return newest
