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


def generate_recommendation_candidates(user_completed_file, top_anime_file, output_file):
    """
    Generate a recommendation candidate list by excluding completed animes from the top anime list.
    """
    try:
        completed_animes_df = pd.read_csv(user_completed_file)
        top_anime_df = pd.read_csv(top_anime_file)

        # Debugging: Print column names to check the correct column for Anime ID or Title
        print("Completed Animes CSV Columns:", completed_animes_df.columns)
        print("Top Anime CSV Columns:", top_anime_df.columns)

        # Assuming the 'Title' column is the identifier for the anime
        completed_anime_titles = completed_animes_df['Title'].tolist()  # Replace 'Title' if necessary

        # Filter out completed anime from the top anime list based on 'Title'
        recommendation_candidates_df = top_anime_df[~top_anime_df['Title'].isin(completed_anime_titles)]

        # Ensure the output directory exists, if not create it
        profile_dir = os.path.dirname(output_file)  # Get the directory of the output file
        if not os.path.exists(profile_dir):
            os.makedirs(profile_dir)

        # Save the recommendation candidates dataframe to the file
        recommendation_candidates_df.to_csv(output_file, index=False)

        print(f"Recommendation candidates saved to '{output_file}'")

    except Exception as e:
        print(f"An error occurred: {e}")

