import math

try:
    from .genre_utils import parse_genres
except ImportError:  # Backward compatibility for direct script-style imports.
    from genre_utils import parse_genres


def calculate_genre_importance(df, genre_medians):
    """Calculate how strongly each genre appears in the user's completed list."""
    genre_scores = {}
    scored_anime_count = 0

    for _, row in df.iterrows():
        score = _to_score(row["User Score"])
        if score <= 0:
            continue

        scored_anime_count += 1

        for genre in parse_genres(row["Genres"]):
            genre_scores.setdefault(genre, {"frequency": 0, "total_score": 0})
            genre_scores[genre]["frequency"] += 1
            genre_scores[genre]["total_score"] += score

    if scored_anime_count == 0:
        return {}

    genre_importance = {}
    for genre, data in genre_scores.items():
        frequency = data["frequency"]
        total_score = data["total_score"]
        avg_score = total_score / frequency
        median_score = genre_medians.get(genre, 0)

        if median_score > 0:
            genre_importance_score = (
                (frequency / scored_anime_count) * 100 * (avg_score / median_score)
            )
            genre_importance[genre] = round(genre_importance_score, 2)

    return genre_importance


def _to_score(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(score) else score
