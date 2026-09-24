"""Read-only workspace boundary over the existing desktop providers.

Sample reports are opt-in; a missing live report never becomes sample evidence.
Settings are allowlisted so credentials cannot enter the browser response.
"""

from dataclasses import replace
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field

from ..core.mal_mapping import ANIME_FIELDS, anime_from_node, anime_from_row
from ..infrastructure.csv_storage import CsvStorage
from ..infrastructure.mal_client import MALClient
from ..services.anime_data_service import AnimeDataService
from ..services.profile_service import username_from_profile_reference
from ..services.workspace_service import ComparisonClient, compare_completed, metadata_model
from ..presentation import recommendation_view_models

from ..presentation.taste_profile import (
    LocalTasteProfileProvider, SampleTasteProfileProvider, TasteProfile,
    TasteProfileUnavailable,
    Archetype, archetype_for,
)
from ..presentation.compatibility import (
    CompatibilityReport, CompatibilityUnavailable, SampleCompatibilityProvider,
)
from ..services.account_service import AccountError
from .accounts import ReaderScope, resolve_scope
from .container import ApiContainer
from .models import ApiModel, RecommendationViewModelResponse
from .serialization import view_model_to_dict


class ProfileReadResponse(ApiModel):
    profile: TasteProfile | None = None
    reason: str | None = None
    archetype: Archetype | None = None


class CompareReadResponse(ApiModel):
    report: CompatibilityReport | None = None
    reason: str | None = None
    sample_names: tuple[str, ...] = ()


class SettingsReadResponse(ApiModel):
    adventurousness: int
    batch_size: int
    minimum_mal_score: float | None
    default_sort: Literal["personal-match", "mal-score", "year", "alphabetical"]
    include_hidden: bool
    include_nsfw: bool
    background_sync: bool
    theme: Literal["system", "dark", "light", "oled", "gradient"]
    gui_scale: float
    font_scale: float
    show_covers: bool
    client_id_present: bool
    username: str | None
    using_defaults: bool
    can_edit: bool = Field(
        default=False,
        description="Whether this account owns the installation and may save these settings (D-021).",
    )


class SettingsWriteRequest(ApiModel):
    adventurousness: int = Field(ge=1, le=10)
    batch_size: int = Field(ge=1, le=150)
    minimum_mal_score: float | None = Field(ge=0, le=10)
    default_sort: Literal["personal-match", "mal-score", "year", "alphabetical"]
    include_hidden: bool
    include_nsfw: bool
    background_sync: bool
    theme: Literal["system", "dark", "light", "oled", "gradient"]
    gui_scale: float = Field(ge=0.75, le=1.5)
    font_scale: float = Field(ge=0.8, le=1.4)
    show_covers: bool


class LibraryReadResponse(ApiModel):
    profile_id: str
    recommendations: tuple[RecommendationViewModelResponse, ...] = ()


class LibraryResolveRequest(ApiModel):
    profile_id: str
    mal_id: int = Field(gt=0)


