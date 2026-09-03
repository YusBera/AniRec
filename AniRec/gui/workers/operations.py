"""Concrete workers that bind the GUI thread contract to AniRec services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from ...application.pipeline import OAUTH_STEP_ID, STEP_LABELS, PipelineOrchestrator
from ...models import (
    AppSettings,
    PipelineProgress,
    PipelineResult,
    PipelineSettings,
    UserProfile,
)
from ...services.profile_service import ProfileService
from ...services.cover_image_service import CoverImageService
from ...services.api_connection_service import ApiConnectionService
from ...services.auth_service import AuthService
from .base import BaseWorker


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OperationKind(str, Enum):
    SYNC = "sync"
    RECOMMENDATION = "recommendation"
    OAUTH = "oauth"
    API_TEST = "api-test"
    PROFILE = "profile"
    COVER = "cover"
    PROFILE_LOOKUP = "profile-lookup"
    MORE_RECOMMENDATIONS = "more-recommendations"
    LIST_SYNC = "list-sync"


def operation_key(kind: OperationKind | str, profile_id: str) -> str:
    resolved_kind = OperationKind(kind)
    normalized_profile_id = profile_id.strip()
    if not normalized_profile_id:
        raise ValueError("profile_id is required.")
    if ":" in normalized_profile_id:
        raise ValueError("profile_id cannot contain ':'.")
    return f"{resolved_kind.value}:{normalized_profile_id}"


class SyncWorker(BaseWorker):
    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        username: str,
        settings: PipelineSettings,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.orchestrator = orchestrator
        self.username = username
        self.settings = settings

    def execute(self) -> object:
        return self.orchestrator.run_sync(
            self.username,
            self.settings,
            progress_callback=self.report_progress,
            cancellation_token=self.cancellation_token,
        )


class ListSyncWorker(BaseWorker):
    """Walk the changed head of a MyAnimeList list off the interface thread.

    Carries no policy of its own. The service decides what a completion means
    and the window decides what to do about it; this exists because the walk
    is network-bound and must not block a launch.
    """

    def __init__(
        self,
        sync_service,
        profile_id: str,
        username: str,
        *,
        watch_later_mal_ids=frozenset(),
        clock=None,
        access_token: str | None = None,
        client_id: str | None = None,
        include_nsfw: bool = False,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.sync_service = sync_service
        self.profile_id = profile_id
        self.username = username
        self.watch_later_mal_ids = frozenset(watch_later_mal_ids)
        self._clock = clock or _utc_now_iso
        self.access_token = access_token
        self.client_id = client_id
        self.include_nsfw = include_nsfw

    def execute(self) -> object:
        return self.sync_service.sync(
            self.profile_id,
            self.username,
            watch_later_mal_ids=self.watch_later_mal_ids,
            synced_at=self._clock(),
            access_token=self.access_token,
            client_id=self.client_id,
            include_nsfw=self.include_nsfw,
            cancellation_token=self.cancellation_token,
        )


class ApiConnectionWorker(BaseWorker):
    def __init__(
        self,
        service: ApiConnectionService,
        settings: AppSettings,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.service = service
        self.settings = settings

    def execute(self) -> object:
        self.service.test(self.settings)
        return self.settings


class ProfileValidationWorker(BaseWorker):
    def __init__(
        self,
        profiles: ProfileService,
        profile_reference: str,
        client_id: str,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.profiles = profiles
        self.profile_reference = profile_reference
        self.client_id = client_id

    def execute(self) -> object:
        return self.profiles.add_public_profile(
            self.profile_reference,
            self.client_id,
            cancellation=self.cancellation_token,
        )


class PublicProfileLookupWorker(BaseWorker):
    """Check that one public MyAnimeList list can be read, and nothing more.

    ``ProfileValidationWorker`` beside this looks similar and is not
    interchangeable: it *adds* the profile - writes a directory, saves a
    profile.json, and makes it the active one. That is right for setup and
    wrong here. Adding a friend to a group recommendation, or comparing
    against them, must not silently switch whose library the application is
    showing.

    So this calls the validating half of the service on its own. The
    exceptions it raises are the ones the interface needs to tell apart -
    absent user, private list, rate limit, outage - and they reach the surface
    through the standard error path rather than being flattened here.
    """

    def __init__(
        self,
        profiles: ProfileService,
        username: str,
        client_id: str,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.profiles = profiles
        self.username = username
        self.client_id = client_id

    def execute(self) -> object:
        return self.profiles.validate_public_profile(
            self.username,
            self.client_id,
            cancellation=self.cancellation_token,
        )


@dataclass(frozen=True)
class PublicProfileSetupResult:
    settings: AppSettings
    profile: UserProfile


class PublicProfileSetupWorker(BaseWorker):
    """Validate a Client ID and public MAL profile in one setup operation."""

    def __init__(
        self,
        api_connection: ApiConnectionService,
        profiles: ProfileService,
        settings: AppSettings,
        profile_reference: str,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.api_connection = api_connection
        self.profiles = profiles
        self.settings = settings
        self.profile_reference = profile_reference

    def execute(self) -> object:
        self.cancellation_token.raise_if_cancelled()
        self.api_connection.test(self.settings)
        self.cancellation_token.raise_if_cancelled()
        profile = self.profiles.add_public_profile(
            self.profile_reference,
            self.settings.client_id or "",
            cancellation=self.cancellation_token,
        )
        return PublicProfileSetupResult(self.settings, profile)


class CoverDownloadWorker(BaseWorker):
    def __init__(
        self,
        service: CoverImageService,
        url: str,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.service = service
        self.url = url

    def execute(self) -> object:
        return self.service.fetch(self.url, cancellation=self.cancellation_token)


class TokenRefreshWorker(BaseWorker):
    """Refresh a token, optionally falling back to interactive OAuth consent."""

    def __init__(
        self,
        auth_service: AuthService,
        profile_id: str,
        settings: AppSettings,
        *,
        interactive_if_missing: bool = False,
        callback_timeout_seconds: float = 180,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.auth_service = auth_service
        self.profile_id = profile_id
        self.settings = settings
        self.interactive_if_missing = interactive_if_missing
        self.callback_timeout_seconds = callback_timeout_seconds

    def execute(self) -> object:
        self.cancellation_token.raise_if_cancelled()
        if self.interactive_if_missing:
            self.auth_service.get_access_token(
                self.profile_id,
                self.settings,
                interactive=True,
                callback_timeout_seconds=self.callback_timeout_seconds,
                cancellation=self.cancellation_token,
                status_callback=self._report_oauth_status,
            )
        else:
            self.auth_service.get_access_token(self.profile_id, self.settings)
        self.cancellation_token.raise_if_cancelled()
        return PipelineResult(user_stats={"oauth_connected": 1})

    def _report_oauth_status(self, status_id: str) -> None:
        self.step_changed.emit(status_id, status_id)


class RecommendationWorker(BaseWorker):
    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        username: str,
        settings: PipelineSettings,
        *,
        step_id: str | None = None,
        genre_adjustments: dict[str, float] | None = None,
        excluded_mal_ids: set[int] | frozenset[int] = frozenset(),
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.orchestrator = orchestrator
        self.username = username
        self.settings = settings
        self.step_id = step_id
        self.genre_adjustments = dict(genre_adjustments or {})
        self.excluded_mal_ids = frozenset(excluded_mal_ids)

    def execute(self) -> object:
        options = {
            "progress_callback": self.report_progress,
            "cancellation_token": self.cancellation_token,
        }
        if self.step_id is not None:
            return self.orchestrator.run_step(
                self.step_id,
                self.username,
                self.settings,
                **options,
            )
        if self.genre_adjustments:
            options["genre_adjustments"] = self.genre_adjustments
        if self.excluded_mal_ids:
            options["excluded_mal_ids"] = self.excluded_mal_ids
        return self.orchestrator.run_full(self.username, self.settings, **options)


class MoreRecommendationsWorker(BaseWorker):
    def __init__(
        self,
        orchestrator: PipelineOrchestrator,
        username: str,
        settings: PipelineSettings,
        *,
        existing_recommendations=(),
        genre_adjustments: dict[str, float] | None = None,
        excluded_mal_ids=(),
        count: int = 5,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.orchestrator = orchestrator
        self.username = username
        self.settings = settings
        self.existing_recommendations = tuple(existing_recommendations)
        self.genre_adjustments = dict(genre_adjustments or {})
        self.excluded_mal_ids = frozenset(excluded_mal_ids or ())
        self.count = count

    def execute(self) -> object:
        return self.orchestrator.run_more(
            self.username,
            self.settings,
            existing_recommendations=self.existing_recommendations,
            genre_adjustments=self.genre_adjustments,
            excluded_mal_ids=self.excluded_mal_ids,
            count=self.count,
            progress_callback=self.report_progress,
            cancellation_token=self.cancellation_token,
        )


class OAuthWorker(BaseWorker):
    def __init__(
        self,
        auth_service: AuthService,
        profile_id: str,
        settings: AppSettings,
        *,
        callback_timeout_seconds: float = 180,
        **worker_options,
    ) -> None:
        super().__init__(**worker_options)
        self.auth_service = auth_service
        self.profile_id = profile_id
        self.settings = settings
        self.callback_timeout_seconds = callback_timeout_seconds

    def execute(self) -> object:
        self.report_progress(
            PipelineProgress(
                stage_id=OAUTH_STEP_ID,
                message=STEP_LABELS[OAUTH_STEP_ID],
                current=0,
                total=0,
                cancellable=True,
            )
        )
        return self.auth_service.authorize(
            self.profile_id,
            self.settings,
            callback_timeout_seconds=self.callback_timeout_seconds,
            cancellation=self.cancellation_token,
            status_callback=self._report_oauth_status,
        )

    def _report_oauth_status(self, status_id: str) -> None:
        self.step_changed.emit(status_id, status_id)
