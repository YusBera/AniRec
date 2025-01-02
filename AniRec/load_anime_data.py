#load_anime_data.py

import os
import pandas as pd


def load_anime_data(filename):
    """
    Load the anime data from a CSV file. Check if the file exists before loading.
    """
    if not os.path.exists(filename):
        raise FileNotFoundError(f"The file '{filename}' does not exist. Please check the path and try again.")
    return pd.read_csv(filename)


def generate_user_profile(input_file, output_file, method='ignore_zeros'):
    """
    Generate a user profile based on genre importance and save it to a CSV file.
    """
    df = load_anime_data(input_file)

    if method == 'ignore_zeros':
        from genre_importance import calculate_genre_importance_ignore_zeros
        genre_scores = calculate_genre_importance_ignore_zeros(df)
    elif method == 'impute_zeros':
        from genre_importance import calculate_genre_importance_impute_zeros
        genre_scores = calculate_genre_importance_impute_zeros(df)
    else:
        raise ValueError("Invalid method. Choose 'ignore_zeros' or 'impute_zeros'.")

    genre_scores_df = pd.DataFrame(list(genre_scores.items()), columns=['Genre', 'Importance_Score'])
    genre_scores_df.to_csv(output_file, index=False)
    print(f"Profile generated and saved to '{output_file}'")
