"""First-time setup over HTTP (D-020).

One write: start with a public MyAnimeList list, given only its username.
Routes stay thin; the work is ``OnboardingService.import_public_mal_profile``.
A list that cannot be read is answered with a ``reason`` the web client words
for a newcomer, never with a server error or MyAnimeList's raw message.
"""

from __future__ import annotations

from fastapi import APIRouter
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
from .container import ApiContainer
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
            "installation-refused, rate-limited, network or unavailable."
        ),
    )


def _reason(error: AniRecError) -> str:
    """What went wrong, from the reader's side of the screen.

    Order matters: AccessDeniedError is an AuthError; RateLimitError,
    ServerError and UnexpectedStatusError are NetworkErrors.
    """
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


def onboarding_router(services: ApiContainer) -> APIRouter:
    router = APIRouter(prefix="/api/onboarding")

    @router.post("/mal-profile", response_model=MalImportResponse)
    def import_mal_profile(payload: MalImportRequest) -> MalImportResponse:
        try:
            profile = services.onboarding.import_public_mal_profile(payload.username)
        except AniRecError as error:
            return MalImportResponse(reason=_reason(error))
        except OSError:
            # A local write failed (disk full, permissions): not a server crash.
            return MalImportResponse(reason="unavailable")
        return MalImportResponse(
            profile=ProfileSummary(profile_id=profile.profile_id, username=profile.username)
        )

    return router