def workspace_router(services: ApiContainer) -> APIRouter:
    router = APIRouter(prefix="/api/workspace")
    settings_lock = Lock()

    def reader(request: Request) -> ReaderScope:
        return resolve_scope(services, request)

    def owned(scope: ReaderScope, profile_id):
        """The directory of ``profile_id``, only when it is this reader's import now."""
        if not profile_id or scope.profile_id != profile_id:
            raise HTTPException(409, "Active profile changed. Reload this view.")
        return services.profiles.directory(profile_id)

    def still_owned(request: Request, profile_id) -> None:
        """Re-checked after a slow read: the reader may have signed out meanwhile."""
        owned(resolve_scope(services, request), profile_id)

    @router.get("/library", response_model=LibraryReadResponse)
    def library(profile_id: str, request: Request, scope: ReaderScope = Depends(reader)) -> LibraryReadResponse:
        directory = owned(scope, profile_id)
        state = services.recommendation_state.load(profile_id)
        wanted = set(state.watch_later_mal_ids) | set(state.hidden_mal_ids)
        found = {}
        result = services.results.load(profile_id)
        if result:
            found.update((m.mal_id, m) for m in recommendation_view_models(result.recommendations) if m.mal_id in wanted)
        for filename in (
            "completed_anime.csv",
            "candidate_catalogue.csv",
            "top_anime.csv",
            "recommendation_candidates.csv",
        ):
            path = directory / filename
            if not path.exists():
                continue
            for _, row in CsvStorage().read(path).iterrows():
                anime = anime_from_row(row)
                if anime.mal_id in wanted and anime.mal_id not in found:
                    found[anime.mal_id] = metadata_model(anime)
        still_owned(request, profile_id)
        return LibraryReadResponse(profile_id=profile_id, recommendations=tuple(view_model_to_dict(m) for m in found.values()))

    @router.post("/library/resolve", response_model=RecommendationViewModelResponse)
    def resolve_title(payload: LibraryResolveRequest, request: Request, scope: ReaderScope = Depends(reader)):
        owned(scope, payload.profile_id)
        state = services.recommendation_state.load(payload.profile_id)
        if payload.mal_id not in set(state.watch_later_mal_ids) | set(state.hidden_mal_ids):
            raise HTTPException(400, "Only saved decisions can be resolved here.")
        client_id = services.settings.load().client_id
        if not client_id:
            raise HTTPException(409, "Configure a MAL Client ID in the desktop app first.")
        node = MALClient().get_json(f"https://api.myanimelist.net/v2/anime/{payload.mal_id}",
                                    params={"fields": ANIME_FIELDS}, client_id=client_id)
        anime = anime_from_node(node)
        if anime is None or anime.mal_id != payload.mal_id:
            raise HTTPException(502, "MyAnimeList returned invalid title details.")
        still_owned(request, payload.profile_id)
        return view_model_to_dict(metadata_model(anime))

    @router.get("/profile", response_model=ProfileReadResponse)
    def profile(sample: bool = False, scope: ReaderScope = Depends(reader)) -> ProfileReadResponse:
        provider = (SampleTasteProfileProvider() if sample
                    else LocalTasteProfileProvider(services.statistics, profile=scope.profile))
        try:
            report = provider.taste_profile()
            return ProfileReadResponse(profile=report, archetype=archetype_for(report))
        except TasteProfileUnavailable as error:
            return ProfileReadResponse(reason=error.reason.value)

    @router.get("/compare", response_model=CompareReadResponse)
    def compare(
        request: Request, sample: bool = False, username: str = "", scope: ReaderScope = Depends(reader)
    ) -> CompareReadResponse:
        if not sample:
            if not username:
                return CompareReadResponse(reason="username-required")
            name = username_from_profile_reference(username)
            profile_id = scope.profile_id
            if not profile_id:
                return CompareReadResponse(reason="not-connected")
            directory = owned(scope, profile_id)
            client_id = services.settings.load().client_id
            if not client_id:
                return CompareReadResponse(reason="client-id-required")
            path = directory / "completed_anime.csv"
            if not path.is_file():
                return CompareReadResponse(reason="no-local-snapshot")
            yours = CsvStorage().read(path, required_columns=("Anime ID", "Title", "User Score"))
            theirs = AnimeDataService(client=ComparisonClient()).fetch_completed_anime(name, client_id=client_id,
                include_nsfw=services.settings.load().pipeline.include_nsfw)
            still_owned(request, profile_id)
            return CompareReadResponse(report=compare_completed(name, yours, theirs))
        provider = SampleCompatibilityProvider()
        try:
            names = tuple(friend.username for friend in provider.friends())
            if not names:
                return CompareReadResponse(reason="backend-missing")
            return CompareReadResponse(
                report=provider.compare(username or names[0]), sample_names=names,
            )
        except CompatibilityUnavailable as error:
            return CompareReadResponse(reason=error.reason.value)

    def is_owner(scope: ReaderScope) -> bool:
        account = scope.account
        if account is None or not account.registered:
            return False
        try:
            return services.accounts.owner_account_id() == account.account_id
        except AccountError:
            return False

    @router.get("/settings", response_model=SettingsReadResponse)
    def settings(scope: ReaderScope = Depends(reader)) -> SettingsReadResponse:
        saved = services.settings.load()
        return SettingsReadResponse(
            adventurousness=saved.pipeline.randomness_factor,
            batch_size=saved.pipeline.recommendation_count,
            minimum_mal_score=saved.pipeline.minimum_mean_score,
            default_sort=saved.default_recommendation_sort,
            include_hidden=saved.include_hidden_recommendations,
            include_nsfw=saved.pipeline.include_nsfw,
            background_sync=saved.background_sync_enabled,
            theme=saved.theme, gui_scale=saved.gui_scale,
            font_scale=saved.font_scale, show_covers=saved.show_covers,
            client_id_present=bool(saved.client_id),
            username=None if scope.profile is None else scope.profile.username,
            using_defaults=services.settings.last_error is not None,
            can_edit=is_owner(scope),
        )

    @router.post("/settings", response_model=SettingsReadResponse)
    def save_settings(payload: SettingsWriteRequest, scope: ReaderScope = Depends(reader)) -> SettingsReadResponse:
        # These settings rank every account's feed; only the installation
        # owner, named from the console, may change them (docs/ACCOUNTS.md).
        if not is_owner(scope):
            raise HTTPException(403, "Only the owner of this AniRec installation can change these settings.")
        with settings_lock:
            saved = services.settings.load()
            if services.settings.last_error:
                raise HTTPException(409, "Saved settings are unreadable. Repair them in the desktop app before saving.")
            if payload.batch_size > saved.pipeline.candidate_pool_size:
                raise HTTPException(422, f"Batch size cannot exceed the candidate pool ({saved.pipeline.candidate_pool_size}).")
            pipeline = replace(saved.pipeline, randomness_factor=payload.adventurousness,
                recommendation_count=payload.batch_size, minimum_mean_score=payload.minimum_mal_score,
                include_nsfw=payload.include_nsfw)
            services.settings.save_preferences(replace(saved, pipeline=pipeline,
                default_recommendation_sort=payload.default_sort,
                include_hidden_recommendations=payload.include_hidden,
                background_sync_enabled=payload.background_sync, theme=payload.theme,
                gui_scale=payload.gui_scale, font_scale=payload.font_scale, show_covers=payload.show_covers))
            return settings(scope)

    return router
