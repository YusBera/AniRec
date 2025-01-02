import pandas as pd
import numpy as np


def handle_missing_scores_with_user_mean(df):
    """
    Impute missing scores (0) in the user's anime list with the average of medians
    of genres associated with each anime.
    """
    # Calculate medians for all genres
    genre_medians = df.groupby('Genres')['User Score'].median().to_dict()

    # Ensure 'User Score' is of type float64
    if df['User Score'].dtype != 'float64':
        df['User Score'] = df['User Score'].astype('float64')

    for idx, row in df.iterrows():
        if row['User Score'] == 0:  # Check if the score is missing
            genres = row['Genres'].split(", ")  # Split genres
            median_scores = [genre_medians.get(genre, 0) for genre in genres]
            imputed_score = sum(median_scores) / len(median_scores) if median_scores else 0
            df.at[idx, 'User Score'] = round(imputed_score, 2)  # Assign imputed score

    return df
