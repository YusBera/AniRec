"""The composition root, shared with the desktop launcher.

``gui_main.main()`` builds exactly this graph before it constructs a window.
Nothing is re-implemented here: the same services, wired the same way, with
the same optional ``root_override`` that lets a test point the whole
application at a temporary directory.

Keeping the graph in one place is what makes the two clients honest with each
other. If the API ever built a ``PipelineOrchestrator`` with, say, no
``anime_graph``, the web feed would quietly lose the collaborative signal and
nothing would fail - it would just recommend differently to the same person on
the same data. So the desktop path should eventually call ``build_container``
too; that change is deliberately not made yet, because the point of this stage
is to add a second client without touching the first.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..application.pipeline import PipelineOrchestrator
from ..errors import AuthError
from ..infrastructure.csv_storage import CsvStorage
from ..infrastructure.mal_client import MALClient
from ..services import (
    AnimeDataService,
    AnimeGraphService,
    AuthService,
    BundleContextService,
    CoverImageService,
    DataManagementService,
    MalSyncService,
    OnboardingService,
    ProfileService,
    ProfileStatisticsService,
    RecommendationService,
    RecommendationStateService,
    ResultService,
    SampleDataService,
    SettingsService,
    TasteFeedbackService,
    TokenStore,
)


@dataclass(frozen=True)
class ApiContainer:
    """Every service one request may need, constructed once per process."""

    settings: SettingsService
    tokens: TokenStore
    profiles: ProfileService
    auth: AuthService
    orchestrator: PipelineOrchestrator
    onboarding: OnboardingService
    results: ResultService
    recommendation_state: RecommendationStateService
    data_management: DataManagementService
    mal_sync: MalSyncService
    taste_feedback: TasteFeedbackService
    covers: CoverImageService
    samples: SampleDataService
    bundles: BundleContextService
    statistics: ProfileStatisticsService

    def active_profile_id(self) -> str | None:
        profile = self.profiles.active_profile()
        return None if profile is None else profile.profile_id

    def active_username(self) -> str | None:
        profile = self.profiles.active_profile()
        return None if profile is None else profile.username


def build_container(root_override: str | Path | None = None) -> ApiContainer:
    """Construct the service graph. Mirrors ``gui_main.main()``."""
    settings = SettingsService(root_override=root_override)
    tokens = TokenStore(root_override=root_override)
    profiles = ProfileService(
        root_override=root_override,
        mal_client=MALClient(),
        token_store=tokens,
    )
    auth = AuthService(token_store=tokens)

    def access_token_provider() -> str:
        profile = profiles.active_profile()
        if profile is None:
            raise AuthError("No active profile is available.")
        return auth.get_access_token(profile.profile_id, settings.load())

    orchestrator = PipelineOrchestrator(
        anime_data=AnimeDataService(),
        profiles=profiles,
        recommendations=RecommendationService(),
        storage=CsvStorage(),
        access_token_provider=access_token_provider,
        client_id_provider=lambda: settings.load().client_id or "",
        anime_graph=AnimeGraphService(),
    )
    return ApiContainer(
        settings=settings,
        tokens=tokens,
        profiles=profiles,
        auth=auth,
        orchestrator=orchestrator,
        onboarding=OnboardingService(
            settings=settings,
            profiles=profiles,
            tokens=tokens,
            root_override=root_override,
        ),
        results=ResultService(root_override=root_override),
        recommendation_state=RecommendationStateService(root_override=root_override),
        data_management=DataManagementService(root_override=root_override),
        mal_sync=MalSyncService(),
        taste_feedback=TasteFeedbackService(),
        covers=CoverImageService(root_override=root_override),
        samples=SampleDataService(),
        bundles=BundleContextService(),
        statistics=ProfileStatisticsService(profiles),
    )
