import os
import pandas as pd
from oauth_handler import initiate_oauth_flow, get_access_token
from anime_data import get_top_anime
from user_data import get_user_completed_animes
from handle_missing_scores import handle_missing_scores_with_user_mean
from genre_importance import calculate_genre_importance, calculate_genre_medians


def save_user_completed_animes_to_csv(completed_animes_df, username):
    file_name = f"{username}CompletedAnimeList.csv"
    completed_animes_df.to_csv(file_name, index=False)
    print(f"Data successfully saved to '{file_name}'!")


def save_top_anime_to_csv(top_anime_df):
    file_name = "TopAnimeList.csv"
    top_anime_df.to_csv(file_name, index=False)
    print(f"Top anime data successfully saved to '{file_name}'!")


def validate_file_exists(filename, fetch_option=None):
    """
    Check if the specified file exists. If not, prompt the user to fetch the data first.
    """
    if not os.path.exists(filename):
        print(f"Error: File '{filename}' not found.")
        if fetch_option:
            print(f"Please run Option {fetch_option} in the main menu to generate the required file.")
        return False
    return True


def main():
    try:
        while True:
            print("\nWelcome to the MyAnimeList Anime Fetcher!")
            print("Please select an option:")
            print("1. Fetch top anime list")
            print("2. Fetch user completed anime data")
            print("3. Generate a new authorization code")
            print("4. Handle missing scores")
            print("5. Calculate genre importance")
            print("6. Exit")

            choice = input("Enter your choice (1-6): ").strip()

            if choice == "1":
                access_token = get_access_token()
                limit = int(input("How many top anime would you like to fetch? (Max 500): ").strip())
                top_anime_df = get_top_anime(limit, access_token)
                if not top_anime_df.empty:
                    print(f"\nTop {limit} anime fetched successfully:")
                    print(top_anime_df.head())
                    save_data = input("Do you want to save the top anime data to a CSV file? (y/n): ").strip().lower()
                    if save_data == "y":
                        save_top_anime_to_csv(top_anime_df)
                else:
                    print("Failed to fetch top anime list.")

            elif choice == "2":
                access_token = get_access_token()
                username = input("Enter the username of the user: ").strip()
                completed_animes_df = get_user_completed_animes(username, access_token)
                if not completed_animes_df.empty:
                    print(f"\nCompleted anime list for user '{username}':")
                    print(completed_animes_df.head())
                    save_user_completed_animes_to_csv(completed_animes_df, username)
                else:
                    print("Failed to fetch user completed anime data.")

            elif choice == "4":
                username = input("Enter the username of the user: ").strip()
                input_file = f"{username}CompletedAnimeList.csv"

                if not validate_file_exists(input_file, fetch_option=2):
                    continue

                df = pd.read_csv(input_file)
                genre_medians = calculate_genre_medians(df)
                df = handle_missing_scores_with_user_mean(df, genre_medians)
                file_name = f"{username}_Completed_Animes_Imputed.csv"
                df.to_csv(file_name, index=False)
                print(f"Processed data saved to '{file_name}'.")


            elif choice == "5":
                username = input("Enter the username of the user: ").strip()
                input_file = f"{username}CompletedAnimeList.csv"
                if not validate_file_exists(input_file, fetch_option=2):
                    continue
                df = pd.read_csv(input_file)
                genre_medians = calculate_genre_medians(df)
                genre_importance = calculate_genre_importance(df, genre_medians)
                # Save Genre Importance to File
                output_file = f"{username}_Genre_Importance.csv"
                pd.DataFrame([
                    {"Genre": genre, "Importance": importance}
                    for genre, importance in genre_importance.items()
                ]).to_csv(output_file, index=False)
                print(f"Genre importance scores saved to '{output_file}'.")

            elif choice == "6":
                print("Exiting the program. Goodbye!")
                break

            else:
                print("Invalid choice. Please select a valid option.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
