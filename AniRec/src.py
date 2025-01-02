#src.py

import os
import pandas as pd

from anime_data import get_top_anime
from genre_importance import calculate_genre_importance, calculate_genre_medians
from handle_missing_scores import handle_missing_scores_with_genre_medians
from load_anime_data import generate_recommendation_candidates
from oauth_handler import initiate_oauth_flow, get_access_token
from recommendation_system import recommend_animes_with_randomness
from user_data import get_user_completed_animes
from handle_missing_scores import calculate_genre_medians



def save_user_completed_animes_to_csv(completed_animes_df, username):
    profile_dir = f"{username}Profile"
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    file_name = f"{profile_dir}/{username}CompletedAnimeList.csv"
    completed_animes_df.to_csv(file_name, index=False)
    print(f"Data successfully saved to '{file_name}'!")


def save_top_anime_to_csv(top_anime_df, username):
    profile_dir = f"{username}Profile"
    if not os.path.exists(profile_dir):
        os.makedirs(profile_dir)

    file_name = f"{profile_dir}/TopAnimeList.csv"
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
        # Ask for username
        username = input("Enter your username: ").strip()
        profile_dir = f"{username}Profile"

        # Create the profile folder for the user if it doesn't exist
        if not os.path.exists(profile_dir):
            os.makedirs(profile_dir)

        while True:
            print("\nWelcome to the MyAnimeList Anime Fetcher!")
            print("Please select an option:")
            print("1. Fetch top anime list")
            print("2. Fetch user completed anime data")
            print("3. Generate a new authorization code")
            print("4. Handle missing scores")
            print("5. Calculate genre importance")
            print("6. Generate recommendation candidates")
            print("7. Generate personalized anime recommendations")
            print("8. Exit")

            choice = input("Enter your choice (1-8): ").strip()

            if choice == "1":
                # Automatically fetch and save top anime data to the user's profile folder
                if not os.path.exists(f"{profile_dir}/TopAnimeList.csv"):
                    access_token = get_access_token()
                    limit = 100  # You can adjust the limit as needed
                    top_anime_df = get_top_anime(limit, access_token)
                    if not top_anime_df.empty:
                        print(f"\nTop {limit} anime fetched successfully:")
                        print(top_anime_df.head())
                        save_top_anime_to_csv(top_anime_df, username)
                    else:
                        print("Failed to fetch top anime list.")
                else:
                    print("Top anime list already exists in the profile folder.")

            elif choice == "2":
                # Automatically fetch and save user completed anime data
                access_token = get_access_token()
                username_input = username  # Use the username entered by the user
                completed_animes_df = get_user_completed_animes(username_input, access_token)
                if not completed_animes_df.empty:
                    print(f"\nCompleted anime list for user '{username_input}':")
                    print(completed_animes_df.head())
                    save_user_completed_animes_to_csv(completed_animes_df, username_input)
                else:
                    print("Failed to fetch user completed anime data.")
            elif choice == "3":  # Handling Option 3: Generate a new authorization code
                print("Generating a new authorization code...")
                access_token = initiate_oauth_flow()  # Assuming this function handles the OAuth flow
                if access_token:
                    print("Authorization successful. Access token obtained.")
                else:
                    print("Authorization failed. Please try again.")

            elif choice == "4":
                input_file = f"{profile_dir}/{username}CompletedAnimeList.csv"

                if not validate_file_exists(input_file, fetch_option=2):
                    continue

                df = pd.read_csv(input_file)
                genre_medians = calculate_genre_medians(df)
                df = handle_missing_scores_with_genre_medians(df, genre_medians)  # Updated to handle genre medians
                file_name = f"{profile_dir}/{username}_Completed_Animes_Imputed.csv"
                df.to_csv(file_name, index=False)
                print(f"Processed data saved to '{file_name}'.")

            elif choice == "5":
                input_file = f"{profile_dir}/{username}CompletedAnimeList.csv"

                if not validate_file_exists(input_file, fetch_option=2):
                    continue

                df = pd.read_csv(input_file)
                genre_medians = calculate_genre_medians(df)
                genre_importance = calculate_genre_importance(df, genre_medians)

                # Save genre importance to a CSV file inside the profile folder
                genre_importance_df = pd.DataFrame(list(genre_importance.items()),
                                                   columns=['Genre', 'Importance_Score'])
                genre_importance_file = f"{profile_dir}/{username}_Genre_Importance.csv"
                genre_importance_df.to_csv(genre_importance_file, index=False)
                print(f"Genre importance saved to '{genre_importance_file}'.")


            elif choice == "6":
                print("Generating recommendation candidates...")
                # Automatically use the files in {username}Profile directory
                user_completed_file = os.path.join(profile_dir, f"{username}_Completed_Animes_Imputed.csv")
                top_anime_file = os.path.join(profile_dir, "TopAnimeList.csv")  # Save to the profile folder
                # Validate the input files
                if validate_file_exists(user_completed_file) and validate_file_exists(top_anime_file):
                    # Generate recommendation candidates
                    output_file = os.path.join(profile_dir,
                                               f"{username}_RecommendationCandidates.csv")  # Corrected output file path
                    generate_recommendation_candidates(user_completed_file, top_anime_file,
                                                       output_file)  # Pass output_file to function
                else:
                    print("Error: One or more files are missing or invalid.")




            elif choice == "7":

                print("\nGenerating personalized recommendations...")

                # Suggested default values for top anime and randomness factor

                recommended_top_anime = 150  # Default suggestion for top anime

                recommended_randomness_factor = 5  # Default suggestion for randomness

                # Show suggested values

                print(f"Recommended number of top anime to select: {recommended_top_anime} (for top 500 anime list)")

                print(

                    "\nRecommended randomness factor: 5-7 "

                    "(Lower values lead to more focused recommendations; Higher values may introduce more randomness.)"

                )

                # Ask the user for the number of recommendations

                try:

                    num_recommendations = int(

                        input("How many recommendations would you like to receive? (Suggested: 5-10): ").strip()

                    )

                    if num_recommendations < 1:
                        print("Invalid number. Defaulting to 5 recommendations.")

                        num_recommendations = 5

                except ValueError:

                    print("Invalid input. Defaulting to 5 recommendations.")

                    num_recommendations = 5

                # Ask for the top anime count

                top_anime_count = input(

                    f"How many top anime should be selected? (Suggested: {recommended_top_anime} for top 500): ").strip()

                if not top_anime_count.isdigit():

                    top_anime_count = recommended_top_anime

                else:

                    top_anime_count = int(top_anime_count)

                if top_anime_count < 1:
                    print(f"Invalid number. Defaulting to {recommended_top_anime} top anime.")

                    top_anime_count = recommended_top_anime

                # Ask for the randomness factor

                randomness_factor = input(

                    f"What randomness factor would you like? (Suggested: {recommended_randomness_factor} for balanced diversity, 1-10): ").strip()

                if not randomness_factor.isdigit():

                    randomness_factor = recommended_randomness_factor

                else:

                    randomness_factor = int(randomness_factor)

                if randomness_factor < 1 or randomness_factor > 10:
                    print(f"Invalid randomness factor! Using default ({recommended_randomness_factor}).")

                    randomness_factor = recommended_randomness_factor

                # Prepare file paths

                recommendation_candidates_file = os.path.join(profile_dir, f"{username}_RecommendationCandidates.csv")

                genre_importance_file = os.path.join(profile_dir, f"{username}_Genre_Importance.csv")

                # Ensure these files exist before calling the recommendation function

                if validate_file_exists(recommendation_candidates_file) and validate_file_exists(genre_importance_file):

                    # Generate recommendations

                    recommendations = recommend_animes_with_randomness(

                        recommendation_candidates_file, genre_importance_file, username,

                        num_recommendations, top_anime_count, randomness_factor, profile_dir

                    )

                    if recommendations:

                        print("\nPersonalized Anime Recommendations:")

                        print("\n".join(recommendations))

                    else:

                        print("No recommendations were generated.")

                else:

                    print("Error: One or more required files are missing.")

            elif choice == "8":
                print("Exiting the program. Goodbye!")
                break
            else:
                print("Invalid choice. Please select a valid option.")
    except Exception as e:
        print(f"An error occurred: {e}")


if __name__ == "__main__":
    main()
