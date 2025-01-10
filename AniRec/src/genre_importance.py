# genre_importance.py

import numpy as np
from handle_missing_scores import calculate_genre_medians


def calculate_genre_importance(df, genre_medians):
    """
    Calculate Genre Importance Score for each genre based on the user's completed anime data.

    Parameters:
    - df: DataFrame containing completed anime data with genres and scores
    - genre_medians: Dictionary of genre medians

    Returns:
    - genre_importance: Dictionary of genre importance scores for each genre
    """
    genre_scores = {}
    total_animes = len(df)

    # Calculate frequency and average score for each genre
    for idx, row in df.iterrows():
        score = row['User Score']
        genres = eval(row['Genres'])  # Convert genre string to list

        for genre in genres:
            if genre not in genre_scores:
                genre_scores[genre] = {'frequency': 0, 'total_score': 0}

            genre_scores[genre]['frequency'] += 1
            genre_scores[genre]['total_score'] += score

    genre_importance = {}

    # Calculate Genre Importance Score (GI) for each genre
    for genre, data in genre_scores.items():
        frequency = data['frequency']
        total_score = data['total_score']
        avg_score = total_score / frequency
        median_score = genre_medians.get(genre, 0)  # Genre median (default to 0 if not found)

        if median_score > 0:  # Only calculate GI if the median score is available
            gi = ((frequency / total_animes) * 100) * (avg_score / median_score)
            genre_importance[genre] = round(gi, 2)  # Round to 2 decimal places

    return genre_importance
