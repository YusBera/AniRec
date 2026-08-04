import pandas as pd
from statistics import mean, median

try:
    from .genre_utils import parse_genres
except ImportError:  # Backward compatibility for direct script-style imports.
    from genre_utils import parse_genres


def calculate_genre_medians(df):
    """Calculate the median user score for each genre."""
    genre_scores = {}

    for _, row in df.iterrows():
        score = _to_score(row["User Score"])
        if score <= 0:
            continue

        for genre in parse_genres(row["Genres"]):
            genre_scores.setdefault(genre, [])
            genre_scores[genre].append(score)

    return {genre: median(scores) for genre, scores in genre_scores.items()}


def handle_missing_scores_with_genre_medians(df, genre_medians):
    """Fill missing or zero user scores using the user's genre medians."""
    updated_df = df.copy()
    updated_df["User Score"] = updated_df["User Score"].apply(_to_score)
    fallback_score = median(genre_medians.values()) if genre_medians else 0

    for index, row in updated_df.iterrows():
        if row["User Score"] > 0:
            continue

        genre_scores = [
            genre_medians[genre]
            for genre in parse_genres(row["Genres"])
            if genre in genre_medians
        ]
        imputed_score = mean(genre_scores) if genre_scores else fallback_score
        updated_df.at[index, "User Score"] = round(imputed_score, 2)

    return updated_df


def _to_score(value):
    if pd.isna(value):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
