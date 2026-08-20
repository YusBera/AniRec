import random
from pathlib import Path

import pandas as pd

try:
    from .genre_utils import parse_genres
    from .title_utils import normalize_title_key
except ImportError:  # Backward compatibility for direct script-style imports.
    from genre_utils import parse_genres
    from title_utils import normalize_title_key


# A typical anime carries roughly this many meaningful genres. Calibrating
# against the strongest few weights rather than against the best score in the
# current batch keeps a title's match percentage the same no matter which other
# titles happen to be ranked alongside it.
CALIBRATION_GENRE_COUNT = 3


def recommend_animes_with_randomness(
    recommendation_candidates_file, genre_importance_file, username,
    num_recommendations, top_anime_count, randomness_factor, output_dir
):
    """Generate recommendations from candidate anime and user genre weights."""
    candidates_df = pd.read_csv(recommendation_candidates_file)
    genre_importance_df = pd.read_csv(genre_importance_file)

    final_recommendations = rank_recommendations(
        candidates_df,
        genre_importance_df,
        num_recommendations=num_recommendations,
        top_anime_count=top_anime_count,
        randomness_factor=randomness_factor,
    )

    if final_recommendations.empty:
        return []

    output_path = Path(output_dir) / f"{username}_recommendations.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_recommendations.to_csv(output_path, index=False)
    return final_recommendations["Title"].tolist()


def rank_recommendations(
    candidates_df,
    genre_importance_df,
    *,
    num_recommendations,
    top_anime_count,
    randomness_factor,
    random_state=None,
    genre_adjustments=None,
    excluded_mal_ids=None,
    excluded_titles=None,
    minimum_mean_score=None,
):
    """Rank in-memory candidate data without reading or writing CSV files."""
    required_candidate_columns = {"Title", "Genres"}
    missing_candidate_columns = required_candidate_columns - set(candidates_df.columns)
    if missing_candidate_columns:
        missing = ", ".join(sorted(missing_candidate_columns))
        raise ValueError(f"Recommendation candidates are missing columns: {missing}")

    if not {"Genre", "Importance_Score"}.issubset(genre_importance_df.columns):
        raise ValueError("Genre importance file must include Genre and Importance_Score columns.")

    if candidates_df.empty or genre_importance_df.empty:
        return candidates_df.head(0).copy()

    excluded_ids = {int(value) for value in (excluded_mal_ids or ()) if value is not None}
    excluded_title_keys = {
        key for value in (excluded_titles or ()) if (key := normalize_title_key(value))
    }
    candidates_df = candidates_df.copy()
    if excluded_ids and "Anime ID" in candidates_df.columns:
        numeric_ids = pd.to_numeric(candidates_df["Anime ID"], errors="coerce")
        candidates_df = candidates_df.loc[~numeric_ids.isin(excluded_ids)]
    if excluded_title_keys:
        candidate_keys = candidates_df["Title"].map(normalize_title_key)
        candidates_df = candidates_df.loc[~candidate_keys.isin(excluded_title_keys)]
    if minimum_mean_score is not None and "Mean Score" in candidates_df.columns:
        numeric_scores = pd.to_numeric(candidates_df["Mean Score"], errors="coerce")
        candidates_df = candidates_df.loc[numeric_scores >= float(minimum_mean_score)]
    if candidates_df.empty:
        return candidates_df.copy()

    genre_weights = dict(
        zip(
            genre_importance_df["Genre"],
            genre_importance_df["Importance_Score"].astype(float),
        )
    )
    adjustment_by_key = {
        str(genre).strip().casefold(): float(value)
        for genre, value in (genre_adjustments or {}).items()
        if str(genre).strip()
    }
    for genre in tuple(genre_weights):
        genre_weights[genre] = float(genre_weights[genre]) + adjustment_by_key.get(
            str(genre).casefold(), 0.0
        )
    recommendations_df = candidates_df.copy()
    recommendations_df["Recommendation Score"] = recommendations_df["Genres"].apply(
        lambda genres: _score_genres(genres, genre_weights)
    )
    calibration_reference = _calibration_reference(genre_weights)
    if calibration_reference <= 0:
        recommendations_df["Match Score"] = 0.0
    else:
        recommendations_df["Match Score"] = recommendations_df[
            "Recommendation Score"
        ].apply(lambda score: _match_percentage(score, calibration_reference))
    recommendations_df["Genre Contributions"] = recommendations_df["Genres"].apply(
        lambda genres: _genre_contributions(genres, genre_weights)
    )
    recommendations_df["Contributing Genres"] = recommendations_df[
        "Genre Contributions"
    ].apply(lambda values: [genre for genre, _score in values])
    recommendations_df["Recommendation Reason"] = recommendations_df[
        "Genres"
    ].apply(
        lambda genres: _recommendation_reason(
            [genre for genre, _score in _genre_contributions(genres, genre_weights)],
            _matched_feedback_genres(genres, adjustment_by_key),
        )
    )

    sort_columns = ["Recommendation Score"]
    ascending = [False]
    if "Mean Score" in recommendations_df.columns:
        sort_columns.append("Mean Score")
        ascending.append(False)
    if "Anime ID" in recommendations_df.columns:
        sort_columns.append("Anime ID")
        ascending.append(True)
    sort_columns.append("Title")
    ascending.append(True)

    ranked_df = recommendations_df.sort_values(
        sort_columns,
        ascending=ascending,
        kind="mergesort",
        na_position="last",
    )
    ranked_df = ranked_df.head(max(top_anime_count, num_recommendations))

    randomness_factor = min(max(randomness_factor, 1), 10)
    pool_size = max(num_recommendations, round(len(ranked_df) * randomness_factor / 10))
    recommendation_pool = ranked_df.head(pool_size)

    if len(recommendation_pool) > num_recommendations:
        final_recommendations = recommendation_pool.sample(
            n=num_recommendations,
            random_state=(
                random.randint(1, 1_000_000) if random_state is None else random_state
            ),
        ).sort_values(sort_columns, ascending=ascending)
    else:
        final_recommendations = recommendation_pool

    return final_recommendations.copy()


