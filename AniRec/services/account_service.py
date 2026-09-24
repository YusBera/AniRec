"""AniRec accounts: who owns an import, and the sessions that prove it (D-021).

An account is identified by an ID this service assigns. A MyAnimeList username
or ID is never an account key: it only names a public list that one account
imported, and two accounts that import the same list own two separate imports.
See ``docs/ACCOUNTS.md`` for the design, its limits and the phase plan.

Everything lives in ``config/accounts.sqlite3`` (standard-library ``sqlite3``,
one short ``BEGIN IMMEDIATE`` transaction per change, WAL). Passwords are
hashed with the standard library's scrypt; session cookies are stored only as
SHA-256 digests. Neither a password, a hash nor a session token is ever logged
or returned.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
import threading
import time
import unicodedata
from collections import deque
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..errors import AniRecError
from ..infrastructure.paths import config_dir


SESSION_COOKIE = "anirec_session"
SESSION_LIFETIME = timedelta(days=30)
# A used session is extended at most this often, so reads do not turn into a
# write on every request.
SESSION_TOUCH_INTERVAL = timedelta(hours=1)
PASSWORD_MIN = 8
PASSWORD_MAX = 256
EMAIL_MAX = 254
FAILURE_LIMIT = 5
FAILURE_WINDOW = timedelta(minutes=15)
# Process-wide caps (docs/ACCOUNTS.md): failures across all emails per minute,
# new accounts (guest or registered) per hour.
GLOBAL_FAILURES_PER_MINUTE = 60
NEW_ACCOUNTS_PER_HOUR = 30

# scrypt cost: N = 2**15, r = 8, p = 1 needs 32 MiB, which is exactly the
# default ceiling; maxmem leaves headroom for OpenSSL's own overhead.
_SCRYPT_LOG_N = 15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_MAXMEM = 64 * 1024 * 1024
# At most two hashes at once: each holds 32 MiB, and sign-in is unauthenticated.
_HASH_SLOTS = threading.BoundedSemaphore(2)
_EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


class AccountError(AniRecError):
    """A refusal the web client words for the reader, by ``reason``."""

    code = "account_error"
    user_title = "Account problem"
    safe_description = "AniRec could not complete that account request."
    suggested_solution = "Check the details and try again."

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Account:
    account_id: str
    kind: str  # "guest" or "registered"
    email: str | None
    active_profile_id: str | None

    @property
    def registered(self) -> bool:
        return self.kind == "registered"


@dataclass(frozen=True)
class SignedIn:
    """An account and the fresh session token that now names it."""

    account: Account
    token: str
    # Imports a guest brought with them when signing in to this account.
    moved_profile_ids: tuple[str, ...] = ()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _scrypt(password: str, salt: bytes, log_n: int, r: int, p: int) -> bytes:
    if not _HASH_SLOTS.acquire(blocking=False):
        raise AccountError("busy")
    try:
        return hashlib.scrypt(
            unicodedata.normalize("NFKC", password).encode("utf-8"), salt=salt,
            n=2**log_n, r=r, p=p, maxmem=_SCRYPT_MAXMEM, dklen=32,
        )
    finally:
        _HASH_SLOTS.release()


def hash_password(password: str, *, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    key = _scrypt(password, salt, _SCRYPT_LOG_N, _SCRYPT_R, _SCRYPT_P)
    return f"scrypt${_SCRYPT_LOG_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, log_n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt" or int(log_n) > 20:
            return False
        key = _scrypt(password, base64.b64decode(salt), int(log_n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(key, base64.b64decode(expected))


# Checked when the email is unknown, so an unknown and a known email take the
# same time to refuse. Computed lazily: importing this module must stay cheap.
_DUMMY: list[str] = []


def _dummy_hash() -> str:
    if not _DUMMY:
        _DUMMY.append(hash_password("anirec-dummy-password", salt=b"\0" * 16))
    return _DUMMY[0]


def normalize_email(value: str) -> str:
    email = str(value or "").strip().casefold()
    if len(email) > EMAIL_MAX or not _EMAIL.fullmatch(email):
        raise AccountError("invalid-email")
    return email


def _check_password(password: str) -> str:
    if not isinstance(password, str) or len(password) < PASSWORD_MIN:
        raise AccountError("weak-password")
    if len(password) > PASSWORD_MAX:
        raise AccountError("password-too-long")
    return password


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_import_id() -> str:
    """A server-assigned import directory name; never derived from MAL."""
    return "imp_" + secrets.token_hex(16)


class RateWindow:
    """At most ``limit`` events per ``seconds``, process-wide."""

    def __init__(self, limit: int, seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._seconds = seconds
        self._clock = clock
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def _trim(self, now: float) -> None:
        while self._events and now - self._events[0] >= self._seconds:
            self._events.popleft()

    def full(self) -> bool:
        with self._lock:
            self._trim(self._clock())
            return len(self._events) >= self._limit

    def take(self) -> bool:
        """Record one event; ``False`` (and nothing recorded) when full."""
        with self._lock:
            now = self._clock()
            self._trim(now)
            if len(self._events) >= self._limit:
                return False
            self._events.append(now)
            return True


_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('guest', 'registered')),
    email TEXT UNIQUE,
    password_hash TEXT,
    active_profile_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_account ON sessions(account_id);
CREATE TABLE IF NOT EXISTS profile_owners (
    profile_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(account_id),
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS profile_owners_account ON profile_owners(account_id);
CREATE TABLE IF NOT EXISTS login_failures (
    email TEXT PRIMARY KEY,
    count INTEGER NOT NULL,
    last_failed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS installation (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class AccountService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        clock: Callable[[], datetime] = _utc_now,
        new_accounts: RateWindow | None = None,
        failures: RateWindow | None = None,
    ) -> None:
        self._path = config_dir(root_override) / "accounts.sqlite3"
        self._clock = clock
        self._new_accounts = new_accounts or RateWindow(NEW_ACCOUNTS_PER_HOUR, 3600)
        self._failures = failures or RateWindow(GLOBAL_FAILURES_PER_MINUTE, 60)
        self._ready = False
        self._ready_lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    # -- storage --------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._path, timeout=10, isolation_level=None)
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        if not self._ready:
            with self._ready_lock:
                if not self._ready:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.executescript(_SCHEMA)
                    self._ready = True
        return conn

    def _transaction(self) -> "_Transaction":
        return _Transaction(self._connect())

    def _now(self) -> datetime:
        return self._clock().astimezone(timezone.utc)

    @staticmethod
    def _account(row) -> Account | None:
        if row is None:
            return None
        return Account(account_id=row[0], kind=row[1], email=row[2], active_profile_id=row[3])

    def _load(self, conn, account_id: str) -> Account | None:
        return self._account(conn.execute(
            "SELECT account_id, kind, email, active_profile_id FROM accounts WHERE account_id=?",
            (account_id,),
        ).fetchone())

    def _insert_account(self, conn, kind: str, email: str | None = None, password_hash: str | None = None) -> str:
        account_id = "acc_" + secrets.token_hex(16)
        now = self._now().isoformat()
        conn.execute(
            "INSERT INTO accounts(account_id, kind, email, password_hash, created_at, updated_at) VALUES (?,?,?,?,?,?)",
            (account_id, kind, email, password_hash, now, now),
        )
        return account_id

    def _new_session(self, conn, account_id: str) -> str:
        token = secrets.token_urlsafe(32)
        now = self._now()
        conn.execute(
            "INSERT INTO sessions(token_hash, account_id, created_at, expires_at, last_seen_at) VALUES (?,?,?,?,?)",
            (_token_hash(token), account_id, now.isoformat(), (now + SESSION_LIFETIME).isoformat(), now.isoformat()),
        )
        return token

    def _session_account_locked(self, conn, token: str | None) -> Account | None:
        if not token or len(token) > 200:
            return None
        row = conn.execute(
            "SELECT account_id, expires_at FROM sessions WHERE token_hash=?", (_token_hash(token),)
        ).fetchone()
        if row is None or datetime.fromisoformat(row[1]) <= self._now():
            return None
        return self._load(conn, row[0])

    # -- sessions -------------------------------------------------------------

    def account_for_session(self, token: str | None) -> Account | None:
        """The account a session cookie names, or ``None`` for no valid session."""
        if not token or len(token) > 200:
            return None
        digest = _token_hash(token)
        now = self._now()
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT account_id, expires_at, last_seen_at FROM sessions WHERE token_hash=?", (digest,)
            ).fetchone()
            if row is None:
                return None
            if datetime.fromisoformat(row[1]) <= now:
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
                return None
            if now - datetime.fromisoformat(row[2]) >= SESSION_TOUCH_INTERVAL:
                conn.execute(
                    "UPDATE sessions SET last_seen_at=?, expires_at=? WHERE token_hash=?",
                    (now.isoformat(), (now + SESSION_LIFETIME).isoformat(), digest),
                )
            return self._load(conn, row[0])

    def sign_out(self, token: str | None) -> None:
        if not token or len(token) > 200:
            return
        with self._transaction() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))

    def create_guest(self) -> SignedIn:
        if not self._new_accounts.take():
            raise AccountError("busy")
        with self._transaction() as conn:
            account_id = self._insert_account(conn, "guest")
            token = self._new_session(conn, account_id)
            return SignedIn(self._load(conn, account_id), token)

    # -- registration and sign-in ----------------------------------------------

    def register(self, email: str, password: str, *, current_token: str | None = None) -> SignedIn:
        """Create a registered account, or upgrade the current guest one.

        Upgrading keeps the guest's account ID, so its imports and saved
        decisions stay exactly where they are. Every earlier session of that
        account ends, so a cookie planted before registering reaches nothing.
        """
        email = normalize_email(email)
        _check_password(password)
        with self._transaction() as conn:
            current = self._session_account_locked(conn, current_token)
            if current is not None and current.registered:
                raise AccountError("already-signed-in")
            if conn.execute("SELECT 1 FROM accounts WHERE email=?", (email,)).fetchone():
                raise AccountError("email-taken")
        if current is None and not self._new_accounts.take():
            raise AccountError("busy")
        password_hash = hash_password(password)   # slow: outside the write lock
        with self._transaction() as conn:
            # Re-checked under the lock: another request may have taken the
            # email, or registered this guest, while the hash was computed.
            if conn.execute("SELECT 1 FROM accounts WHERE email=?", (email,)).fetchone():
                raise AccountError("email-taken")
            current = self._session_account_locked(conn, current_token)
            now = self._now().isoformat()
            if current is not None and current.kind == "guest":
                account_id = current.account_id
                conn.execute(
                    "UPDATE accounts SET kind='registered', email=?, password_hash=?, updated_at=? "
                    "WHERE account_id=? AND kind='guest'",
                    (email, password_hash, now, account_id),
                )
                conn.execute("DELETE FROM sessions WHERE account_id=?", (account_id,))
            elif current is not None:
                raise AccountError("already-signed-in")
            else:
                account_id = self._insert_account(conn, "registered", email, password_hash)
            token = self._new_session(conn, account_id)
            return SignedIn(self._load(conn, account_id), token)

    def sign_in(self, email: str, password: str, *, current_token: str | None = None) -> SignedIn:
        """Check the password; bring a guest's imports along (docs/ACCOUNTS.md)."""
        if not isinstance(password, str) or len(password) > PASSWORD_MAX:
            raise AccountError("wrong-credentials")
        try:
            email = normalize_email(email)
        except AccountError:
            raise AccountError("wrong-credentials") from None
        if self._failures.full():
            raise AccountError("too-many-attempts")
        now = self._now()
        # The attempt is counted before the password is checked, in one
        # locked transaction, so parallel guesses cannot all see a low count.
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT count, last_failed_at FROM login_failures WHERE email=?", (email,)
            ).fetchone()
            fresh = row is None or now - datetime.fromisoformat(row[1]) >= FAILURE_WINDOW
            if not fresh and row[0] >= FAILURE_LIMIT:
                raise AccountError("too-many-attempts")
            conn.execute(
                "INSERT INTO login_failures(email, count, last_failed_at) VALUES (?,?,?) "
                "ON CONFLICT(email) DO UPDATE SET count=excluded.count, last_failed_at=excluded.last_failed_at",
                (email, 1 if fresh else row[0] + 1, now.isoformat()),
            )
            account = conn.execute(
                "SELECT account_id, password_hash FROM accounts WHERE email=? AND kind='registered'", (email,)
            ).fetchone()
        # Hashing happens outside the write lock: it is the slow part. An
        # unknown email is checked against a dummy hash to take the same time.
        valid = verify_password(password, account[1] if account else _dummy_hash()) and account is not None
        if not valid:
            self._failures.take()
            raise AccountError("wrong-credentials")
        with self._transaction() as conn:
            conn.execute("DELETE FROM login_failures WHERE email=?", (email,))
            account_id = account[0]
            moved: tuple[str, ...] = ()
            current = self._session_account_locked(conn, current_token)
            if current is not None and current.kind == "guest" and current.account_id != account_id:
                # Deleting the guest also ends every session it had.
                moved = self._move_guest_locked(conn, current, account_id)
            elif current_token:
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(current_token),))
            token = self._new_session(conn, account_id)
            return SignedIn(self._load(conn, account_id), token, moved)

    def _move_guest_locked(self, conn, guest: Account, account_id: str) -> tuple[str, ...]:
        moved = tuple(r[0] for r in conn.execute(
            "SELECT profile_id FROM profile_owners WHERE account_id=? ORDER BY created_at", (guest.account_id,)
        ))
        conn.execute("UPDATE profile_owners SET account_id=? WHERE account_id=?", (account_id, guest.account_id))
        target = self._load(conn, account_id)
        if target.active_profile_id is None and guest.active_profile_id in moved:
            conn.execute("UPDATE accounts SET active_profile_id=? WHERE account_id=?", (guest.active_profile_id, account_id))
        conn.execute("DELETE FROM accounts WHERE account_id=?", (guest.account_id,))
        return moved

    # -- imports ----------------------------------------------------------------

    def owns(self, account_id: str, profile_id: str) -> bool:
        with self._transaction() as conn:
            return conn.execute(
                "SELECT 1 FROM profile_owners WHERE profile_id=? AND account_id=?", (profile_id, account_id)
            ).fetchone() is not None

    def owned_profile_ids(self, account_id: str) -> tuple[str, ...]:
        with self._transaction() as conn:
            return tuple(r[0] for r in conn.execute(
                "SELECT profile_id FROM profile_owners WHERE account_id=? ORDER BY created_at", (account_id,)
            ))

    def add_import(self, account_id: str, profile_id: str) -> None:
        """Record a new import as this account's, and make it the active one."""
        with self._transaction() as conn:
            if self._load(conn, account_id) is None:
                # The guest signed in elsewhere while this import was read.
                raise AccountError("session-ended")
            conn.execute(
                "INSERT INTO profile_owners(profile_id, account_id, created_at) VALUES (?,?,?)",
                (profile_id, account_id, self._now().isoformat()),
            )
            conn.execute("UPDATE accounts SET active_profile_id=? WHERE account_id=?", (profile_id, account_id))

    def set_active(self, account_id: str, profile_id: str) -> None:
        with self._transaction() as conn:
            changed = conn.execute(
                "UPDATE accounts SET active_profile_id=? WHERE account_id=? AND EXISTS "
                "(SELECT 1 FROM profile_owners WHERE profile_id=? AND account_id=?)",
                (profile_id, account_id, profile_id, account_id),
            ).rowcount
            if not changed:
                raise AccountError("not-owner")

    def is_owned(self, profile_id: str) -> bool:
        with self._transaction() as conn:
            return conn.execute("SELECT 1 FROM profile_owners WHERE profile_id=?", (profile_id,)).fetchone() is not None

    # -- the installation owner (named from the console, never the web) ----------

    def owner_account_id(self) -> str | None:
        with self._transaction() as conn:
            row = conn.execute("SELECT value FROM installation WHERE key='owner_account_id'").fetchone()
            return None if row is None else row[0]

    def set_owner(self, email: str, unowned_profile_ids: Iterable[str]) -> tuple[Account, tuple[str, ...]]:
        """Name the installation owner and give them every unowned import.

        Only the operator's console calls this (``python -m
        AniRec.api.accounts owner``): unowned imports can carry MyAnimeList
        sign-ins, and web registration is open to anyone.
        """
        email = normalize_email(email)
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT account_id FROM accounts WHERE email=? AND kind='registered'", (email,)
            ).fetchone()
            if row is None:
                raise AccountError("no-such-account")
            account_id = row[0]
            conn.execute(
                "INSERT INTO installation(key, value) VALUES ('owner_account_id', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (account_id,),
            )
            owned = {r[0] for r in conn.execute("SELECT profile_id FROM profile_owners")}
            claimed = tuple(sorted(i for i in set(unowned_profile_ids) if i not in owned))
            now = self._now().isoformat()
            for profile_id in claimed:
                conn.execute(
                    "INSERT INTO profile_owners(profile_id, account_id, created_at) VALUES (?,?,?)",
                    (profile_id, account_id, now),
                )
            account = self._load(conn, account_id)
            if account.active_profile_id is None and claimed:
                conn.execute("UPDATE accounts SET active_profile_id=? WHERE account_id=?", (claimed[0], account_id))
            return self._load(conn, account_id), claimed


class _Transaction:
    """``BEGIN IMMEDIATE`` ... ``COMMIT`` on one short-lived connection."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def __enter__(self) -> sqlite3.Connection:
        self._conn.execute("BEGIN IMMEDIATE")
        return self._conn

    def __exit__(self, kind, _value, _traceback) -> None:
        with closing(self._conn):
            self._conn.execute("ROLLBACK" if kind else "COMMIT")
