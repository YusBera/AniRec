"""Per-visitor limits, and who the visitor is behind a proxy (D-021, phase 2).

Phase 1 capped new accounts, sign-in failures and imports process-wide, so one
visitor sending junk could block everyone. These limits are per client: one
visitor exhausting theirs leaves everybody else's untouched.

"Client" is the connecting address. AniRec binds to loopback, so a hosted
deployment sits behind a reverse proxy, and every request would otherwise
come from the proxy's address. ``ANIREC_TRUSTED_PROXIES`` names the proxies
whose ``X-Forwarded-For`` and ``X-Forwarded-Proto`` headers are believed;
from anyone else those headers are ignored, because any client can send them.
"""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field

from starlette.requests import Request

TRUSTED_PROXIES_ENV_VAR = "ANIREC_TRUSTED_PROXIES"

# Per client. Chosen so a real reader never meets them: a family sharing one
# address can still register a few accounts, and a reader can look up dozens
# of titles or friends in an hour.
NEW_ACCOUNTS_PER_HOUR = 10
SIGN_IN_FAILURES_PER_MINUTE = 20
MAL_CALLS_PER_HOUR = 60
# Beyond this many tracked clients the least recently seen is forgotten, so
# the table itself cannot be used to exhaust memory.
MAX_TRACKED_CLIENTS = 10_000


class KeyedRateWindow:
    """At most ``limit`` events per ``seconds`` for each key."""

    def __init__(self, limit: int, seconds: float, *, clock: Callable[[], float] = time.monotonic,
                 max_keys: int = MAX_TRACKED_CLIENTS) -> None:
        self._limit = limit
        self._seconds = seconds
        self._clock = clock
        self._max_keys = max_keys
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = threading.Lock()

    def _current(self, key: str, now: float) -> deque[float]:
        events = self._events.get(key)
        if events is None:
            events = deque()
            self._events[key] = events
            while len(self._events) > self._max_keys:
                self._events.popitem(last=False)
        self._events.move_to_end(key)
        while events and now - events[0] >= self._seconds:
            events.popleft()
        return events

    def full(self, key: str) -> bool:
        with self._lock:
            return len(self._current(key, self._clock())) >= self._limit

    def take(self, key: str) -> bool:
        """Record one event for ``key``; ``False`` (nothing recorded) when full."""
        with self._lock:
            now = self._clock()
            events = self._current(key, now)
            if len(events) >= self._limit:
                return False
            events.append(now)
            return True


def trusted_proxies_from_environment() -> frozenset[str]:
    raw = os.environ.get(TRUSTED_PROXIES_ENV_VAR, "")
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


@dataclass
class ClientLimits:
    trusted_proxies: frozenset[str] = frozenset()
    new_accounts: KeyedRateWindow = field(default_factory=lambda: KeyedRateWindow(NEW_ACCOUNTS_PER_HOUR, 3600))
    sign_in_failures: KeyedRateWindow = field(default_factory=lambda: KeyedRateWindow(SIGN_IN_FAILURES_PER_MINUTE, 60))
    # Imports, public-list lookups, live Compare and title look-ups: each
    # spends this installation's MyAnimeList Client ID.
    mal_calls: KeyedRateWindow = field(default_factory=lambda: KeyedRateWindow(MAL_CALLS_PER_HOUR, 3600))

    @classmethod
    def from_environment(cls) -> "ClientLimits":
        return cls(trusted_proxies=trusted_proxies_from_environment())

    def _forwarded(self, request: Request) -> bool:
        peer = request.client.host if request.client else ""
        return bool(self.trusted_proxies) and peer in self.trusted_proxies

    def client(self, request: Request) -> str:
        """The visitor's address: the peer, or what a trusted proxy reports."""
        peer = request.client.host if request.client else "unknown"
        if not self._forwarded(request):
            return peer
        chain = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
        # The right-most address a trusted proxy did not add is the client;
        # anything to its left was written by the client and proves nothing.
        for address in reversed(chain):
            if address not in self.trusted_proxies:
                return address
        return peer

    def is_https(self, request: Request) -> bool:
        if request.url.scheme == "https":
            return True
        if self._forwarded(request):
            proto = request.headers.get("x-forwarded-proto", "").split(",")[0].strip().lower()
            return proto == "https"
        return False
