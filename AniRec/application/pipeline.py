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
    from ..errors import CancelledError, DataError
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
    from ..services import AnimeDataService, ProfileService, RecommendationService
except ImportError:  # Backward compatibility for ``python AniRec/main.py``.
    from core.mal_mapping import anime_from_row
    from errors import CancelledError, DataError
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
    from services import AnimeDataService, ProfileService, RecommendationService


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
    "fetch_top": "Fetch top anime",
    "fetch_completed": "Fetch completed anime",
    "impute_scores": "Handle missing scores",
    "genre_importance": "Calculate genre importance",
    "generate_candidates": "Generate recommendation candidates",
    "generate_recommendations": "Generate recommendations",
}


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
    ) -> None:
        self._anime_data = anime_data
        self._profiles = profiles
        self._recommendations = recommendations
        self._storage = storage
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
        """Fetch and atomically persist the two MAL source datasets."""
        token = cancellation_token or CancellationToken()
        profile = self._profiles.resolve_profile(username)
        directory = self._profiles.directory(profile.profile_id, create=True)
        started_at = self._timestamp()
        credentials = self._checked_credentials(token)

        self._emit(progress_callback, "fetch_top", 1, len(SYNC_STEP_IDS))
        token.raise_if_cancelled()
        top_anime = self._anime_data.fetch_top_anime(
            limit=settings.top_anime_limit,
            include_nsfw=settings.include_nsfw,
            **credentials,
            cancellation_token=token,
        )
        self._require_nonempty(top_anime, "MyAnimeList returned no top anime data.")
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
        token.raise_if_cancelled()
        top_path, completed_path = self._storage.write_batch(
            (
                (top_anime, directory / "top_anime.csv"),
                (completed, directory / "completed_anime.csv"),
            ),
            cancellation_check=token.raise_if_cancelled,
        )
        self._profiles.mark_synced(profile)

        return PipelineResult(
            user_stats={
                "username": username,
                "top_anime_count": len(top_anime),
                "completed_count": len(completed),
                "rated_count": self._rated_count(completed),
            },
            generated_files=(str(top_path), str(completed_path)),
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
        top_anime = self._anime_data.fetch_top_anime(
            limit=settings.top_anime_limit,
            include_nsfw=settings.include_nsfw,
            **credentials,
            cancellation_token=token,
        )
        self._require_nonempty(top_anime, "MyAnimeList returned no top anime data.")
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
        token.raise_if_cancelled()

        self._emit(progress_callback, "impute_scores", 3, 6)
        token.raise_if_cancelled()
        imputed = self._recommendations.impute_missing_scores(completed)
        token.raise_if_cancelled()

        self._emit(progress_callback, "genre_importance", 4, 6)
        token.raise_if_cancelled()
        genre_importance = self._recommendations.calculate_genre_importance(imputed)
        self._require_nonempty(genre_importance, "No genre importance scores were generated.")
        token.raise_if_cancelled()

        self._emit(progress_callback, "generate_candidates", 5, 6)
        token.raise_if_cancelled()
        candidates = self._recommendations.create_candidates(imputed, top_anime)
        self._require_nonempty(candidates, "No recommendation candidates were generated.")
        token.raise_if_cancelled()

        self._emit(progress_callback, "generate_recommendations", 6, 6)
        token.raise_if_cancelled()
        ranked = self._recommendations.recommend(
            candidates,
            genre_importance,
            settings,
            genre_adjustments=genre_adjustments,
            excluded_mal_ids=excluded_mal_ids,
        )
        self._require_nonempty(ranked, "No recommendations were generated.")
        token.raise_if_cancelled()
        recommendation_path = directory / f"{profile.profile_id}_recommendations.csv"
        generated_paths = self._storage.write_batch(
            (
                (top_anime, directory / "top_anime.csv"),
                (completed, directory / "completed_anime.csv"),
                (imputed, directory / "completed_anime_imputed.csv"),
                (genre_importance, directory / "genre_importance.csv"),
                (candidates, directory / "recommendation_candidates.csv"),
                (ranked, recommendation_path),
            ),
            cancellation_check=token.raise_if_cancelled,
        )
        self._profiles.mark_synced(profile)

        return PipelineResult(
            recommendations=self._recommendation_models(ranked),
            genre_stats=self._genre_models(genre_importance),
            user_stats={
                "completed_count": len(completed),
                "candidate_count": len(candidates),
                "recommendation_count": len(ranked),
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
        excluded_ids = {
            item.anime.mal_id
            for item in existing_recommendations
            if item.anime.mal_id is not None
        }
        excluded_titles = {
            item.anime.title.casefold() for item in existing_recommendations
        }
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
        )
        self._require_nonempty(ranked, "No unseen recommendations remain in the candidate pool.")
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
            frame = self._anime_data.fetch_top_anime(
                limit=settings.top_anime_limit,
                include_nsfw=settings.include_nsfw,
                **self._checked_credentials(token),
                cancellation_token=token,
            )
            self._require_nonempty(frame, "MyAnimeList returned no top anime data.")
            return self._write_step(frame, directory / "top_anime.csv", started_at, token)

        if step_id == "fetch_completed":
            frame = self._anime_data.fetch_completed_anime(
                username,
                include_nsfw=settings.include_nsfw,
                **self._checked_credentials(token),
                cancellation_token=token,
            )
            self._require_nonempty(frame, "MyAnimeList returned no completed anime data.")
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
            frame = self._recommendations.calculate_genre_importance(completed)
            self._require_nonempty(frame, "No genre importance scores were generated.")
            path = directory / "genre_importance.csv"
            result = self._write_step(frame, path, started_at, token)
            return PipelineResult(
                genre_stats=self._genre_models(frame),
                generated_files=result.generated_files,
                started_at=result.started_at,
                completed_at=result.completed_at,
            )

        top_anime = self._storage.read(
            directory / "top_anime.csv",
            required_columns=["Title", "Genres"],
        )
        if step_id == "generate_candidates":
            frame = self._recommendations.create_candidates(completed, top_anime)
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
        ranked = self._recommendations.recommend(candidates, importance, settings)
        self._require_nonempty(ranked, "No recommendations were generated.")
        result = self._write_step(
            ranked,
            directory / f"{profile.profile_id}_recommendations.csv",
            started_at,
            token,
        )
        return PipelineResult(
            recommendations=self._recommendation_models(ranked),
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

    def _write_step(
        self,
        frame: pd.DataFrame,
        path: Path,
        started_at: str,
        token: CancellationToken,
    ) -> PipelineResult:
        token.raise_if_cancelled()
        output = self._storage.write(frame, path)
        return self._step_result(started_at, generated_files=(str(output),))

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
    def _recommendation_models(frame: pd.DataFrame) -> tuple[Recommendation, ...]:
        models = []
        for rank, (_, row) in enumerate(frame.iterrows(), start=1):
            anime = anime_from_row(row)
            models.append(
                Recommendation(
                    anime=anime,
                    match_score=row.get("Match Score", 0.0),
                    raw_score=row.get("Recommendation Score", 0.0),
                    contributing_genres=tuple(row.get("Contributing Genres") or ()),
                    genre_contributions=tuple(row.get("Genre Contributions") or ()),
                    reason=row.get("Recommendation Reason"),
                    rank=rank,
                )
            )
        return tuple(models)

    @staticmethod
    def _genre_models(frame: pd.DataFrame) -> tuple[GenreStat, ...]:
        return tuple(
            GenreStat(
                genre=row["Genre"],
                importance_score=row["Importance_Score"],
            )
            for _, row in frame.iterrows()
        )

    def _timestamp(self) -> str:
        return self._clock().astimezone(timezone.utc).isoformat()
