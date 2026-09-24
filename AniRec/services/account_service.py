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
import json
import re
import secrets
import sqlite3
import threading
import unicodedata
from collections.abc import Callable, Iterable
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..errors import AniRecError
from ..infrastructure.paths import config_dir


SESSION_COOKIE = "anirec_session"
SESSION_LIFETIME = timedelta(days=30)
# A session's last-seen time is written at most this often, so reads do not
# turn into a write on every request.
SESSION_TOUCH_INTERVAL = timedelta(hours=1)
PASSWORD_MIN = 8
PASSWORD_MAX = 256
EMAIL_MAX = 254
# Wrong passwords for one email from one visitor; and, much higher, for one
# email from everyone at once (guessing spread across many addresses). A
# visitor can therefore no longer lock another reader out on their own.
FAILURE_LIMIT = 5
ACCOUNT_FAILURE_LIMIT = 50
FAILURE_WINDOW = timedelta(minutes=15)
# Per-visitor limits (new accounts, sign-in failures) live in the API, which
# knows who the visitor is: ``AniRec/api/limits.py``.

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


class _HashSlot:
    """One of the two hashing slots, taken without waiting, or ``busy``."""

    def __enter__(self) -> None:
        if not _HASH_SLOTS.acquire(blocking=False):
            raise AccountError("busy")

    def __exit__(self, *_exc) -> None:
        _HASH_SLOTS.release()


def _scrypt(password: str, salt: bytes, log_n: int, r: int, p: int, *, slot_held: bool = False) -> bytes:
    def run() -> bytes:
        return hashlib.scrypt(
            unicodedata.normalize("NFKC", password).encode("utf-8"), salt=salt,
            n=2**log_n, r=r, p=p, maxmem=_SCRYPT_MAXMEM, dklen=32,
        )
    if slot_held:
        return run()
    with _HashSlot():
        return run()


def hash_password(password: str, *, salt: bytes | None = None, slot_held: bool = False) -> str:
    salt = salt or secrets.token_bytes(16)
    key = _scrypt(password, salt, _SCRYPT_LOG_N, _SCRYPT_R, _SCRYPT_P, slot_held=slot_held)
    return f"scrypt${_SCRYPT_LOG_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(key)}"


