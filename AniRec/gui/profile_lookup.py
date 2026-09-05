"""One place the interface asks whether a MyAnimeList username is usable.

Two surfaces need the same answer. Discover resolves the profiles added for
group recommendations; Compare resolves the profile being compared against.
Left to themselves they would each build a lookup, each keep their own memory
of what they had already asked, and the same username typed on both would cost
two requests and could produce two different verdicts.

So the lookup is here, once, with a session cache in front of it. The cache is
a frontend concern and only a frontend concern: it stops *this session* asking
twice for something it already knows. The frontend deliberately does not
guess at persistence or cross-session cache policy.

Nothing in this file decides whether a list is private or a user exists. It
asks the existing profile service, which asks MyAnimeList, and it translates
the exceptions that come back into the states the interface has to draw.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from ..errors import AniRecError
from ..presentation.compatibility import UnavailableReason
from .texts import FILTER_TEXT
from .workers import (
    OperationAlreadyRunningError,
    PublicProfileLookupWorker,
    WorkerController,
)


@dataclass(frozen=True)
class ProfileLookupResult:
    """What became of one username.

    ``reason`` is kept alongside the sentence because the two are used for
    different things: the sentence is shown, the reason decides whether a
    retry is offered at all. Re-asking for a list that is private is not a
    retry, it is the same refusal again.
    """

    username: str
    ok: bool
    message: str = ""
    reason: UnavailableReason | None = None

    @property
    def retryable(self) -> bool:
        return self.reason in (
            UnavailableReason.NETWORK,
            UnavailableReason.API_UNAVAILABLE,
        )


# The worker emits ``presentable_error``'s model, not the exception, so the
# distinction has to be read off ``code``. That is a deliberate boundary - a
# traceback must not reach the interface - and the codes are exactly the
# vocabulary needed here.
FAILURE_REASONS = {
    "not_found": UnavailableReason.USER_NOT_FOUND,
    "access_denied": UnavailableReason.PRIVATE_LIST,
    "auth_error": UnavailableReason.PRIVATE_LIST,
    "auth_timeout": UnavailableReason.NETWORK,
    "rate_limited": UnavailableReason.API_UNAVAILABLE,
    "server_error": UnavailableReason.API_UNAVAILABLE,
    "network_error": UnavailableReason.NETWORK,
    "invalid_response": UnavailableReason.API_UNAVAILABLE,
    "profile_error": UnavailableReason.USER_NOT_FOUND,
    "config_error": UnavailableReason.NOT_CONNECTED,
}

# What each reason says, in the second person, naming the profile it is about.
# One sentence per reason rather than one per error code, because "HTTP 403"
# and "HTTP 401" are the same fact to a reader: this list is not public.
FAILURE_MESSAGES = {
    UnavailableReason.USER_NOT_FOUND: FILTER_TEXT.profile_not_found,
    UnavailableReason.PRIVATE_LIST: FILTER_TEXT.profile_private,
    UnavailableReason.API_UNAVAILABLE: FILTER_TEXT.profile_rate_limited,
    UnavailableReason.NETWORK: FILTER_TEXT.profile_unreachable,
    UnavailableReason.NOT_CONNECTED: FILTER_TEXT.profile_needs_client_id,
}


def classify_failure(username: str, error: object) -> ProfileLookupResult:
    """Turn one reported failure into the state a pill or a panel should show.

    The distinctions matter because the interface says something different for
    each, and a reader can act on some of them. Collapsing them all into
    "could not load" is the version of this that makes a private list look
    like an outage and an outage look like a typo.
    """
    code = str(getattr(error, "code", "") or "")
    reason = FAILURE_REASONS.get(code, UnavailableReason.API_UNAVAILABLE)
    template = FAILURE_MESSAGES.get(reason, FILTER_TEXT.profile_failed)
    return ProfileLookupResult(
        username=username,
        ok=False,
        message=template.format(value=username),
        reason=reason,
    )


class ProfileLookupService(QObject):
    """Resolve usernames off the GUI thread, once per session each.

    Requests are independent: five usernames added at once become five
    operations that start together and land as they land, so one slow list
    does not hold the other four, and one failure does not touch them at all.
    That is the whole reason this does not batch.
    """

    resolved = Signal(object)

    #: Distinct from the operation keys the pipeline uses, so a profile lookup
    #: can never collide with a sync or a recommendation run.
    KEY_PREFIX = "profile-lookup"

    def __init__(
        self,
        *,
        worker_controller: WorkerController | None = None,
        profile_service=None,
        settings_service=None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.worker_controller = worker_controller
        self.profile_service = profile_service
        self.settings_service = settings_service
        self._cache: dict[str, ProfileLookupResult] = {}
        self._in_flight: dict[str, tuple[str, str]] = {}
        if worker_controller is not None:
            worker_controller.result_ready.connect(self._on_result)
            worker_controller.error_occurred.connect(self._on_error)

    # ---- session cache ---------------------------------------------------

    def cached(self, username: str) -> ProfileLookupResult | None:
        return self._cache.get(str(username).strip().casefold())

    def forget(self, username: str) -> None:
        """Drop one answer so it will be asked for again.

        Used by retry. Without it a retry would be served the failure that is
        already on screen, which is not a retry.
        """
        self._cache.pop(str(username).strip().casefold(), None)

    def clear_cache(self) -> None:
        self._cache.clear()

    def is_pending(self, username: str) -> bool:
        wanted = str(username).strip().casefold()
        return any(key == wanted for key, _name in self._in_flight.values())

    # ---- lookup ----------------------------------------------------------

    def lookup(self, username: str) -> ProfileLookupResult | None:
        """Start a lookup, or answer immediately from what is already known.

        Returns the result when it was already known and ``None`` when a
        request has been started - so a caller can render a pill as resolved
        straight away rather than flashing it through a loading state it never
        really had.
        """
        name = str(username).strip()
        key = name.casefold()
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        if self.is_pending(name):
            return None

        failure = self._unavailable_reason()
        if failure is not None:
            # Deliberately not cached. "No Client ID yet" is a fact about the
            # application's configuration, not about this username, and it
            # stops being true the moment someone finishes setup. Caching it
            # would leave every profile permanently unresolvable for the rest
            # of the session after one attempt made too early.
            return ProfileLookupResult(name, False, failure[0], failure[1])

        settings = self.settings_service.load()
        operation_key = f"{self.KEY_PREFIX}:{key}"
        worker = PublicProfileLookupWorker(
            self.profile_service, name, settings.client_id or ""
        )
        try:
            self.worker_controller.start(operation_key, worker)
        except (OperationAlreadyRunningError, ValueError):
            return None
        # Both spellings are kept: the key is how a pill is found, the name is
        # how the reader wrote it and is what any message must say back.
        self._in_flight[operation_key] = (key, name)
        return None

    def _unavailable_reason(self):
        """Whether a lookup can be attempted at all, and why not."""
        if self.worker_controller is None or self.profile_service is None:
            return (FILTER_TEXT.profile_offline, UnavailableReason.BACKEND_MISSING)
        if self.settings_service is None:
            return (FILTER_TEXT.profile_needs_client_id, UnavailableReason.NOT_CONNECTED)
        try:
            settings = self.settings_service.load()
        except (AniRecError, OSError, TypeError, ValueError):
            return (FILTER_TEXT.profile_needs_client_id, UnavailableReason.NOT_CONNECTED)
        if not (settings.client_id or "").strip():
            # Not a failure of the username. Saying so where the username was
            # typed is what stops someone editing a name that was fine.
            return (FILTER_TEXT.profile_needs_client_id, UnavailableReason.NOT_CONNECTED)
        return None

    # ---- worker replies --------------------------------------------------

    def _on_result(self, operation_key: str, result: object) -> None:
        entry = self._in_flight.pop(operation_key, None)
        if entry is None:
            return
        key, name = entry
        # MyAnimeList normalises capitalisation, so prefer what it returned
        # over what was typed: the pill should read the way the profile is
        # actually spelled.
        username = getattr(result, "username", "") or name
        resolved = ProfileLookupResult(username, True)
        self._cache[key] = resolved
        self.resolved.emit(resolved)

    def _on_error(self, operation_key: str, error: object) -> None:
        entry = self._in_flight.pop(operation_key, None)
        if entry is None:
            return
        key, name = entry
        # The reported failure carries no username, and the pill that has to
        # be updated is identified by one. The key it was filed under is that
        # username, so it is passed in rather than dug out of the error.
        resolved = classify_failure(name, error)
        self._cache[key] = resolved
        self.resolved.emit(resolved)
