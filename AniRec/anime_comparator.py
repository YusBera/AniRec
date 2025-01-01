import pandas as pd


def remove_completed_animes_from_top(top_anime_file="top_anime.csv", completed_anime_file="completed_animes.csv",
                                     output_file="updated_top_anime.csv"):
    """
    Remove completed animes from the top anime list.

    Args:
    - top_anime_file (str): Path to the top anime CSV file.
    - completed_anime_file (str): Path to the completed anime CSV file.
    - output_file (str): Path to save the updated top anime list without completed animes.
    """
    try:
        # Load the top anime list and the completed anime list from CSV files
        top_anime_df = pd.read_csv(top_anime_file)
        completed_animes_df = pd.read_csv(completed_anime_file)

        # Ensure that the "Title" column exists in both dataframes
        if 'Title' not in top_anime_df.columns or 'Title' not in completed_animes_df.columns:
            raise ValueError("Both the top anime and completed anime lists must have a 'Title' column.")

        # Remove completed animes from the top anime list
        completed_titles = completed_animes_df['Title'].tolist()
        filtered_top_anime_df = top_anime_df[~top_anime_df['Title'].isin(completed_titles)]

        # Save the updated top anime list to the output CSV
        filtered_top_anime_df.to_csv(output_file, index=False)
        print(f"Updated top anime list saved to {output_file}.")

    except FileNotFoundError:
        print(f"Error: One or both of the input files '{top_anime_file}' or '{completed_anime_file}' were not found.")
    except Exception as e:
        print(f"An error occurred: {e}")
