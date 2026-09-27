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

import ipaddress
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
EXPORTS_PER_HOUR = 20
# Password reset emails asked for; the mail worker also caps each account
# and the installation (account_service.py).
PASSWORD_RESETS_PER_HOUR = 5
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
    """Addresses or CIDR ranges, comma-separated, in any spelling."""
    raw = os.environ.get(TRUSTED_PROXIES_ENV_VAR, "")
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def _address(value: str):
    try:
        return ipaddress.ip_address(value.strip().strip("[]"))
    except ValueError:
        return None


def _networks(entries: frozenset[str]) -> tuple:
    networks = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry.strip(), strict=False))
        except ValueError:
            continue   # an unparseable entry trusts nothing
    return tuple(networks)


def bucket(value: str) -> str:
    """The limit key for an address: IPv4 as is, IPv6 by its /64.

    One IPv6 host usually holds a whole /64, so keying by full address would
    hand it unlimited buckets.
    """
    address = _address(value)
    if address is None:
        return value.strip() or "unknown"
    if address.version == 4:
        return str(address)
    if address.ipv4_mapped is not None:
        return str(address.ipv4_mapped)
    return str(ipaddress.ip_network(f"{address}/64", strict=False))


@dataclass
class ClientLimits:
    trusted_proxies: frozenset[str] = frozenset()
    new_accounts: KeyedRateWindow = field(default_factory=lambda: KeyedRateWindow(NEW_ACCOUNTS_PER_HOUR, 3600))
    sign_in_failures: KeyedRateWindow = field(default_factory=lambda: KeyedRateWindow(SIGN_IN_FAILURES_PER_MINUTE, 60))
    # Imports, public-list lookups, live Compare and title look-ups: each
    # spends this installation's MyAnimeList Client ID.
    mal_calls: KeyedRateWindow = field(default_factory=lambda: KeyedRateWindow(MAL_CALLS_PER_HOUR, 3600))
    exports: KeyedRateWindow = field(default_factory=lambda: KeyedRateWindow(EXPORTS_PER_HOUR, 3600))
    password_resets: KeyedRateWindow = field(default_factory=lambda: KeyedRateWindow(PASSWORD_RESETS_PER_HOUR, 3600))

    @classmethod
    def from_environment(cls) -> "ClientLimits":
        return cls(trusted_proxies=trusted_proxies_from_environment())

    def _trusted(self, value: str) -> bool:
        address = _address(value)
        if address is None:
            return False
        networks = getattr(self, "_parsed", None)
        if networks is None:
            networks = self._parsed = _networks(self.trusted_proxies)
        return any(address in network for network in networks if network.version == address.version)

    def _forwarded(self, request: Request) -> bool:
        return bool(self.trusted_proxies) and self._trusted(request.client.host if request.client else "")

    @staticmethod
    def _header_values(request: Request, name: str) -> list[str]:
        # Every header line, joined: a proxy that appends its own line after
        # the client's must not let the client's line decide (final review).
        joined = ",".join(request.headers.getlist(name))
        return [part.strip() for part in joined.split(",") if part.strip()]

    def client(self, request: Request) -> str:
        """The visitor's limit key: the peer, or what a trusted proxy reports."""
        peer = request.client.host if request.client else "unknown"
        if not self._forwarded(request):
            return bucket(peer)
        # The right-most address a trusted proxy did not add is the client;
        # anything to its left was written by the client and proves nothing.
        for address in reversed(self._header_values(request, "x-forwarded-for")):
            if not self._trusted(address):
                return bucket(address)
        return bucket(peer)

    def is_https(self, request: Request) -> bool:
        if request.url.scheme == "https":
            return True
        if self._forwarded(request):
            # The right-most value is the one the trusted proxy wrote.
            values = self._header_values(request, "x-forwarded-proto")
            return bool(values) and values[-1].lower() == "https"
        return False
