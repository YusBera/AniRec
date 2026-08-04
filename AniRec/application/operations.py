"""Parameter-driven AniRec operations with no terminal input or output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import pandas as pd

try:
    from ..anime_data import get_top_anime
    from ..candidate_generation import generate_recommendation_candidates
    from ..genre_importance import calculate_genre_importance
    from ..handle_missing_scores import (
        calculate_genre_medians,
        handle_missing_scores_with_genre_medians,
    )
    from ..recommendation_system import recommend_animes_with_randomness
    from ..user_data import get_user_completed_animes
except ImportError:  # Backward compatibility for ``python AniRec/main.py``.
    from anime_data import get_top_anime
    from candidate_generation import generate_recommendation_candidates
    from genre_importance import calculate_genre_importance
    from handle_missing_scores import (
        calculate_genre_medians,
        handle_missing_scores_with_genre_medians,
    )
    from recommendation_system import recommend_animes_with_randomness
    from user_data import get_user_completed_animes


@dataclass(frozen=True)
class FileOperationResult:
    path: Path
    row_count: int


@dataclass(frozen=True)
class RecommendationFileResult(FileOperationResult):
    titles: tuple[str, ...]


def require_file(path: str | Path, hint: str) -> Path:
    required_path = Path(path)
    if not required_path.exists():
        raise FileNotFoundError(f"Missing '{required_path}'. {hint}")
    return required_path


def fetch_top_anime_to_file(
    profile_directory: str | Path,
    *,
    limit: int,
    access_token: str,
    fetcher: Callable[..., pd.DataFrame] = get_top_anime,
) -> FileOperationResult:
    profile_path = Path(profile_directory)
    profile_path.mkdir(parents=True, exist_ok=True)
    frame = fetcher(limit=limit, access_token=access_token)
    if frame.empty:
        raise RuntimeError("MyAnimeList returned no top anime data.")
    output = profile_path / "top_anime.csv"
    frame.to_csv(output, index=False)
    return FileOperationResult(output, len(frame))


def fetch_completed_anime_to_file(
    username: str,
    profile_directory: str | Path,
    *,
    access_token: str,
    fetcher: Callable[..., pd.DataFrame] = get_user_completed_animes,
) -> FileOperationResult:
    profile_path = Path(profile_directory)
    profile_path.mkdir(parents=True, exist_ok=True)
    frame = fetcher(username, access_token)
    if frame.empty:
        raise RuntimeError(
            "No completed anime were returned. Check the username and MyAnimeList list privacy settings."
        )
    output = profile_path / "completed_anime.csv"
    frame.to_csv(output, index=False)
    return FileOperationResult(output, len(frame))


def impute_missing_scores_file(profile_directory: str | Path) -> FileOperationResult:
    profile_path = Path(profile_directory)
    source = require_file(
        profile_path / "completed_anime.csv",
        "Run 'Fetch completed anime' first.",
    )
    completed = pd.read_csv(source)
    medians = calculate_genre_medians(completed)
    imputed = handle_missing_scores_with_genre_medians(completed, medians)
    output = profile_path / "completed_anime_imputed.csv"
    imputed.to_csv(output, index=False)
    return FileOperationResult(output, len(imputed))


def calculate_genre_importance_file(profile_directory: str | Path) -> FileOperationResult:
    profile_path = Path(profile_directory)
    source = profile_path / "completed_anime_imputed.csv"
    if not source.exists():
        source = require_file(
            profile_path / "completed_anime.csv",
            "Run 'Fetch completed anime' first.",
        )

    completed = pd.read_csv(source)
    medians = calculate_genre_medians(completed)
    importance = calculate_genre_importance(completed, medians)
    if not importance:
        raise RuntimeError("No genre importance scores were generated. Check that user scores exist.")

    frame = pd.DataFrame(
        sorted(importance.items(), key=lambda item: item[1], reverse=True),
        columns=["Genre", "Importance_Score"],
    )
    output = profile_path / "genre_importance.csv"
    frame.to_csv(output, index=False)
    return FileOperationResult(output, len(frame))


def create_recommendation_candidates_file(
    profile_directory: str | Path,
) -> FileOperationResult:
    profile_path = Path(profile_directory)
    completed = profile_path / "completed_anime_imputed.csv"
    if not completed.exists():
        completed = require_file(
            profile_path / "completed_anime.csv",
            "Run 'Fetch completed anime' first.",
        )
    top_anime = require_file(
        profile_path / "top_anime.csv",
        "Run 'Fetch top anime list' first.",
    )
    output = profile_path / "recommendation_candidates.csv"
    frame = generate_recommendation_candidates(completed, top_anime, output)
    return FileOperationResult(output, len(frame))


def generate_recommendations_file(
    username: str,
    profile_directory: str | Path,
    *,
    num_recommendations: int,
    top_anime_count: int,
    randomness_factor: int,
    recommender: Callable[..., list[str]] = recommend_animes_with_randomness,
) -> RecommendationFileResult:
    profile_path = Path(profile_directory)
    candidates = require_file(
        profile_path / "recommendation_candidates.csv",
        "Run 'Generate recommendation candidates' first.",
    )
    importance = require_file(
        profile_path / "genre_importance.csv",
        "Run 'Calculate genre importance' first.",
    )
    titles = recommender(
        candidates,
        importance,
        username,
        num_recommendations,
        top_anime_count,
        randomness_factor,
        profile_path,
    )
    if not titles:
        raise RuntimeError("No recommendations were generated. Try fetching more top anime.")
    output = profile_path / f"{username}_recommendations.csv"
    return RecommendationFileResult(output, len(titles), tuple(titles))
