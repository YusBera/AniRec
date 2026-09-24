"""First-time setup over HTTP (D-020).

One write: start with a public MyAnimeList list, given only its username.
The list becomes an import of the requesting account; a visitor with no
account gets a guest account, but only once the list has been read (D-021).
Routes stay thin; the work is in ``OnboardingService``.
A list that cannot be read is answered with a ``reason`` the web client words
for a newcomer, never with a server error or MyAnimeList's raw message.
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response
from pydantic import Field

from ..errors import (
    AccessDeniedError,
    AniRecError,
    AuthError,
    ConfigError,
    NetworkError,
    NotFoundError,
    ProfileError,
    RateLimitError,
    ServerError,
    UnexpectedStatusError,
)
from ..services.account_service import AccountError
from .accounts import renew_cookie, resolve_scope, set_session_cookie
from .container import ApiContainer
from .limits import ClientLimits
from .models import ApiModel, ProfileSummary


class MalImportRequest(ApiModel):
    username: str = Field(max_length=200, description="A MyAnimeList username or https://myanimelist.net/profile/... URL.")


class MalImportResponse(ApiModel):
    """The new active profile, or why there is none."""

    profile: ProfileSummary | None = None
    reason: str | None = Field(
        default=None,
        description=(
            "invalid-username, client-id-required, user-not-found, private-list, "
            "installation-refused, rate-limited, network, busy or unavailable."
        ),
    )


def _reason(error: AniRecError) -> str:
    """What went wrong, from the reader's side of the screen.

    Order matters: AccessDeniedError is an AuthError; RateLimitError,
    ServerError and UnexpectedStatusError are NetworkErrors.
    """
    if isinstance(error, AccountError):
        # busy: too many imports or new guests this hour; session-ended: the
        # guest signed in elsewhere while the list was read.
        return "busy" if error.reason == "busy" else "unavailable"
    if isinstance(error, ProfileError):
        return "invalid-username"
    if isinstance(error, ConfigError):
        return "client-id-required"
    if isinstance(error, NotFoundError):
        return "user-not-found"
    if isinstance(error, AccessDeniedError):
        return "private-list"
    if isinstance(error, AuthError):
        # 401: the only credential sent is this installation's Client ID, so
        # nothing about the reader's list needs to change.
        return "installation-refused"
    if isinstance(error, RateLimitError):
        return "rate-limited"
    if isinstance(error, (ServerError, UnexpectedStatusError)):
        return "unavailable"
    if isinstance(error, NetworkError):
        return "network"
    return "unavailable"


def onboarding_router(services: ApiContainer, limits: ClientLimits) -> APIRouter:
    router = APIRouter(prefix="/api/onboarding")

    @router.post("/mal-profile", response_model=MalImportResponse)
    def import_mal_profile(payload: MalImportRequest, request: Request, response: Response) -> MalImportResponse:
        try:
            # Every import reads MyAnimeList with this installation's Client
            # ID: it counts against this visitor's shared budget (limits.py).
            client = limits.client(request)
            scope = resolve_scope(services, request)
            renew_cookie(request, response, scope, limits)
            # A visitor who could not be given a guest account spends no call.
            if scope.account is None and limits.new_accounts.full(client):
                raise AccountError("busy")
            if not limits.mal_calls.take(client):
                raise AccountError("busy")
            username = services.onboarding.read_public_mal_list(payload.username)
            account = scope.account
            if account is None:
                if not limits.new_accounts.take(client):
                    raise AccountError("busy")
                guest = services.accounts.create_guest()
                set_session_cookie(request, response, guest.token, limits)
                account = guest.account
            profile = services.onboarding.import_for_account(services.accounts, account.account_id, username)
        except AniRecError as error:
            return MalImportResponse(reason=_reason(error))
        except OSError:
            # A local write failed (disk full, permissions): not a server crash.
            return MalImportResponse(reason="unavailable")
        return MalImportResponse(
            profile=ProfileSummary(profile_id=profile.profile_id, username=profile.username)
        )

    return router
