# handle_missing_scores.py

import numpy as np
import pandas as pd


def calculate_genre_medians(df):
    """
    Calculate the median score for each genre in the completed anime data.

    Parameters:
    - df: DataFrame with user completed anime data including 'Genres' and 'User Score'

    Returns:
    - genre_medians: Dictionary of genre medians
    """
    genre_scores = {}

    # Extracting the genre and corresponding scores for each anime
    for idx, row in df.iterrows():
        score = row['User Score']
        genres = eval(row['Genres'])  # Convert genre string to list

        for genre in genres:
            if genre not in genre_scores:
                genre_scores[genre] = []
            genre_scores[genre].append(score)

    # Calculate median for each genre
    genre_medians = {genre: np.median(scores) for genre, scores in genre_scores.items()}

    return genre_medians


def handle_missing_scores_with_genre_medians(df, genre_medians):
    """
    Impute missing scores in the DataFrame using genre medians.

    Parameters:
    - df: DataFrame with user completed anime data, including 'Genres' and 'User Score'.
    - genre_medians: Dictionary of genre medians used for imputing missing scores.

    Returns:
    - df: The DataFrame with missing scores imputed.
    """

    # Ensure the 'User Score' column is of type float to avoid dtype warnings
    df['User Score'] = df['User Score'].astype(float)

    for idx, row in df.iterrows():
        score = row['User Score']

        # Check if the score is missing (NaN) or zero
        if pd.isna(score) or score == 0:  # Check for NaN or 0 scores
            genres = eval(row['Genres'])  # Convert genres string to a list
            genre_scores = [genre_medians.get(genre, None) for genre in genres]

            # Filter out None values (genres that don't have a median)
            valid_scores = [score for score in genre_scores if score is not None]

            if valid_scores:
                # If there are valid genre medians, impute with the average of those medians
                imputed_score = np.mean(valid_scores)
            else:
                # If no valid medians, fallback to 0 (or any other strategy you prefer)
                imputed_score = 0

            # Assign the imputed score, rounded to 2 decimal places
            df.at[idx, 'User Score'] = round(imputed_score, 2)

    return df