def _calibration_reference(genre_weights):
    """Return a batch-independent denominator for the match percentage."""
    positives = sorted(
        (float(value) for value in genre_weights.values() if float(value) > 0),
        reverse=True,
    )
    return sum(positives[:CALIBRATION_GENRE_COUNT])


def _match_percentage(score, reference):
    try:
        percentage = float(score) / reference * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0
    if pd.isna(percentage):
        return 0.0
    return round(min(100.0, max(0.0, percentage)), 2)


def _score_genres(genres, genre_weights):
    matched_scores = [genre_weights.get(genre, 0) for genre in parse_genres(genres)]
    return round(sum(matched_scores), 2)


def _genre_contributions(genres, genre_weights, limit=3):
    contributions = [
        (genre, float(genre_weights.get(genre, 0)))
        for genre in dict.fromkeys(parse_genres(genres))
        if float(genre_weights.get(genre, 0)) > 0
    ]
    contributions.sort(key=lambda item: (-item[1], item[0].casefold()))
    return [(genre, round(score, 2)) for genre, score in contributions[:limit]]


def _matched_feedback_genres(genres, adjustments):
    matched = []
    for genre in parse_genres(genres):
        value = adjustments.get(genre.casefold(), 0.0)
        if value:
            matched.append((genre, value))
    return matched


def _recommendation_reason(genres, feedback_genres=()):
    positive = [genre for genre, score in feedback_genres if score > 0]
    negative = [genre for genre, score in feedback_genres if score < 0]
    if positive:
        return f"Adapted to your likes in {', '.join(positive[:2])}."
    if negative and not genres:
        return f"Explores outside genres you disliked, including {', '.join(negative[:2])}."
    if not genres:
        return "Broadens your recommendations beyond your strongest genres."
    if len(genres) == 1:
        return f"Matches your interest in {genres[0]}."
    if len(genres) == 2:
        return f"Matches your interests in {genres[0]} and {genres[1]}."
    return f"Matches your interests in {', '.join(genres[:-1])}, and {genres[-1]}."
