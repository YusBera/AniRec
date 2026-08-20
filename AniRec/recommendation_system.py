import random
from pathlib import Path

import pandas as pd

try:
    from .genre_utils import parse_genres
    from .scoring.features import GENRE, feature_label, token
    from .scoring.ranking import score_candidates
    from .scoring.serialization import profile_from_frame
    from .title_utils import normalize_title_key
except ImportError:  # Backward compatibility for direct script-style imports.
    from genre_utils import parse_genres
    from scoring.features import GENRE, feature_label, token
    from scoring.ranking import score_candidates
    from scoring.serialization import profile_from_frame
    from title_utils import normalize_title_key


# How many drivers to name in an explanation before summarising the rest.
CONTRIBUTION_LIMIT = 3

OTHER_FEATURES_LABEL = "Other tags"
QUALITY_LABEL = "Community rating"
COLLABORATIVE_LABEL = "Similar viewers"
BASELINE_LABEL = "Baseline"

# Largest gap attributable to rounding rather than to the score itself.
ROUNDING_TOLERANCE = 0.05

# Feedback adjustments arrive on the display scale used by the interface.
# Dividing by this maps a single strong vote onto the affinity range.
FEEDBACK_SCALE = 24.0


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

    profile = profile_from_frame(genre_importance_df)
    adjustment_by_key = {
        str(genre).strip().casefold(): float(value)
        for genre, value in (genre_adjustments or {}).items()
        if str(genre).strip()
    }
    profile = _apply_adjustments(profile, adjustment_by_key)

    recommendations_df = candidates_df.copy()
    rows = [row for _index, row in recommendations_df.iterrows()]
    scored = score_candidates(rows, profile)

    recommendations_df["Recommendation Score"] = [
        round(item.final_score, 6) for item in scored
    ]
    recommendations_df["Match Score"] = [round(item.match_score, 2) for item in scored]
    recommendations_df["Genre Contributions"] = [
        _display_contributions(item) for item in scored
    ]
    recommendations_df["Contributing Genres"] = [
        _genre_drivers(item) for item in scored
    ]
    recommendations_df["Recommendation Reason"] = [
        _recommendation_reason(
            _genre_drivers(item),
            _matched_feedback_genres(row.get("Genres"), adjustment_by_key),
        )
        for row, item in zip(rows, scored)
    ]

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


def _apply_adjustments(profile, adjustment_by_key):
    """Fold explicit feedback into the profile before anything is scored.

    Adjustments arrive keyed by plain genre name. They are matched against the
    profile's own features, and a genre the user has never rated creates a new
    feature rather than being silently dropped, which is exactly the discovery
    case feedback exists to serve.
    """
    if not adjustment_by_key:
        return profile

    matched: dict[str, float] = {}
    for feature in profile.affinities:
        value = adjustment_by_key.get(feature_label(feature).strip().casefold())
        if value:
            matched[feature] = value
    seen = {feature_label(feature).strip().casefold() for feature in profile.affinities}
    for key, value in adjustment_by_key.items():
        if key not in seen and value:
            matched[token(GENRE, key)] = value
    if not matched:
        return profile

    # The size of an adjustment reflects how many times the user voted on that
    # genre, so it sets how far the affinity moves rather than where it lands.
    # One vote nudges; a saturated preference commits.
    updates = [
        (
            frozenset({feature}),
            1.0 if value > 0 else -1.0,
            min(1.0, abs(value) / FEEDBACK_SCALE),
        )
        for feature, value in matched.items()
    ]
    return profile.with_feedback(updates)


def _display_contributions(scored, limit=CONTRIBUTION_LIMIT):
    """The full breakdown of a score, labelled for a person to read.

    Every part of the score appears, including negative ones and the community
    rating, and anything past the named few is summarised rather than dropped.
    The values therefore add up to the match percentage shown beside them,
    which is the whole point of showing them.
    """
    ranked = sorted(scored.contributions, key=lambda item: (-abs(item[1]), item[0]))
    parts = [(feature_label(feature), value) for feature, value in ranked[:limit]]
    remainder = sum(value for _feature, value in ranked[limit:])
    if round(remainder, 2):
        parts.append((OTHER_FEATURES_LABEL, remainder))
    if round(scored.quality_contribution, 2):
        parts.append((QUALITY_LABEL, scored.quality_contribution))
    if round(scored.collaborative_contribution, 2):
        parts.append((COLLABORATIVE_LABEL, scored.collaborative_contribution))
    if not parts:
        return []

    rounded = [(label, round(value, 2)) for label, value in parts]
    residual = round(round(scored.match_score, 2) - sum(v for _l, v in rounded), 2)
    if not residual:
        return rounded

    # A cent of rounding drift belongs in the largest part. Anything larger is
    # real: it is the share of a weakly matched title's score that none of its
    # own attributes earned, and it is named rather than hidden.
    if abs(residual) <= ROUNDING_TOLERANCE:
        position = max(range(len(rounded)), key=lambda i: abs(rounded[i][1]))
        label, value = rounded[position]
        rounded[position] = (label, round(value + residual, 2))
    else:
        rounded.append((BASELINE_LABEL, residual))
    return rounded


def _genre_drivers(scored, limit=CONTRIBUTION_LIMIT):
    """Only the genre-like reasons, for prose that names them."""
    ranked = sorted(
        (item for item in scored.contributions if item[1] > 0),
        key=lambda item: (-item[1], item[0]),
    )
    return [feature_label(feature) for feature, _value in ranked[:limit]]


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
