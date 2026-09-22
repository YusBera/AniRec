"""Qt-independent full and single-step AniRec pipeline orchestration."""

from __future__ import annotations

import threading
from dataclasses import replace
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

try:
    from ..core.mal_mapping import anime_from_row
    from ..errors import AniRecError, CancelledError, DataError
    from ..genre_utils import parse_genres
    from ..infrastructure.csv_storage import CsvStorage
    from ..models import (
        Anime,
        GenreStat,
        PipelineProgress,
        PipelineResult,
        PipelineSettings,
        Recommendation,
    )
    from ..scoring.collaborative import (
        collaborative_scores,
        franchise_exclusions,
        select_seeds,
    )
    from ..scoring.taste import build_taste_profile
    from ..services import (
        AnimeDataService,
        AnimeGraphService,
        ProfileService,
        RecommendationService,
    )
    from ..title_utils import normalize_title_key
except ImportError:  # Backward compatibility for ``python AniRec/main.py``.
    from core.mal_mapping import anime_from_row
    from errors import AniRecError, CancelledError, DataError
    from genre_utils import parse_genres
    from infrastructure.csv_storage import CsvStorage
    from models import (
        Anime,
        GenreStat,
        PipelineProgress,
        PipelineResult,
        PipelineSettings,
        Recommendation,
    )
    from scoring.collaborative import (
        collaborative_scores,
        franchise_exclusions,
        select_seeds,
    )
    from scoring.taste import build_taste_profile
    from services import (
        AnimeDataService,
        AnimeGraphService,
        ProfileService,
        RecommendationService,
    )
    from title_utils import normalize_title_key


OAUTH_STEP_ID = "oauth"
FULL_PIPELINE_STEP_IDS = (
    "fetch_top",
    "fetch_completed",
    "impute_scores",
    "genre_importance",
    "generate_candidates",
    "generate_recommendations",
)
SYNC_STEP_IDS = ("fetch_top", "fetch_completed")
SINGLE_STEP_IDS = (OAUTH_STEP_ID, *FULL_PIPELINE_STEP_IDS)
STEP_LABELS = {
    OAUTH_STEP_ID: "Connect MyAnimeList account",
    # The stable step id is retained for API compatibility; the operation now
    # loads the installed AniRec catalogue and only uses MAL ranking as an
    # explicitly labelled legacy fallback when no catalogue is installed.
    "fetch_top": "Load candidate catalogue",
    "fetch_completed": "Fetch completed anime",
    "impute_scores": "Handle missing scores",
    "genre_importance": "Calculate genre importance",
    "generate_candidates": "Generate recommendation candidates",
    "generate_recommendations": "Generate recommendations",
}

CANDIDATE_CATALOGUE_FILENAME = "candidate_catalogue.csv"
CATALOGUE_SOURCE_COLUMN = "Candidate Catalogue Source"
OWNED_CATALOGUE_SOURCE = "installed-model-catalogue"
LEGACY_MAL_CATALOGUE_SOURCE = "mal-ranking-legacy"


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise CancelledError("Pipeline cancellation requested.")


