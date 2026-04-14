import random
from pathlib import Path

import pandas as pd

from genre_utils import parse_genres


def recommend_animes_with_randomness(
    recommendation_candidates_file, genre_importance_file, username,
    num_recommendations, top_anime_count, randomness_factor, output_dir
):
    """Generate recommendations from candidate anime and user genre weights."""
    candidates_df = pd.read_csv(recommendation_candidates_file)
    genre_importance_df = pd.read_csv(genre_importance_file)

    required_candidate_columns = {"Title", "Genres"}
    missing_candidate_columns = required_candidate_columns - set(candidates_df.columns)
    if missing_candidate_columns:
        missing = ", ".join(sorted(missing_candidate_columns))
        raise ValueError(f"Recommendation candidates are missing columns: {missing}")

    if not {"Genre", "Importance_Score"}.issubset(genre_importance_df.columns):
        raise ValueError("Genre importance file must include Genre and Importance_Score columns.")

    if candidates_df.empty or genre_importance_df.empty:
        return []

    genre_weights = dict(
        zip(
            genre_importance_df["Genre"],
            genre_importance_df["Importance_Score"].astype(float),
        )
    )
    recommendations_df = candidates_df.copy()
    recommendations_df["Recommendation Score"] = recommendations_df["Genres"].apply(
        lambda genres: _score_genres(genres, genre_weights)
    )

    sort_columns = ["Recommendation Score"]
    ascending = [False]
    if "Mean Score" in recommendations_df.columns:
        sort_columns.append("Mean Score")
        ascending.append(False)

    ranked_df = recommendations_df.sort_values(sort_columns, ascending=ascending)
    ranked_df = ranked_df.head(max(top_anime_count, num_recommendations))

    randomness_factor = min(max(randomness_factor, 1), 10)
    pool_size = max(num_recommendations, round(len(ranked_df) * randomness_factor / 10))
    recommendation_pool = ranked_df.head(pool_size)

    if len(recommendation_pool) > num_recommendations:
        final_recommendations = recommendation_pool.sample(
            n=num_recommendations,
            random_state=random.randint(1, 1_000_000),
        ).sort_values(sort_columns, ascending=ascending)
    else:
        final_recommendations = recommendation_pool

    output_path = Path(output_dir) / f"{username}_recommendations.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final_recommendations.to_csv(output_path, index=False)
    return final_recommendations["Title"].tolist()


def _score_genres(genres, genre_weights):
    matched_scores = [genre_weights.get(genre, 0) for genre in parse_genres(genres)]
    return round(sum(matched_scores), 2)
