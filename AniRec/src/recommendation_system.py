#recommendation_system.py

import random
import os
import pandas as pd


def recommend_animes_with_randomness(
    recommendation_candidates_file, genre_importance_file, username,
    num_recommendations, top_anime_count, randomness_factor, output_dir
):
    try:
        # Load the recommendation candidates and genre importance
        recommendation_candidates_df = pd.read_csv(recommendation_candidates_file)
        genre_importance_df = pd.read_csv(genre_importance_file)

        # Ensure the 'Genres' column exists before proceeding
        if 'Genres' not in recommendation_candidates_df.columns:
            raise KeyError("'Genres' column is missing from the recommendation candidates data.")

        # Select the top anime based on genre importance scores
        recommendation_candidates_df['Weighted_Score'] = recommendation_candidates_df['Genres'].map(
            genre_importance_df.set_index('Genre')['Importance_Score']
        )

        # Sort by weighted score and select the top 'top_anime_count'
        top_recommendations = recommendation_candidates_df.sort_values(
            by='Weighted_Score', ascending=False
        ).head(top_anime_count)

        # Shuffle the top recommendations based on the randomness factor
        shuffled_recommendations = top_recommendations.sample(
            frac=randomness_factor / 10, random_state=random.randint(1, 1000)
        )

        # Select the specified number of recommendations from the shuffled pool
        final_recommendations = shuffled_recommendations.head(num_recommendations)

        # Save the recommendations to a CSV file in the specified output directory
        output_file = os.path.join(output_dir, f"{username}_Recommended_Anime.csv")
        final_recommendations.to_csv(output_file, index=False)
        print(f"Recommendations saved to '{output_file}'")
        return final_recommendations['Title'].tolist()  # Return the list of recommended anime titles

    except Exception as e:
        print(f"An error occurred: {e}")
        return []