class PipelineOrchestrator:
    def __init__(
        self,
        *,
        anime_data: AnimeDataService,
        profiles: ProfileService,
        recommendations: RecommendationService,
        storage: CsvStorage,
        access_token_provider: Callable[[], str] | None = None,
        client_id_provider: Callable[[], str] | None = None,
        clock: Callable[[], datetime] = _default_clock,
        anime_graph: AnimeGraphService | None = None,
    ) -> None:
        self._anime_data = anime_data
        self._profiles = profiles
        self._recommendations = recommendations
        self._storage = storage
        # Optional throughout. Without it, scoring runs on content and
        # community rating alone.
        self._anime_graph = anime_graph
        self._access_token_provider = access_token_provider
        self._client_id_provider = client_id_provider
        self._clock = clock

    def run_sync(
        self,
        username: str,
        settings: PipelineSettings,
        *,
        progress_callback: Callable[[PipelineProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> PipelineResult:
        """Persist the candidate catalogue and current MAL user datasets."""
        token = cancellation_token or CancellationToken()
        profile = self._profiles.resolve_profile(username)
        directory = self._profiles.directory(profile.profile_id, create=True)
        started_at = self._timestamp()
        credentials = self._checked_credentials(token)

        self._emit(progress_callback, "fetch_top", 1, len(SYNC_STEP_IDS))
        token.raise_if_cancelled()
        candidate_catalogue = self._load_candidate_catalogue(
            settings, token, credentials=credentials
        )
        token.raise_if_cancelled()
        self._emit(progress_callback, "fetch_completed", 2, len(SYNC_STEP_IDS))
        token.raise_if_cancelled()
        completed = self._anime_data.fetch_completed_anime(
            username,
            include_nsfw=settings.include_nsfw,
            **credentials,
            cancellation_token=token,
        )
        self._require_nonempty(completed, "MyAnimeList returned no completed anime data.")
        history = self._fetch_user_history(
            username, settings, credentials, token
        )
        token.raise_if_cancelled()
        sources = [
            (candidate_catalogue, directory / CANDIDATE_CATALOGUE_FILENAME),
            (completed, directory / "completed_anime.csv"),
        ]
        if history is not None and not history.empty:
            sources.append((history, directory / "user_history.csv"))
        generated = self._storage.write_batch(
            tuple(sources),
            cancellation_check=token.raise_if_cancelled,
        )
        self._profiles.mark_synced(profile)

        return PipelineResult(
            user_stats={
                "username": username,
                "candidate_catalogue_count": len(candidate_catalogue),
                "candidate_catalogue_source": self._catalogue_source(
                    candidate_catalogue
                ),
                "completed_count": len(completed),
                "rated_count": self._rated_count(completed),
            },
            generated_files=tuple(str(path) for path in generated),
            started_at=started_at,
            completed_at=self._timestamp(),
        )

    def run_full(
        self,
        username: str,
        settings: PipelineSettings,
        *,
        progress_callback: Callable[[PipelineProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
        genre_adjustments: dict[str, float] | None = None,
        excluded_mal_ids: set[int] | frozenset[int] = frozenset(),
    ) -> PipelineResult:
        token = cancellation_token or CancellationToken()
        profile = self._profiles.resolve_profile(username)
        directory = self._profiles.directory(profile.profile_id, create=True)
        started_at = self._timestamp()
        credentials = self._checked_credentials(token)

        self._emit(progress_callback, "fetch_top", 1, 6)
        token.raise_if_cancelled()
        candidate_catalogue = self._load_candidate_catalogue(
            settings, token, credentials=credentials
        )
        token.raise_if_cancelled()

        self._emit(progress_callback, "fetch_completed", 2, 6)
        token.raise_if_cancelled()
        completed = self._anime_data.fetch_completed_anime(
            username,
            include_nsfw=settings.include_nsfw,
            **credentials,
            cancellation_token=token,
        )
        self._require_nonempty(completed, "MyAnimeList returned no completed anime data.")
        history = self._fetch_user_history(
            username, settings, credentials, token
        )
        token.raise_if_cancelled()

        self._emit(progress_callback, "impute_scores", 3, 6)
        token.raise_if_cancelled()
        imputed = self._recommendations.impute_missing_scores(completed)
        fallback_candidates = self._recommendations.create_candidates(
            imputed, candidate_catalogue
        )
        token.raise_if_cancelled()

        self._emit(progress_callback, "genre_importance", 4, 6)
        token.raise_if_cancelled()
        # Learn taste from what the user actually rated, not from the imputed
        # frame. Feeding filled-in scores back in made AniRec measure its own
        # guesses and counted unrated titles toward every genre's share.
        genre_importance = self._recommendations.calculate_genre_importance(
            completed, candidate_catalogue
        )
        self._require_nonempty(genre_importance, "No genre importance scores were generated.")
        token.raise_if_cancelled()

        self._emit(progress_callback, "generate_candidates", 5, 6)
        token.raise_if_cancelled()
        candidates = self._recommendations.create_candidates(
            imputed, candidate_catalogue
        )
        self._require_nonempty(candidates, "No recommendation candidates were generated.")
        token.raise_if_cancelled()

        self._emit(progress_callback, "generate_recommendations", 6, 6)
        token.raise_if_cancelled()
        collaborative, franchise_ids = self._collaborative_signal(
            completed, directory, credentials, token
        )
        ranked = self._recommendations.recommend(
            candidates,
            genre_importance,
            settings,
            genre_adjustments=genre_adjustments,
            excluded_mal_ids=set(excluded_mal_ids) | franchise_ids,
            collaborative_scores=collaborative,
            user_history=history,
            fallback_candidates=fallback_candidates,
            consumed_mal_ids=self._mal_ids(completed),
            include_nsfw=settings.include_nsfw,
            as_of=self._clock().date(),
        )
        self._require_nonempty(ranked, "No recommendations were generated.")
        ranking_metadata = ranked.attrs.get("ranking_engine")
        eligibility_audit = ranked.attrs.get("eligibility_audit")
        token.raise_if_cancelled()
        recommendation_path = directory / f"{profile.profile_id}_recommendations.csv"
        outputs = [
            (candidate_catalogue, directory / CANDIDATE_CATALOGUE_FILENAME),
            (completed, directory / "completed_anime.csv"),
            (imputed, directory / "completed_anime_imputed.csv"),
            (genre_importance, directory / "genre_importance.csv"),
            (candidates, directory / "recommendation_candidates.csv"),
            (ranked, recommendation_path),
        ]
        if history is not None and not history.empty:
            outputs.append((history, directory / "user_history.csv"))
        generated_paths = self._storage.write_batch(
            tuple(outputs),
            cancellation_check=token.raise_if_cancelled,
        )
        self._profiles.mark_synced(profile)

        return PipelineResult(
            recommendations=self._recommendation_models(ranked),
            genre_stats=self._genre_models(genre_importance, completed),
            user_stats={
                "completed_count": len(completed),
                "rated_count": self._rated_count(completed),
                "candidate_count": len(candidates),
                "candidate_catalogue_count": len(candidate_catalogue),
                "candidate_catalogue_source": self._catalogue_source(
                    candidate_catalogue
                ),
                "recommendation_count": len(ranked),
                **self._ranking_user_stats(
                    ranking_metadata,
                    eligibility_audit,
                ),
            },
            generated_files=tuple(str(path) for path in generated_paths),
            started_at=started_at,
            completed_at=self._timestamp(),
        )

    def run_more(
        self,
        username: str,
        settings: PipelineSettings,
        *,
        existing_recommendations: tuple[Recommendation, ...] = (),
        genre_adjustments: dict[str, float] | None = None,
        excluded_mal_ids: set[int] | frozenset[int] = frozenset(),
        count: int = 5,
        progress_callback: Callable[[PipelineProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> PipelineResult:
        """Generate additional feedback-aware picks from the persisted candidate pool."""

        token = cancellation_token or CancellationToken()
        profile = self._profiles.resolve_profile(username)
        directory = self._profiles.directory(profile.profile_id, create=True)
        started_at = self._timestamp()
        self._emit(progress_callback, "generate_recommendations", 1, 1)
        token.raise_if_cancelled()
        candidates = self._storage.read(
            directory / "recommendation_candidates.csv",
            required_columns=["Title", "Genres"],
        )
        importance = self._storage.read(
            directory / "genre_importance.csv",
            required_columns=["Genre", "Importance_Score"],
        )
        history = self._read_user_history(directory)
        completed = self._read_completed(directory)
        candidate_catalogue = self._read_candidate_catalogue(directory)
        fallback_candidates = candidates
        excluded_ids = {
            item.anime.mal_id
            for item in existing_recommendations
            if item.anime.mal_id is not None
        }
        # Titles the user has already rejected or hidden must not reappear here
        # either; run_more previously only skipped what was already on screen.
        excluded_ids |= {int(value) for value in (excluded_mal_ids or ()) if value}
        excluded_titles = {
            normalize_title_key(item.anime.title) for item in existing_recommendations
        }
        excluded_titles.discard("")
        more_settings = replace(
            settings,
            recommendation_count=max(1, int(count)),
            candidate_pool_size=max(settings.candidate_pool_size, int(count)),
            seed=None,
        )
        ranked = self._recommendations.recommend(
            candidates,
            importance,
            more_settings,
            genre_adjustments=genre_adjustments,
            excluded_mal_ids=excluded_ids,
            excluded_titles=excluded_titles,
            user_history=history,
            fallback_candidates=fallback_candidates,
            consumed_mal_ids=self._mal_ids(completed),
            include_nsfw=settings.include_nsfw,
            as_of=self._clock().date(),
        )
        self._require_nonempty(ranked, "No unseen recommendations remain in the candidate pool.")
        ranking_metadata = ranked.attrs.get("ranking_engine")
        eligibility_audit = ranked.attrs.get("eligibility_audit")
        token.raise_if_cancelled()
        new_recommendations = self._recommendation_models(ranked)
        combined = tuple(existing_recommendations) + new_recommendations
        combined = tuple(
            replace(item, rank=index) for index, item in enumerate(combined, start=1)
        )
        return PipelineResult(
            recommendations=combined,
            user_stats={
                "recommendation_count": len(combined),
                "added_recommendation_count": len(new_recommendations),
                "candidate_catalogue_count": len(candidate_catalogue),
                "candidate_catalogue_source": self._catalogue_source(
                    candidate_catalogue
                ),
                "candidate_snapshot_count": len(candidates),
                **self._ranking_user_stats(
                    ranking_metadata,
                    eligibility_audit,
                ),
            },
            started_at=started_at,
            completed_at=self._timestamp(),
        )

    def run_step(
        self,
        step_id: str,
        username: str,
        settings: PipelineSettings,
        *,
        progress_callback: Callable[[PipelineProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> PipelineResult:
        if step_id not in SINGLE_STEP_IDS:
            raise ValueError(f"Unknown pipeline step: {step_id}")

        token = cancellation_token or CancellationToken()
        profile = self._profiles.resolve_profile(username)
        directory = self._profiles.directory(profile.profile_id, create=True)
        started_at = self._timestamp()
        self._emit(progress_callback, step_id, 1, 1)
        token.raise_if_cancelled()

        if step_id == OAUTH_STEP_ID:
            self._checked_credentials(token)
            return self._step_result(started_at, user_stats={"oauth_connected": 1})

        if step_id == "fetch_top":
            frame = self._load_candidate_catalogue(
                settings,
                token,
            )
            return self._write_step(
                frame,
                directory / CANDIDATE_CATALOGUE_FILENAME,
                started_at,
                token,
                user_stats={
                    "candidate_catalogue_count": len(frame),
                    "candidate_catalogue_source": self._catalogue_source(frame),
                },
            )

        if step_id == "fetch_completed":
            frame = self._anime_data.fetch_completed_anime(
                username,
                include_nsfw=settings.include_nsfw,
                **self._checked_credentials(token),
                cancellation_token=token,
            )
            self._require_nonempty(frame, "MyAnimeList returned no completed anime data.")
            history = self._fetch_user_history(
                username, settings, self._checked_credentials(token), token
            )
            if history is not None and not history.empty:
                paths = self._storage.write_batch(
                    (
                        (frame, directory / "completed_anime.csv"),
                        (history, directory / "user_history.csv"),
                    ),
                    cancellation_check=token.raise_if_cancelled,
                )
                return PipelineResult(
                    generated_files=tuple(str(path) for path in paths),
                    started_at=started_at,
                    completed_at=self._timestamp(),
                )
            return self._write_step(
                frame,
                directory / "completed_anime.csv",
                started_at,
                token,
            )

        completed = self._read_completed(directory)
        if step_id == "impute_scores":
            frame = self._recommendations.impute_missing_scores(completed)
            return self._write_step(
                frame,
                directory / "completed_anime_imputed.csv",
                started_at,
                token,
            )

        if step_id == "genre_importance":
            candidate_catalogue = self._read_candidate_catalogue(directory)
            frame = self._recommendations.calculate_genre_importance(
                completed, candidate_catalogue
            )
            self._require_nonempty(frame, "No genre importance scores were generated.")
            path = directory / "genre_importance.csv"
            result = self._write_step(frame, path, started_at, token)
            return PipelineResult(
                genre_stats=self._genre_models(frame, completed),
                generated_files=result.generated_files,
                started_at=result.started_at,
                completed_at=result.completed_at,
            )

        candidate_catalogue = self._read_candidate_catalogue(directory)
        if step_id == "generate_candidates":
            frame = self._recommendations.create_candidates(
                completed, candidate_catalogue
            )
            self._require_nonempty(frame, "No recommendation candidates were generated.")
            return self._write_step(
                frame,
                directory / "recommendation_candidates.csv",
                started_at,
                token,
            )

        candidates = self._storage.read(
            directory / "recommendation_candidates.csv",
            required_columns=["Title", "Genres"],
        )
        importance = self._storage.read(
            directory / "genre_importance.csv",
            required_columns=["Genre", "Importance_Score"],
        )
        ranked = self._recommendations.recommend(
            candidates,
            importance,
            settings,
            user_history=self._read_user_history(directory),
            fallback_candidates=candidates,
            consumed_mal_ids=self._mal_ids(completed),
            include_nsfw=settings.include_nsfw,
            as_of=self._clock().date(),
        )
        self._require_nonempty(ranked, "No recommendations were generated.")
        ranking_metadata = ranked.attrs.get("ranking_engine")
        eligibility_audit = ranked.attrs.get("eligibility_audit")
        result = self._write_step(
            ranked,
            directory / f"{profile.profile_id}_recommendations.csv",
            started_at,
            token,
        )
        return PipelineResult(
            recommendations=self._recommendation_models(ranked),
            user_stats={
                "candidate_catalogue_count": len(candidate_catalogue),
                "candidate_catalogue_source": self._catalogue_source(
                    candidate_catalogue
                ),
                "candidate_snapshot_count": len(candidates),
                **self._ranking_user_stats(
                    ranking_metadata,
                    eligibility_audit,
                ),
            },
            generated_files=result.generated_files,
            started_at=result.started_at,
            completed_at=result.completed_at,
        )

    def _checked_token(self, cancellation_token: CancellationToken) -> str:
        """Return an OAuth token for compatibility with authenticated CLI flows."""
        cancellation_token.raise_if_cancelled()
        if self._access_token_provider is None:
            raise DataError("No access token provider is configured.")
        access_token = self._access_token_provider()
        cancellation_token.raise_if_cancelled()
        if not access_token:
            raise DataError("The access token provider returned an empty token.")
        return access_token

    def _checked_credentials(self, cancellation_token: CancellationToken) -> dict[str, str]:
        """Prefer the public Client ID flow; fall back to OAuth when configured."""
        cancellation_token.raise_if_cancelled()
        if self._client_id_provider is not None:
            client_id = self._client_id_provider()
            cancellation_token.raise_if_cancelled()
            if client_id:
                return {"client_id": client_id}
        return {"access_token": self._checked_token(cancellation_token)}

    def _read_completed(self, directory: Path) -> pd.DataFrame:
        imputed = directory / "completed_anime_imputed.csv"
        path = imputed if imputed.exists() else directory / "completed_anime.csv"
        return self._storage.read(path, required_columns=["Title", "Genres", "User Score"])

    def _read_candidate_catalogue(self, directory: Path) -> pd.DataFrame:
        current = directory / CANDIDATE_CATALOGUE_FILENAME
        if current.exists():
            return self._storage.read(current, required_columns=["Title", "Genres"])

        # Existing profiles may predate the owned-catalogue boundary. Preserve
        # their ability to finish a staged operation, but label the old source
        # explicitly instead of presenting it as AniRec-owned data.
        legacy = self._storage.read(
            directory / "top_anime.csv",
            required_columns=["Title", "Genres"],
        ).copy()
        legacy[CATALOGUE_SOURCE_COLUMN] = LEGACY_MAL_CATALOGUE_SOURCE
        return legacy

    def _read_user_history(self, directory: Path) -> pd.DataFrame | None:
        if not self._recommendations.requires_user_history:
            return None
        path = directory / "user_history.csv"
        if not path.exists():
            return None
        return self._storage.read(
            path,
            required_columns=[
                "Anime ID",
                "Status",
                "User Score",
                "Episodes Watched",
                "Is Rewatching",
                "Updated At",
            ],
        )

    def _fetch_user_history(self, username, settings, credentials, token):
        if not self._recommendations.requires_user_history:
            return None
        try:
            return self._anime_data.fetch_user_history(
                username,
                include_nsfw=settings.include_nsfw,
                **credentials,
                cancellation_token=token,
            )
        except CancelledError:
            raise
        except AniRecError:
            # The fallback engine will report that current history was unavailable.
            return None

    def _load_candidate_catalogue(
        self,
        settings: PipelineSettings,
        token: CancellationToken,
        *,
        credentials: dict[str, str] | None = None,
    ) -> pd.DataFrame:
        owned = self._recommendations.candidate_catalog(
            include_nsfw=settings.include_nsfw,
            as_of=self._clock().date(),
        )
        if owned is not None:
            if owned.empty:
                raise DataError(
                    "The installed candidate catalogue has no eligible titles; "
                    "refusing to switch silently to MyAnimeList ranking data."
                )
            catalogue = owned.copy()
            catalogue[CATALOGUE_SOURCE_COLUMN] = OWNED_CATALOGUE_SOURCE
            return catalogue

        token.raise_if_cancelled()
        legacy = self._anime_data.fetch_top_anime(
            limit=settings.top_anime_limit,
            include_nsfw=settings.include_nsfw,
            **(credentials or self._checked_credentials(token)),
            cancellation_token=token,
        )
        self._require_nonempty(legacy, "No installed catalogue or MAL ranking data is available.")
        catalogue = legacy.copy()
        catalogue[CATALOGUE_SOURCE_COLUMN] = LEGACY_MAL_CATALOGUE_SOURCE
        return catalogue

    def _write_step(
        self,
        frame: pd.DataFrame,
        path: Path,
        started_at: str,
        token: CancellationToken,
        user_stats: dict[str, int | float | str] | None = None,
    ) -> PipelineResult:
        token.raise_if_cancelled()
        output = self._storage.write(frame, path)
        return self._step_result(
            started_at,
            generated_files=(str(output),),
            user_stats=user_stats,
        )

    def _step_result(
        self,
        started_at: str,
        *,
        generated_files: tuple[str, ...] = (),
        user_stats: dict[str, int | float | str] | None = None,
    ) -> PipelineResult:
        return PipelineResult(
            user_stats=user_stats or {},
            generated_files=generated_files,
            started_at=started_at,
            completed_at=self._timestamp(),
        )

    @staticmethod
    def _require_nonempty(frame: pd.DataFrame, message: str) -> None:
        if frame.empty:
            raise DataError(message)

    @staticmethod
    def _rated_count(frame: pd.DataFrame) -> int:
        if "User Score" not in frame.columns:
            return 0
        scores = pd.to_numeric(frame["User Score"], errors="coerce").fillna(0)
        return int((scores > 0).sum())

    @staticmethod
    def _catalogue_source(frame: pd.DataFrame) -> str:
        if CATALOGUE_SOURCE_COLUMN not in frame.columns or frame.empty:
            return "unknown"
        values = {
            str(value).strip()
            for value in frame[CATALOGUE_SOURCE_COLUMN].dropna().tolist()
            if str(value).strip()
        }
        return next(iter(values)) if len(values) == 1 else "mixed"

    @staticmethod
    def _emit(
        callback: Callable[[PipelineProgress], None] | None,
        step_id: str,
        current: int,
        total: int,
    ) -> None:
        if callback:
            callback(
                PipelineProgress(
                    stage_id=step_id,
                    message=STEP_LABELS[step_id],
                    current=current,
                    total=total,
                    cancellable=True,
                )
            )

    @staticmethod
    def _ranking_user_stats(metadata, eligibility=None) -> dict[str, int | str]:
        stats: dict[str, int | str] = {}
        if metadata is not None:
            stats.update({
                "ranking_engine_id": metadata.engine_id,
                "ranking_engine_version": metadata.engine_version,
                "ranking_fallback_used": int(metadata.fallback_used),
            })
            if metadata.requested_engine_id:
                stats["ranking_requested_engine_id"] = metadata.requested_engine_id
        if eligibility is not None:
            stats.update({
                "eligibility_policy_version": eligibility.policy_version,
                "eligibility_catalog_version": eligibility.catalog_version,
                "eligibility_input_count": eligibility.input_candidates,
                "eligibility_eligible_count": eligibility.eligible_candidates,
                "eligibility_excluded_count": eligibility.excluded_candidates,
            })
            stats.update({
                f"eligibility_excluded_{reason}": count
                for reason, count in eligibility.excluded_by_reason.items()
            })
        return stats

    @staticmethod
    def _mal_ids(frame: pd.DataFrame) -> set[int]:
        if "Anime ID" not in frame.columns:
            return set()
        return set(
            pd.to_numeric(frame["Anime ID"], errors="coerce")
            .dropna()
            .astype(int)
            .loc[lambda values: values > 0]
            .tolist()
        )

    @staticmethod
    def _recommendation_models(frame: pd.DataFrame) -> tuple[Recommendation, ...]:
        models = []
        for rank, (_, row) in enumerate(frame.iterrows(), start=1):
            anime = anime_from_row(row)
            models.append(
                Recommendation(
                    anime=anime,
                    match_score=row.get("Match Score", 0.0),
                    match_score_available=bool(row.get("Match Score Available", True)),
                    raw_score=row.get("Recommendation Score", 0.0),
                    contributing_genres=tuple(row.get("Contributing Genres") or ()),
                    genre_contributions=tuple(row.get("Genre Contributions") or ()),
                    reason=row.get("Recommendation Reason"),
                    rank=rank,
                )
            )
        return tuple(models)

    def _collaborative_signal(self, completed, directory, credentials, token):
        """Walk the recommendation graph out from the user's favourites.

        Entirely best effort. Any failure leaves the run scoring on content and
        community rating alone rather than losing the recommendations, which is
        why every outcome here returns empty rather than raising.
        """
        if self._anime_graph is None or completed is None or completed.empty:
            return {}, set()
        if "Anime ID" not in completed.columns:
            return {}, set()

        try:
            profile = build_taste_profile(completed)
            spread = profile.rating_spread or 1.0
            rated = [
                (
                    row.get("Anime ID"),
                    (float(score) - profile.mean_rating) / spread,
                )
                for _index, row in completed.iterrows()
                if (score := pd.to_numeric(row.get("User Score"), errors="coerce"))
                is not None
                and pd.notna(score)
                and float(score) > 0
            ]
            seeds = select_seeds(rated)
            if not seeds:
                return {}, set()
            graph = self._anime_graph.build_graph(
                [mal_id for mal_id, _weight in seeds],
                directory,
                access_token=credentials.get("access_token"),
                client_id=credentials.get("client_id"),
                cancellation=token,
            )
            if not graph:
                return {}, set()
            return collaborative_scores(seeds, graph), franchise_exclusions(graph)
        except CancelledError:
            raise
        except Exception:  # noqa: BLE001 - an optional signal must never break a run
            return {}, set()

    @staticmethod
    def _genre_models(
        frame: pd.DataFrame,
        completed: pd.DataFrame | None = None,
    ) -> tuple[GenreStat, ...]:
        summaries = PipelineOrchestrator._genre_summaries(completed)
        models = []
        for _, row in frame.iterrows():
            summary = summaries.get(str(row["Genre"]), {})
            scores = summary.get("scores", ())
            models.append(
                GenreStat(
                    genre=row["Genre"],
                    importance_score=row["Importance_Score"],
                    completed_count=summary.get("completed_count", 0),
                    average_user_score=(sum(scores) / len(scores)) if scores else None,
                    missing_score_count=summary.get("missing_score_count", 0),
                    example_titles=tuple(summary.get("titles", ())[:3]),
                )
            )
        return tuple(models)

    @staticmethod
    def _genre_summaries(completed: pd.DataFrame | None) -> dict[str, dict]:
        """Per-genre counts backing the taste panel.

        Built from the raw completed list rather than the imputed one, so that
        "average user score" reports what the user actually rated instead of
        values AniRec filled in for them.
        """
        if completed is None or completed.empty or "Genres" not in completed.columns:
            return {}
        summaries: dict[str, dict] = {}
        for _, row in completed.iterrows():
            score = pd.to_numeric(row.get("User Score"), errors="coerce")
            rated = pd.notna(score) and float(score) > 0
            title = str(row.get("Title") or "").strip()
            for genre in dict.fromkeys(parse_genres(row.get("Genres"))):
                summary = summaries.setdefault(
                    genre,
                    {"completed_count": 0, "missing_score_count": 0, "scores": [], "titles": []},
                )
                summary["completed_count"] += 1
                if rated:
                    summary["scores"].append(float(score))
                else:
                    summary["missing_score_count"] += 1
                if title:
                    summary["titles"].append(title)
        return summaries

    def _timestamp(self) -> str:
        return self._clock().astimezone(timezone.utc).isoformat()
