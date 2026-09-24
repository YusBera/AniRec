"""Qt-independent full and single-step AniRec pipeline orchestration."""

from __future__ import annotations

import hashlib
import json
import math
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
        UserProfile,
    )
    from ..scoring.collaborative import (
        collaborative_scores,
        franchise_exclusions,
        select_seeds,
    )
    from ..scoring.selection import SELECTION_POLICY_VERSION, clamp_adventurousness
    from ..infrastructure.paths import RANKING_SNAPSHOT_ARCHIVE
    from ..scoring.explanation import (
        EXPLANATION_COLUMN,
        MODEL_RANK_COLUMN,
        RANKED_COUNT_COLUMN,
    )
    from ..scoring.taste import build_taste_profile
    from ..services import (
        AnimeDataService,
        AnimeGraphService,
        ProfileService,
        RecommendationService,
        RecommendationStateService,
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
        UserProfile,
    )
    from scoring.collaborative import (
        collaborative_scores,
        franchise_exclusions,
        select_seeds,
    )
    from scoring.selection import SELECTION_POLICY_VERSION, clamp_adventurousness
    from infrastructure.paths import RANKING_SNAPSHOT_ARCHIVE
    from scoring.explanation import (
        EXPLANATION_COLUMN,
        MODEL_RANK_COLUMN,
        RANKED_COUNT_COLUMN,
    )
    from scoring.taste import build_taste_profile
    from services import (
        AnimeDataService,
        AnimeGraphService,
        ProfileService,
        RecommendationService,
        RecommendationStateService,
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
# The ranking snapshot a generated feed was ranked from: the collaborative
# scores, franchise and hidden exclusions, eligibility date, a digest of the
# ranking inputs and the engine that answered. "More" continues exactly that
# ranking, so fit ranks stay unique and comparable, and refuses when the inputs
# have changed since instead of silently mixing two rankings in one feed.
RANKING_SIGNALS_FILENAME = "ranking_signals.csv"
# Every snapshot is also archived under its ranking id so activity recorded
# against an older feed can still be resolved to what that feed was ranked
# from. An archive expires 90 days after it was last written or referenced by
# a recorded event (the event service refreshes it), so it always outlives the
# events that point at it.
SNAPSHOT_ARCHIVE_RETENTION_SECONDS = 90 * 86400
SIGNAL_COLLABORATIVE = "collaborative"
SIGNAL_FRANCHISE_EXCLUDED = "franchise-excluded"
SIGNAL_HIDDEN_EXCLUDED = "hidden-excluded"
SIGNAL_AS_OF = "as-of"
SIGNAL_INPUT_DIGEST = "input-digest"
SIGNAL_RANKING_ENGINE = "ranking-engine"
SIGNAL_RANKING_ID = "ranking-id"
SIGNAL_FILTERS = "eligibility-filters"
# Files whose content decides a ranking; a sync or a regenerated step changes it.
# What decides whether a ranking is still current: only what the reader did
# (D-018). The catalogue and community columns in these files (mean score,
# scorer counts, pictures) drift every day; hashing whole files made nearly
# every sync look like a change and swapped the feed under the reader.
USER_INPUT_COLUMNS = (
    ("completed_anime.csv", ("Anime ID", "Status", "User Score")),
    (
        "user_history.csv",
        ("Anime ID", "Status", "User Score", "Episodes Watched", "Is Rewatching", "Updated At"),
    ),
)
# Files a ranking is computed from that only a generation writes: hashed byte
# for byte, so a changed (or tampered) candidate pool or taste profile still
# makes "more" refuse, while a sync, which never writes them, cannot churn them.
GENERATED_INPUT_FILES = ("genre_importance.csv", "recommendation_candidates.csv")
STALE_FEED_MESSAGE = (
    "Your MyAnimeList data, feedback, filters or saved candidates changed "
    "since this feed was generated. Generate a new feed to see more "
    "recommendations."
)
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
        recommendation_state=None,
    ) -> None:
        self._anime_data = anime_data
        self._profiles = profiles
        self._recommendations = recommendations
        self._storage = storage
        # Optional throughout. Without it, scoring runs on content and
        # community rating alone.
        self._anime_graph = anime_graph
        # Hidden titles are read from the profile's own saved state whenever a
        # caller does not pass them, so no caller (CLI, desktop or API) can
        # forget them and serve a title the reader hid.
        self._recommendation_state = recommendation_state or RecommendationStateService(
            root_override=getattr(profiles, "root_override", None)
        )
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
        profile_override: UserProfile | None = None,
        access_token_provider: Callable[[], str] | None = None,
    ) -> PipelineResult:
        """Persist the candidate catalogue and current MAL user datasets."""
        token = cancellation_token or CancellationToken()
        profile = profile_override or self._profiles.resolve_profile(username)
        if profile.username.casefold() != username.strip().casefold():
            raise DataError("The selected profile does not match the requested MAL username.")
        directory = self._profiles.directory(profile.profile_id, create=True)
        started_at = self._timestamp()
        credentials = self._checked_credentials(token, access_token_provider)

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
        excluded_mal_ids: set[int] | frozenset[int] | None = None,
        profile_override: UserProfile | None = None,
        access_token_provider: Callable[[], str] | None = None,
    ) -> PipelineResult:
        token = cancellation_token or CancellationToken()
        profile = profile_override or self._profiles.resolve_profile(username)
        if profile.username.casefold() != username.strip().casefold():
            raise DataError("The selected profile does not match the requested MAL username.")
        directory = self._profiles.directory(profile.profile_id, create=True)
        started_at = self._timestamp()
        credentials = self._checked_credentials(token, access_token_provider)
        candidate_catalogue, completed, history = self._fetch_inputs(
            username, settings, token, credentials, progress_callback
        )
        return self._generate_feed(
            profile,
            directory,
            settings,
            token,
            credentials,
            progress_callback,
            candidate_catalogue=candidate_catalogue,
            completed=completed,
            history=history,
            genre_adjustments=genre_adjustments,
            excluded_mal_ids=excluded_mal_ids,
            started_at=started_at,
        )

    def _fetch_inputs(self, username, settings, token, credentials, progress_callback):
        """Steps 1 and 2 of a full run: the catalogue, the list and its history."""
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
        return candidate_catalogue, completed, history

    def _generate_feed(
        self,
        profile,
        directory: Path,
        settings: PipelineSettings,
        token: CancellationToken,
        credentials,
        progress_callback,
        *,
        candidate_catalogue: pd.DataFrame,
        completed: pd.DataFrame,
        history,
        genre_adjustments,
        excluded_mal_ids,
        started_at,
        extra_user_stats: dict | None = None,
    ) -> PipelineResult:
        """Steps 3 to 6 of a full run, from already fetched inputs.

        A full run and a refresh rebuild both come here, so a rebuilt feed is
        ranked exactly as a full run ranks it: taste learned from real
        ratings, fresh similar-viewer and franchise signals, one snapshot.
        """
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
        hidden_ids = self._hidden_titles(profile.profile_id, excluded_mal_ids)
        ranked = self._recommendations.recommend(
            candidates,
            genre_importance,
            settings,
            genre_adjustments=genre_adjustments,
            excluded_mal_ids=hidden_ids | franchise_ids,
            collaborative_scores=collaborative,
            user_history=history,
            fallback_candidates=fallback_candidates,
            consumed_mal_ids=self._mal_ids(completed),
            include_nsfw=settings.include_nsfw,
            as_of=self._clock().date(),
            rated_history=completed,
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
        snapshot = self._snapshot(
            directory,
            collaborative=collaborative,
            franchise_ids=franchise_ids,
            hidden_ids=hidden_ids,
            as_of=self._clock().date(),
            genre_adjustments=genre_adjustments,
            ranking_metadata=ranking_metadata,
            eligibility_audit=eligibility_audit,
            settings=settings,
        )
        generated_paths = (
            *generated_paths,
            self._write_ranking_snapshot(directory, snapshot),
        )
        self._profiles.mark_synced(profile)

        return PipelineResult(
            recommendations=self._recommendation_models(
                ranked, snapshot["ranking_id"], settings
            ),
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
                # A new feed: no batch has been added to it yet.
                "added_recommendation_count": 0,
                **self._ranking_user_stats(
                    ranking_metadata,
                    eligibility_audit,
                ),
                **(extra_user_stats or {}),
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
        excluded_mal_ids: set[int] | frozenset[int] | None = None,
        count: int = 5,
        progress_callback: Callable[[PipelineProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
        profile_override: UserProfile | None = None,
    ) -> PipelineResult:
        """Generate additional feedback-aware picks from the persisted candidate pool."""

        token = cancellation_token or CancellationToken()
        profile = profile_override or self._profiles.resolve_profile(username)
        if profile.username.casefold() != username.strip().casefold():
            raise DataError("The selected profile does not match the requested MAL username.")
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
        snapshot = self._read_ranking_snapshot(directory)
        if not self._snapshot_is_current(
            directory, settings, existing_recommendations, genre_adjustments, snapshot
        ):
            raise DataError(STALE_FEED_MESSAGE)
        collaborative = snapshot["collaborative"]
        franchise_ids = snapshot["franchise"]
        shown_ids = {
            item.anime.mal_id
            for item in existing_recommendations
            if item.anime.mal_id is not None
        }
        shown_titles = {
            normalize_title_key(item.anime.title) for item in existing_recommendations
        }
        shown_titles.discard("")
        # Rank exactly the population the feed was ranked from, so every fit
        # rank in the combined list comes from one ordering. Titles already on
        # screen, and titles hidden since, stay ranked and are only skipped at
        # selection. Titles hidden at generation stay excluded even if
        # restored since; the next full run considers them again.
        hidden_now = self._hidden_titles(profile.profile_id, excluded_mal_ids)
        skipped_ids = shown_ids | (hidden_now - snapshot["hidden"])
        # The pool grows by the titles already shown, which stay ranked but
        # cannot be selected again.
        more_pool = max(settings.candidate_pool_size, int(count)) + len(
            existing_recommendations
        )
        more_settings = replace(
            settings,
            recommendation_count=max(1, int(count)),
            candidate_pool_size=more_pool,
            top_anime_limit=max(settings.top_anime_limit, more_pool),
            seed=None,
        )
        ranked = self._recommendations.recommend(
            candidates,
            importance,
            more_settings,
            genre_adjustments=genre_adjustments,
            excluded_mal_ids=snapshot["hidden"] | franchise_ids,
            collaborative_scores=collaborative,
            already_shown_mal_ids=skipped_ids,
            already_shown_titles=shown_titles,
            user_history=history,
            fallback_candidates=fallback_candidates,
            consumed_mal_ids=self._mal_ids(completed),
            include_nsfw=settings.include_nsfw,
            as_of=snapshot["as_of"],
            rated_history=self._read_rated_history(directory),
        )
        self._require_nonempty(ranked, "No unseen recommendations remain in the candidate pool.")
        ranking_metadata = ranked.attrs.get("ranking_engine")
        if (
            self._engine_label(ranking_metadata, ranked.attrs.get("eligibility_audit"))
            != snapshot["engine"]
        ):
            raise DataError(
                "The ranking engine changed since this feed was generated. "
                "Generate a new feed to see more recommendations."
            )
        eligibility_audit = ranked.attrs.get("eligibility_audit")
        token.raise_if_cancelled()
        new_recommendations = self._recommendation_models(
            ranked, snapshot["ranking_id"], more_settings
        )
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

    def run_refresh(
        self,
        username: str,
        settings: PipelineSettings,
        *,
        existing: PipelineResult | None,
        count: int,
        progress_callback: Callable[[PipelineProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
        profile_override: UserProfile | None = None,
        access_token_provider: Callable[[], str] | None = None,
    ) -> PipelineResult:
        """Bring the saved feed up to date (D-018).

        Fetches exactly what a full run fetches, once. The feed is rebuilt when
        there is none, when the reader's own list data, feedback or filters
        changed, or when a different engine would rank now. The rebuild is the
        full run's own generation, so it ranks exactly as a full run does.
        Otherwise the fresh list data is saved as a sync saves it, and the
        result carries no recommendations and no timestamps, so the saved feed
        and its ranking stay exactly as they were.
        """
        token = cancellation_token or CancellationToken()
        profile = profile_override or self._profiles.resolve_profile(username)
        if profile.username.casefold() != username.strip().casefold():
            raise DataError("The selected profile does not match the requested MAL username.")
        directory = self._profiles.directory(profile.profile_id, create=True)
        started_at = self._timestamp()
        credentials = self._checked_credentials(token, access_token_provider)
        candidate_catalogue, completed, history = self._fetch_inputs(
            username, settings, token, credentials, progress_callback
        )
        reason = self._refresh_reason(
            directory,
            settings,
            existing,
            {"completed_anime.csv": completed, "user_history.csv": history},
        )
        if reason is None:
            sources = [
                (candidate_catalogue, directory / CANDIDATE_CATALOGUE_FILENAME),
                (completed, directory / "completed_anime.csv"),
            ]
            if history is not None and not history.empty:
                sources.append((history, directory / "user_history.csv"))
            self._storage.write_batch(tuple(sources), cancellation_check=token.raise_if_cancelled)
            self._profiles.mark_synced(profile)
            return PipelineResult(user_stats={"feed_refresh": "current"})
        return self._generate_feed(
            profile,
            directory,
            replace(settings, recommendation_count=max(1, int(count))),
            token,
            credentials,
            progress_callback,
            candidate_catalogue=candidate_catalogue,
            completed=completed,
            history=history,
            genre_adjustments=None,
            excluded_mal_ids=None,
            started_at=started_at,
            extra_user_stats={"feed_refresh": reason},
        )

    def run_step(
        self,
        step_id: str,
        username: str,
        settings: PipelineSettings,
        *,
        progress_callback: Callable[[PipelineProgress], None] | None = None,
        cancellation_token: CancellationToken | None = None,
        excluded_mal_ids: set[int] | frozenset[int] | None = None,
        genre_adjustments: dict[str, float] | None = None,
        profile_override: UserProfile | None = None,
    ) -> PipelineResult:
        """Run one step. ``excluded_mal_ids`` (hidden titles) and
        ``genre_adjustments`` apply to "generate_recommendations" exactly as
        they do in a full run; before, single-step generation ignored both."""
        if step_id not in SINGLE_STEP_IDS:
            raise ValueError(f"Unknown pipeline step: {step_id}")

        token = cancellation_token or CancellationToken()
        profile = profile_override or self._profiles.resolve_profile(username)
        if profile.username.casefold() != username.strip().casefold():
            raise DataError("The selected profile does not match the requested MAL username.")
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
        previous = self._read_ranking_snapshot(directory)
        collaborative = previous["collaborative"] if previous else {}
        franchise_ids = previous["franchise"] if previous else set()
        as_of = self._clock().date()
        hidden_ids = self._hidden_titles(profile.profile_id, excluded_mal_ids)
        ranked = self._recommendations.recommend(
            candidates,
            importance,
            settings,
            genre_adjustments=genre_adjustments,
            excluded_mal_ids=hidden_ids | franchise_ids,
            collaborative_scores=collaborative,
            user_history=self._read_user_history(directory),
            fallback_candidates=candidates,
            consumed_mal_ids=self._mal_ids(completed),
            include_nsfw=settings.include_nsfw,
            as_of=as_of,
            rated_history=self._read_rated_history(directory),
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
        snapshot = self._snapshot(
            directory,
            collaborative=collaborative,
            franchise_ids=franchise_ids,
            hidden_ids=hidden_ids,
            as_of=as_of,
            genre_adjustments=genre_adjustments,
            ranking_metadata=ranking_metadata,
            eligibility_audit=eligibility_audit,
            settings=settings,
        )
        snapshot_path = self._write_ranking_snapshot(directory, snapshot)
        result = replace(
            result, generated_files=(*result.generated_files, str(snapshot_path))
        )
        return PipelineResult(
            recommendations=self._recommendation_models(
                ranked, snapshot["ranking_id"], settings
            ),
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

    def _checked_token(
        self,
        cancellation_token: CancellationToken,
        access_token_provider: Callable[[], str] | None = None,
    ) -> str:
        """Return an OAuth token for compatibility with authenticated CLI flows."""
        cancellation_token.raise_if_cancelled()
        provider = access_token_provider or self._access_token_provider
        if provider is None:
            raise DataError("No access token provider is configured.")
        access_token = provider()
        cancellation_token.raise_if_cancelled()
        if not access_token:
            raise DataError("The access token provider returned an empty token.")
        return access_token

    def _checked_credentials(
        self,
        cancellation_token: CancellationToken,
        access_token_provider: Callable[[], str] | None = None,
    ) -> dict[str, str]:
        """Prefer the public Client ID flow; fall back to OAuth when configured."""
        cancellation_token.raise_if_cancelled()
        if self._client_id_provider is not None:
            client_id = self._client_id_provider()
            cancellation_token.raise_if_cancelled()
            if client_id:
                return {"client_id": client_id}
        return {"access_token": self._checked_token(cancellation_token, access_token_provider)}

    def _read_completed(self, directory: Path) -> pd.DataFrame:
        imputed = directory / "completed_anime_imputed.csv"
        path = imputed if imputed.exists() else directory / "completed_anime.csv"
        return self._storage.read(path, required_columns=["Title", "Genres", "User Score"])

    def _snapshot(
        self,
        directory: Path,
        *,
        collaborative,
        franchise_ids,
        hidden_ids,
        as_of,
        genre_adjustments,
        ranking_metadata,
        eligibility_audit,
        settings: PipelineSettings,
    ) -> dict:
        """What a feed was ranked from, and the identity derived from all of it."""
        snapshot = {
            "collaborative": {int(k): float(v) for k, v in (collaborative or {}).items()},
            "franchise": {int(value) for value in (franchise_ids or ())},
            "hidden": {int(value) for value in (hidden_ids or ()) if value},
            "as_of": as_of,
            "digest": self._ranking_inputs_digest(directory, genre_adjustments),
            "engine": self._engine_label(ranking_metadata, eligibility_audit),
            "filters": self._filters_label(settings),
        }
        identity = json.dumps(
            [
                snapshot["filters"],
                sorted(snapshot["collaborative"].items()),
                sorted(snapshot["franchise"]),
                sorted(snapshot["hidden"]),
                as_of.isoformat(),
                snapshot["digest"],
                snapshot["engine"],
            ]
        )
        snapshot["ranking_id"] = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
        return snapshot

    def _write_ranking_snapshot(self, directory: Path, snapshot: dict) -> str:
        """Record what the feed just ranked was ranked from (see the constants)."""
        rows = [
            {"Signal": SIGNAL_COLLABORATIVE, "Anime ID": mal_id, "Value": value, "Text": None}
            for mal_id, value in sorted(snapshot["collaborative"].items())
        ]
        rows += [
            {"Signal": SIGNAL_FRANCHISE_EXCLUDED, "Anime ID": mal_id, "Value": None, "Text": None}
            for mal_id in sorted(snapshot["franchise"])
        ]
        rows += [
            {"Signal": SIGNAL_HIDDEN_EXCLUDED, "Anime ID": mal_id, "Value": None, "Text": None}
            for mal_id in sorted(snapshot["hidden"])
        ]
        rows += [
            {"Signal": signal, "Anime ID": None, "Value": None, "Text": text}
            for signal, text in (
                (SIGNAL_AS_OF, snapshot["as_of"].isoformat()),
                (SIGNAL_INPUT_DIGEST, snapshot["digest"]),
                (SIGNAL_RANKING_ENGINE, snapshot["engine"]),
                (SIGNAL_FILTERS, snapshot["filters"]),
                (SIGNAL_RANKING_ID, snapshot["ranking_id"]),
            )
        ]
        frame = pd.DataFrame(rows, columns=["Signal", "Anime ID", "Value", "Text"])
        path = self._storage.write(frame, directory / RANKING_SIGNALS_FILENAME)
        self._archive_ranking_snapshot(directory, snapshot["ranking_id"], frame)
        return str(path)

    def _archive_ranking_snapshot(self, directory: Path, ranking_id: str, frame) -> None:
        """Keep an immutable copy under the ranking id; prune expired copies."""
        archive = directory / RANKING_SNAPSHOT_ARCHIVE
        target = archive / f"{ranking_id}.csv"
        if not target.exists():
            self._storage.write(frame, target)
        cutoff = self._clock().timestamp() - SNAPSHOT_ARCHIVE_RETENTION_SECONDS
        for path in archive.glob("*.csv"):
            try:
                if path != target and path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass  # pruning is housekeeping; a failure must not fail a run

    def ranking_snapshot(self, username: str, ranking_id: str) -> dict | None:
        """Resolve an archived ranking snapshot, e.g. for an activity event."""
        profile = self._profiles.resolve_profile(username)
        path = (
            self._profiles.directory(profile.profile_id)
            / RANKING_SNAPSHOT_ARCHIVE
            / f"{ranking_id}.csv"
        )
        return self._read_ranking_snapshot(path.parent, path=path)

    def _read_ranking_snapshot(self, directory: Path, path: Path | None = None) -> dict | None:
        """The last generated feed's ranking snapshot, or None if it has none."""
        path = path or directory / RANKING_SIGNALS_FILENAME
        if not path.exists():
            return None
        frame = self._storage.read(path, required_columns=["Signal", "Anime ID", "Value"])
        snapshot = {
            "collaborative": {},
            "franchise": set(),
            "hidden": set(),
            "as_of": None,
            "digest": None,
            "engine": None,
            "filters": None,
            "ranking_id": None,
        }
        for _index, row in frame.iterrows():
            signal = row.get("Signal")
            text = row.get("Text") if "Text" in frame.columns else None
            text = None if text is None or pd.isna(text) else str(text)
            if signal == SIGNAL_AS_OF and text:
                snapshot["as_of"] = datetime.fromisoformat(text).date()
                continue
            if signal == SIGNAL_INPUT_DIGEST:
                snapshot["digest"] = text
                continue
            if signal == SIGNAL_RANKING_ENGINE:
                snapshot["engine"] = text
                continue
            if signal == SIGNAL_RANKING_ID:
                snapshot["ranking_id"] = text
                continue
            if signal == SIGNAL_FILTERS:
                snapshot["filters"] = text
                continue
            mal_id = pd.to_numeric(row.get("Anime ID"), errors="coerce")
            if pd.isna(mal_id) or int(mal_id) <= 0:
                continue
            if signal == SIGNAL_COLLABORATIVE:
                value = pd.to_numeric(row.get("Value"), errors="coerce")
                if pd.notna(value):
                    snapshot["collaborative"][int(mal_id)] = float(value)
            elif signal == SIGNAL_FRANCHISE_EXCLUDED:
                snapshot["franchise"].add(int(mal_id))
            elif signal == SIGNAL_HIDDEN_EXCLUDED:
                snapshot["hidden"].add(int(mal_id))
        if (
            snapshot["as_of"] is None
            or snapshot["digest"] is None
            or not snapshot["ranking_id"]
            or snapshot["filters"] is None
        ):
            # A file from before snapshots existed cannot vouch for a ranking.
            return None
        return snapshot

    @staticmethod
    def _canonical(value) -> str:
        """One spelling per value, so a CSV round trip does not look like an edit."""
        if value is None:
            return ""
        text = str(value).strip()
        if text.casefold() in {"true", "false"}:
            return text.casefold()
        try:
            number = float(text)
        except ValueError:
            return text
        if math.isnan(number):
            return ""
        return str(int(number)) if number.is_integer() else repr(number)

    def _user_inputs_digest(self, directory: Path, frames: dict, genre_adjustments) -> str:
        """Digest of the reader's own list data, the generated ranking inputs,
        and the reader's feedback."""
        digest = hashlib.sha256()
        for name in GENERATED_INPUT_FILES:
            path = directory / name
            digest.update(name.encode("utf-8") + b"\0")
            digest.update(path.read_bytes() if path.exists() else b"<absent>")
            digest.update(b"\0")
        for name, columns in USER_INPUT_COLUMNS:
            frame = frames.get(name)
            digest.update(name.encode("utf-8") + b"\0")
            if frame is None or frame.empty:
                digest.update(b"<absent>\0")
                continue
            rows = sorted(
                tuple(self._canonical(row.get(column)) for column in columns)
                for row in frame.to_dict("records")
            )
            digest.update(json.dumps(rows).encode("utf-8") + b"\0")
        adjustments = sorted(
            (str(genre).strip().casefold(), round(float(value), 9))
            for genre, value in (genre_adjustments or {}).items()
            if str(genre).strip() and value
        )
        digest.update(json.dumps(adjustments).encode("utf-8"))
        return digest.hexdigest()

    def _ranking_inputs_digest(self, directory: Path, genre_adjustments) -> str:
        """The same digest, read back from the profile's saved files."""
        frames = {
            name: pd.read_csv(directory / name) if (directory / name).exists() else None
            for name, _columns in USER_INPUT_COLUMNS
        }
        return self._user_inputs_digest(directory, frames, genre_adjustments)

    def _snapshot_is_current(
        self, directory: Path, settings: PipelineSettings, recommendations,
        genre_adjustments, snapshot,
    ) -> bool:
        """Whether ``recommendations`` are still exactly what their snapshot ranked.

        False when the inputs or the eligibility filters changed, or when the
        feed is not the one this snapshot ranked (an older feed, or a snapshot
        written for a feed that was never saved). "More" refuses to continue
        such a feed; a refresh rebuilds it. One definition serves both.
        """
        return (
            snapshot is not None
            and snapshot["digest"] == self._ranking_inputs_digest(directory, genre_adjustments)
            and snapshot["filters"] == self._filters_label(settings)
            and all(item.ranking_id == snapshot["ranking_id"] for item in recommendations)
        )

    def _refresh_reason(
        self,
        directory: Path,
        settings: PipelineSettings,
        existing: PipelineResult | None,
        fetched: dict,
    ) -> str | None:
        """Why the saved feed must be rebuilt, or None when it is current.

        ``fetched`` is the list data just read from MyAnimeList, judged before
        anything is written, with the same digest the snapshot recorded.
        """
        if existing is None or not existing.recommendations:
            return "missing"
        snapshot = self._read_ranking_snapshot(directory)
        if (
            snapshot is None
            # The web client feeds no taste adjustments (D-013), so none here.
            or snapshot["digest"] != self._user_inputs_digest(directory, fetched, None)
            or snapshot["filters"] != self._filters_label(settings)
            or any(item.ranking_id != snapshot["ranking_id"] for item in existing.recommendations)
        ):
            return "inputs-changed"
        ranked_by = tuple(str(snapshot["engine"]).split(":")[:2])
        if ranked_by != self._recommendations.engine_identity():
            return "engine-changed"
        return None

    @staticmethod
    def _engine_label(metadata, audit=None) -> str:
        """Engine, version, primary/fallback and the eligibility catalogue.

        The catalogue version fingerprints the bundle's catalogue, mask and
        prerequisites, which can change the ranked population without the
        model checkpoint changing.
        """
        if metadata is None:
            return "unknown"
        catalogue = getattr(audit, "catalog_version", None) or "unversioned"
        return (
            f"{metadata.engine_id}:{metadata.engine_version}:"
            f"{'fallback' if metadata.fallback_used else 'primary'}:{catalogue}"
        )

    @staticmethod
    def _filters_label(settings: PipelineSettings) -> str:
        """Settings that decide which titles may be ranked at all."""
        return json.dumps(
            {
                "include_nsfw": bool(settings.include_nsfw),
                "minimum_mean_score": settings.minimum_mean_score,
            },
            sort_keys=True,
        )

    def _hidden_titles(self, profile_id: str, excluded_mal_ids) -> set[int]:
        """Hidden titles: the caller's set, or the profile's saved state."""
        if excluded_mal_ids is None:
            excluded_mal_ids = self._recommendation_state.load(profile_id).hidden_mal_ids
        return {int(value) for value in excluded_mal_ids if value}

    def _read_rated_history(self, directory: Path) -> pd.DataFrame | None:
        """The synced list with the reader's own scores, never the imputed copy.

        Explanations quote these scores as "you rated this", so a filled-in
        guess must never reach them.
        """
        path = directory / "completed_anime.csv"
        if not path.exists():
            return None
        return self._storage.read(path, required_columns=["Title", "User Score"])

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
    def _recommendation_models(
        frame: pd.DataFrame,
        ranking_id: str | None = None,
        settings: PipelineSettings | None = None,
    ) -> tuple[Recommendation, ...]:
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
                    model_rank=row.get(MODEL_RANK_COLUMN),
                    ranked_candidate_count=row.get(RANKED_COUNT_COLUMN),
                    explanation=row.get(EXPLANATION_COLUMN),
                    ranking_id=ranking_id,
                    selection_policy=SELECTION_POLICY_VERSION if settings else None,
                    adventurousness=(
                        clamp_adventurousness(settings.randomness_factor)
                        if settings
                        else None
                    ),
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
