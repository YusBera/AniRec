#src.py

from oauth_handler import initiate_oauth_flow
from oauth_handler import get_access_token
from anime_data import get_top_anime
from user_data import get_user_completed_animes
from anime_comparator import  remove_completed_animes_from_top

def save_top_anime_to_csv(top_anime, filename="top_anime.csv"):
    """
    Save the top anime list to a CSV file.
    """
    if top_anime.empty:
        print("No data to save.")
        return
    top_anime.to_csv(filename, index=False)
    print(f"Top anime list saved to {filename}.")

def save_user_completed_animes_to_csv(completed_animes, filename="completed_animes.csv"):
    """
    Save the user completed anime list to a CSV file.
    """
    if completed_animes.empty:
        print("No completed anime data to save.")
        return
    completed_animes.to_csv(filename, index=False)
    print(f"User completed anime list saved to {filename}.")


from oauth_handler import initiate_oauth_flow
from oauth_handler import get_access_token
from anime_data import get_top_anime
from user_data import get_user_completed_animes
from anime_comparator import remove_completed_animes_from_top  # Import the new function


def save_top_anime_to_csv(top_anime, filename="top_anime.csv"):
    """
    Save the top anime list to a CSV file.
    """
    if top_anime.empty:
        print("No data to save.")
        return
    top_anime.to_csv(filename, index=False)
    print(f"Top anime list saved to {filename}.")


def save_user_completed_animes_to_csv(completed_animes, filename="completed_animes.csv"):
    """
    Save the user completed anime list to a CSV file.
    """
    if completed_animes.empty:
        print("No completed anime data to save.")
        return
    completed_animes.to_csv(filename, index=False)
    print(f"User completed anime list saved to {filename}.")


def main():
    """
    Main function to handle the program flow with debugging options.
    """
    try:
        while True:
            print("\nWelcome to the MyAnimeList Anime Fetcher!")
            print("Please select an option:")
            print("1. Fetch top anime list")
            print("2. Fetch user completed anime data")
            print("3. Generate a new authorization code")
            print("4. Remove completed animes from top anime list")
            print("5. Exit")

            choice = input("Enter your choice (1/2/3/4/5): ").strip()

            if choice == "1":
                # Obtain access token using OAuth (this will load the token from file if available)
                access_token = get_access_token()
                # Get the number of top animes to fetch
                limit = int(input("How many top anime would you like to fetch? (Max 500): ").strip())
                top_anime_df = get_top_anime(limit, access_token)

                if not top_anime_df.empty:
                    print(f"\nTop {limit} anime fetched successfully:")
                    print(top_anime_df.head())  # Display the first few rows for inspection
                    # Optionally save the data
                    save_data = input("Do you want to save the top anime data to a CSV file? (y/n): ").strip().lower()
                    if save_data == "y":
                        save_top_anime_to_csv(top_anime_df)
                else:
                    print("Failed to fetch top anime list.")

            elif choice == "2":
                # Obtain access token using OAuth (this will load the token from file if available)
                access_token = get_access_token()
                # Fetch user completed anime data
                username = input(
                    "Enter the username of the user whose completed anime data you want to fetch: ").strip()
                completed_animes_df = get_user_completed_animes(username, access_token)

                if not completed_animes_df.empty:
                    print(f"\nCompleted anime list for user '{username}':")
                    print(completed_animes_df.head())  # Display the first few rows for inspection
                    # Optionally save the data
                    save_data = input(
                        "Do you want to save the completed anime data to a CSV file? (y/n): ").strip().lower()
                    if save_data == "y":
                        save_user_completed_animes_to_csv(completed_animes_df)
                else:
                    print("Failed to fetch user completed anime data.")

            elif choice == "3":
                try:
                    print("Starting the process to fetch a new authorization code...")
                    new_access_token = initiate_oauth_flow()
                    print("New authorization code obtained and saved successfully.")
                except Exception as e:
                    print(f"Failed to fetch new authorization code: {e}")

            elif choice == "4":
                # Remove completed animes from the top anime list
                remove_completed_animes_from_top()

            elif choice == "5":
                print("Exiting the program. Goodbye!")
                break

            else:
                print("Invalid choice. Please try again.")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()