def verify_password(password: str, stored: str, *, slot_held: bool = False) -> bool:
    try:
        scheme, log_n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt" or int(log_n) > 20:
            return False
        key = _scrypt(password, base64.b64decode(salt), int(log_n), int(r), int(p), slot_held=slot_held)
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
CREATE TABLE IF NOT EXISTS preferences (
    account_id TEXT PRIMARY KEY REFERENCES accounts(account_id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pending_deletions (
    profile_id TEXT PRIMARY KEY,
    requested_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS released_lists (
    profile_id TEXT PRIMARY KEY,
    released_at TEXT NOT NULL
);
"""

# Reader preferences kept per account (docs/ACCOUNTS.md, "Reader preferences").
PREFERENCE_KEYS = ("adventurousness", "minimum_mal_score", "include_nsfw")
# A guest unused this long (30-day session plus a week of grace) is pruned.
GUEST_IDLE_LIMIT = timedelta(days=37)
PRUNE_INTERVAL = timedelta(hours=1)
PRUNE_BATCH = 20


def is_web_import(profile_id: str) -> bool:
    """A list imported through the web (``imp_*``), as opposed to one from
    before accounts that the desktop tool may still use."""
    return profile_id.startswith("imp_")


@dataclass(frozen=True)
class Deletion:
    """What deleting an account does to its lists."""

    pending: tuple[str, ...]   # web lists whose directories are now to be removed
    released: tuple[str, ...]  # pre-account lists handed back to no owner


# -- account management (docs/ACCOUNTS.md, "Account management") ----------------

def _preferences_from(raw: str | None) -> dict:
    try:
        data = json.loads(raw) if raw else {}
    except ValueError:
        return {}
    return {key: data[key] for key in PREFERENCE_KEYS if key in data} if isinstance(data, dict) else {}


class _AccountManagement:
    """Mixed into AccountService below; kept apart for reading."""

    def account_details(self, account_id: str) -> dict | None:
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT kind, email, created_at FROM accounts WHERE account_id=?", (account_id,)
            ).fetchone()
        if row is None:
            return None
        return {"kind": row[0], "email": row[1] if row[0] == "registered" else None, "created_at": row[2]}

    def preferences(self, account_id: str) -> dict:
        """This account's saved reader preferences (only the keys it saved)."""
        with self._transaction() as conn:
            row = conn.execute("SELECT data FROM preferences WHERE account_id=?", (account_id,)).fetchone()
        return _preferences_from(None if row is None else row[0])

    def save_preferences(self, account_id: str, values: dict) -> dict:
        data = {key: values[key] for key in PREFERENCE_KEYS if key in values}
        with self._transaction() as conn:
            if self._load(conn, account_id) is None:
                raise AccountError("session-ended")
            conn.execute(
                "INSERT INTO preferences(account_id, data, updated_at) VALUES (?,?,?) "
                "ON CONFLICT(account_id) DO UPDATE SET data=excluded.data, updated_at=excluded.updated_at",
                (account_id, json.dumps(data, sort_keys=True), self._now().isoformat()),
            )
        return data

    def delete_account(self, account_id: str, *, keep: Iterable[str] = ()) -> Deletion:
        """Step 2 of deleting an account: one transaction.

        Web lists enter ``pending_deletions``; lists from before accounts, and
        any in ``keep`` (the desktop tool's active one), are released to no
        owner. The account, its sessions, preferences and ownership rows go,
        and the installation owner row if it was the owner. The caller has
        already closed the lists to new operations (step 1) and removes the
        pending directories afterwards (step 3).
        """
        keep = set(keep)
        now = self._now().isoformat()
        with self._transaction() as conn:
            if self._load(conn, account_id) is None:
                raise AccountError("session-ended")
            owned = [r[0] for r in conn.execute(
                "SELECT profile_id FROM profile_owners WHERE account_id=? ORDER BY created_at", (account_id,)
            )]
            pending = tuple(i for i in owned if is_web_import(i) and i not in keep)
            released = tuple(i for i in owned if i not in pending)
            for profile_id in pending:
                conn.execute(
                    "INSERT OR IGNORE INTO pending_deletions(profile_id, requested_at) VALUES (?,?)",
                    (profile_id, now),
                )
            # Remembered, so the sweep never mistakes a kept list for a stray,
            # even after the desktop tool switches away from it.
            for profile_id in released:
                conn.execute(
                    "INSERT OR IGNORE INTO released_lists(profile_id, released_at) VALUES (?,?)",
                    (profile_id, now),
                )
            conn.execute("DELETE FROM profile_owners WHERE account_id=?", (account_id,))
            conn.execute("DELETE FROM installation WHERE key='owner_account_id' AND value=?", (account_id,))
            conn.execute("DELETE FROM accounts WHERE account_id=?", (account_id,))   # sessions, preferences cascade
        return Deletion(pending, released)

    def pending_deletions(self) -> tuple[str, ...]:
        with self._transaction() as conn:
            return tuple(r[0] for r in conn.execute("SELECT profile_id FROM pending_deletions ORDER BY requested_at"))

    def deletion_done(self, profile_id: str) -> None:
        with self._transaction() as conn:
            conn.execute("DELETE FROM pending_deletions WHERE profile_id=?", (profile_id,))

    def is_released(self, profile_id: str) -> bool:
        with self._transaction() as conn:
            return conn.execute("SELECT 1 FROM released_lists WHERE profile_id=?", (profile_id,)).fetchone() is not None

    def is_pending(self, profile_id: str) -> bool:
        with self._transaction() as conn:
            return conn.execute("SELECT 1 FROM pending_deletions WHERE profile_id=?", (profile_id,)).fetchone() is not None

    def claim_prune_run(self) -> bool:
        """Whether this process should prune now: at most once an hour across
        every process sharing this database, recorded under its lock."""
        now = self._now()
        with self._transaction() as conn:
            row = conn.execute("SELECT value FROM installation WHERE key='last_prune_at'").fetchone()
            if row is not None:
                last = datetime.fromisoformat(row[0])
                if last <= now < last + PRUNE_INTERVAL:
                    return False
            conn.execute(
                "INSERT INTO installation(key, value) VALUES ('last_prune_at', ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (now.isoformat(),),
            )
            return True

    def prunable_guests(self, *, limit: int = PRUNE_BATCH) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Guests nobody can reach any more, with their lists; empty when the
        clock looks wrong (docs/ACCOUNTS.md, "Guest pruning")."""
        now = self._now()
        with self._transaction() as conn:
            newest = conn.execute("SELECT MAX(last_seen_at) FROM sessions").fetchone()[0]
            if newest is None:
                return ()
            newest_seen = datetime.fromisoformat(newest)
            # Nobody seen in a day: a forward jump or a long idle. A session
            # seen "in the future": a backward jump. Either way, do nothing.
            if now - newest_seen > timedelta(days=1) or newest_seen > now + timedelta(minutes=5):
                return ()
            cutoff = (now - GUEST_IDLE_LIMIT).isoformat()
            rows = conn.execute(
                """SELECT a.account_id FROM accounts a
                   WHERE a.kind='guest' AND a.created_at < ?
                     AND NOT EXISTS (SELECT 1 FROM sessions s WHERE s.account_id=a.account_id
                                     AND (s.expires_at > ? OR s.last_seen_at >= ?))
                   ORDER BY a.created_at LIMIT ?""",
                (cutoff, now.isoformat(), cutoff, limit),
            ).fetchall()
            return tuple(
                (row[0], tuple(r[0] for r in conn.execute(
                    "SELECT profile_id FROM profile_owners WHERE account_id=?", (row[0],)
                )))
                for row in rows
            )


class AccountService(_AccountManagement):
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._path = config_dir(root_override) / "accounts.sqlite3"
        self._clock = clock
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
        try:
            return _Transaction(self._connect())
        except sqlite3.Error as error:
            # Locked, corrupt or unreadable: a refusal, never a server error.
            raise AccountError("unavailable") from error

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
        """The account a session cookie names, or ``None`` for no valid session.

        An unreadable account database also reads as no session: the visitor
        sees the sample library rather than a server error.
        """
        return self.session(token)[0]

    def session(self, token: str | None) -> tuple[Account | None, bool]:
        """The session's account, and whether its expiry was just renewed
        (the caller then re-sends the cookie with a fresh lifetime)."""
        try:
            return self._account_for_session(token)
        except AccountError:
            return None, False

    def _account_for_session(self, token: str | None) -> tuple[Account | None, bool]:
        if not token or len(token) > 200:
            return None, False
        digest = _token_hash(token)
        now = self._now()
        with self._transaction() as conn:
            row = conn.execute(
                "SELECT account_id, expires_at, last_seen_at FROM sessions WHERE token_hash=?", (digest,)
            ).fetchone()
            if row is None:
                return None, False
            if datetime.fromisoformat(row[1]) <= now:
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
                return None, False
            renewed = now - datetime.fromisoformat(row[2]) >= SESSION_TOUCH_INTERVAL
            if renewed:
                # A session in use lives 30 days from its last use; the caller
                # re-sends the cookie so the browser's copy lives as long.
                conn.execute(
                    "UPDATE sessions SET last_seen_at=?, expires_at=? WHERE token_hash=?",
                    (now.isoformat(), (now + SESSION_LIFETIME).isoformat(), digest),
                )
            return self._load(conn, row[0]), renewed

    def sign_out(self, token: str | None) -> None:
        if not token or len(token) > 200:
            return
        with self._transaction() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(token),))

    def create_guest(self) -> SignedIn:
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

    def sign_in(self, email: str, password: str, *, current_token: str | None = None, client: str = "") -> SignedIn:
        """Check the password; bring a guest's imports along (docs/ACCOUNTS.md)."""
        if not isinstance(password, str) or len(password) > PASSWORD_MAX:
            raise AccountError("wrong-credentials")
        try:
            email = normalize_email(email)
        except AccountError:
            raise AccountError("wrong-credentials") from None
        dummy = _dummy_hash()   # computed once, before a slot is held
        # The hashing slot is taken before the attempt is counted: a "busy"
        # refusal must never count as a wrong password (final review).
        with _HashSlot():
            account_id = self._checked_credentials(email, password, dummy, client)
        with self._transaction() as conn:
            if self._load(conn, account_id) is None:
                # Deleted between the password check and now.
                raise AccountError("wrong-credentials")
            moved: tuple[str, ...] = ()
            current = self._session_account_locked(conn, current_token)
            if current is not None and current.kind == "guest" and current.account_id != account_id:
                # Deleting the guest also ends every session it had.
                moved = self._move_guest_locked(conn, current, account_id)
            elif current_token:
                conn.execute("DELETE FROM sessions WHERE token_hash=?", (_token_hash(current_token),))
            token = self._new_session(conn, account_id)
            return SignedIn(self._load(conn, account_id), token, moved)

    def _checked_credentials(self, email: str, password: str, dummy: str, client: str) -> str:
        return self._checked_credentials_with_hash(email, password, dummy, client)[0]

    def _checked_credentials_with_hash(self, email: str, password: str, dummy: str, client: str) -> tuple[str, str]:
        """The account ID and its stored hash when ``password`` is right,
        counting every attempt.

        The caller holds a hashing slot. Shared by sign-in, changing the
        password and deleting the account, so each is throttled alike.
        """
        if not isinstance(password, str) or len(password) > PASSWORD_MAX:
            raise AccountError("wrong-credentials")
        now = self._now()
        # Two counters (the table's key column holds both kinds): this email
        # from this visitor, and this email from everyone.
        counters = ((f"{email}\n{client}", FAILURE_LIMIT), (email, ACCOUNT_FAILURE_LIMIT))
        # The attempt is counted before the password is checked, in one
        # locked transaction, so parallel guesses cannot all see a low count.
        with self._transaction() as conn:
            counts = []
            for key, limit in counters:
                row = conn.execute(
                    "SELECT count, last_failed_at FROM login_failures WHERE email=?", (key,)
                ).fetchone()
                fresh = row is None or now - datetime.fromisoformat(row[1]) >= FAILURE_WINDOW
                if not fresh and row[0] >= limit:
                    raise AccountError("too-many-attempts")
                counts.append((key, 1 if fresh else row[0] + 1))
            for key, count in counts:
                conn.execute(
                    "INSERT INTO login_failures(email, count, last_failed_at) VALUES (?,?,?) "
                    "ON CONFLICT(email) DO UPDATE SET count=excluded.count, last_failed_at=excluded.last_failed_at",
                    (key, count, now.isoformat()),
                )
            account = conn.execute(
                "SELECT account_id, password_hash FROM accounts WHERE email=? AND kind='registered'", (email,)
            ).fetchone()
        # Hashing happens outside the write lock: it is the slow part. An
        # unknown email is checked against a dummy hash to take the same time.
        valid = verify_password(password, account[1] if account else dummy, slot_held=True) and account is not None
        if not valid:
            raise AccountError("wrong-credentials")
        with self._transaction() as conn:
            for key, _limit in counters:
                conn.execute("DELETE FROM login_failures WHERE email=?", (key,))
        return account[0], account[1]

    def _email_of(self, account_id: str) -> str:
        with self._transaction() as conn:
            account = self._load(conn, account_id)
        if account is None:
            raise AccountError("session-ended")
        if not account.registered or not account.email:
            raise AccountError("not-registered")
        return account.email

    def change_password(self, account_id: str, current: str, new: str, *, client: str = "") -> SignedIn:
        """Replace the password; every session ends and one new one is issued."""
        _check_password(new)
        email = self._email_of(account_id)
        dummy = _dummy_hash()
        with _HashSlot():
            checked = self._checked_credentials_with_hash(email, current, dummy, client)
            if checked[0] != account_id:
                raise AccountError("wrong-credentials")
            password_hash = hash_password(new, slot_held=True)
        with self._transaction() as conn:
            # Only if the password is still the one just checked: a change
            # made meanwhile by another request wins, and this one is refused.
            changed = conn.execute(
                "UPDATE accounts SET password_hash=?, updated_at=? WHERE account_id=? AND password_hash=?",
                (password_hash, self._now().isoformat(), account_id, checked[1]),
            ).rowcount
            if not changed:
                raise AccountError("wrong-credentials")
            conn.execute("DELETE FROM sessions WHERE account_id=?", (account_id,))
            token = self._new_session(conn, account_id)
            return SignedIn(self._load(conn, account_id), token)

    def confirm_password(self, account_id: str, password: str, *, client: str = "") -> None:
        """Check the password of a registered account, counted like a sign-in."""
        email = self._email_of(account_id)
        dummy = _dummy_hash()
        with _HashSlot():
            if self._checked_credentials(email, password, dummy, client) != account_id:
                raise AccountError("wrong-credentials")

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
            pending = {r[0] for r in conn.execute("SELECT profile_id FROM pending_deletions")}
            # Never a web list: an unowned imp_* is one being deleted, or a
            # write that raced a deletion - someone's data, not the operator's.
            claimed = tuple(sorted(
                i for i in set(unowned_profile_ids)
                if i not in owned and i not in pending and not is_web_import(i)
            ))
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
        try:
            self._conn.execute("BEGIN IMMEDIATE")
        except sqlite3.Error as error:
            self._conn.close()
            raise AccountError("unavailable") from error
        return self._conn

    def __exit__(self, kind, value, _traceback) -> None:
        with closing(self._conn):
            try:
                self._conn.execute("ROLLBACK" if kind else "COMMIT")
            except sqlite3.Error as error:
                raise AccountError("unavailable") from error
        if isinstance(value, sqlite3.Error):
            raise AccountError("unavailable") from value
