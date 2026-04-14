from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import requests

from anime_data import get_top_anime
from candidate_generation import generate_recommendation_candidates
from genre_importance import calculate_genre_importance
from handle_missing_scores import (
    calculate_genre_medians,
    handle_missing_scores_with_genre_medians,
)
from oauth_handler import get_access_token, initiate_oauth_flow
from recommendation_system import recommend_animes_with_randomness
from user_data import get_user_completed_animes

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROFILES_DIR = PROJECT_ROOT / "profiles"

DEFAULT_TOP_ANIME_LIMIT = 500
DEFAULT_RECOMMENDATION_COUNT = 10
DEFAULT_CANDIDATE_POOL_SIZE = 150
DEFAULT_RANDOMNESS_FACTOR = 5


def main():
    while True:
        print_main_menu()
        choice = input("Choose an option (1-3): ").strip()

        if choice == "1":
            run_full_pipeline()
        elif choice == "2":
            run_step_by_step_mode()
        elif choice == "3":
            print("Goodbye.")
            break
        else:
            print("Please choose 1, 2, or 3.")


def print_main_menu():
    print_header("AniRec")
    print("1. Run full recommendation pipeline")
    print("2. Run step-by-step mode")
    print("3. Exit")


def run_full_pipeline():
    print_header("Full Recommendation Pipeline")
    username = prompt_username()
    if not username:
        return

    profile_dir = prepare_profile_dir(username)
    print_info(f"Output folder: {profile_dir}")

    top_anime_limit = prompt_int(
        "Top anime to fetch",
        DEFAULT_TOP_ANIME_LIMIT,
        minimum=1,
    )
    num_recommendations = prompt_int(
        "Recommendations to generate",
        DEFAULT_RECOMMENDATION_COUNT,
        minimum=1,
    )
    candidate_pool_default = max(DEFAULT_CANDIDATE_POOL_SIZE, num_recommendations)
    top_anime_count = prompt_int(
        "Ranked candidates to consider",
        candidate_pool_default,
        minimum=num_recommendations,
    )
    randomness_factor = prompt_int(
        "Randomness factor, 1-10",
        DEFAULT_RANDOMNESS_FACTOR,
        minimum=1,
        maximum=10,
    )

    steps = [
        ("Fetch top anime", lambda: fetch_top_anime(profile_dir, top_anime_limit)),
        ("Fetch completed anime", lambda: fetch_completed_anime(username, profile_dir)),
        ("Handle missing scores", lambda: impute_missing_scores(profile_dir)),
        ("Calculate genre importance", lambda: calculate_and_save_genre_importance(profile_dir)),
        ("Generate recommendation candidates", lambda: create_recommendation_candidates(profile_dir)),
        (
            "Generate recommendations",
            lambda: generate_recommendations(
                username,
                profile_dir,
                num_recommendations,
                top_anime_count,
                randomness_factor,
            ),
        ),
    ]

    for index, (label, action) in enumerate(steps, start=1):
        try:
            print_step_start(index, len(steps), label)
            action()
            print_step_success(label)
        except (requests.RequestException, RuntimeError, ValueError, FileNotFoundError) as error:
            print_step_failure(label, error)
            print("Pipeline stopped. Fix the issue above, then run the pipeline again.")
            return

    print("\nPipeline complete. Review your recommendation CSV in:")
    print(f"  {profile_dir}")


def run_step_by_step_mode():
    print_header("Step-By-Step Mode")
    username = prompt_username()
    if not username:
        return

    profile_dir = prepare_profile_dir(username)
    print_info(f"Output folder: {profile_dir}")

    while True:
        print_step_by_step_menu()
        choice = input("Choose an option (1-8): ").strip()

        try:
            if choice == "1":
                fetch_top_anime(profile_dir)
            elif choice == "2":
                fetch_completed_anime(username, profile_dir)
            elif choice == "3":
                print_info("Opening MyAnimeList OAuth flow.")
                initiate_oauth_flow()
                print_success("OAuth token saved.")
            elif choice == "4":
                impute_missing_scores(profile_dir)
            elif choice == "5":
                calculate_and_save_genre_importance(profile_dir)
            elif choice == "6":
                create_recommendation_candidates(profile_dir)
            elif choice == "7":
                generate_recommendations(username, profile_dir)
            elif choice == "8":
                print("Returning to main menu.")
                break
            else:
                print("Please choose a number from 1 to 8.")
        except (requests.RequestException, RuntimeError, ValueError, FileNotFoundError) as error:
            print_user_friendly_error(error)


def print_step_by_step_menu():
    print_header("Step-By-Step Menu")
    print("1. Fetch top anime list")
    print("2. Fetch completed anime for user")
    print("3. Start MyAnimeList OAuth flow")
    print("4. Impute missing user scores")
    print("5. Calculate genre importance")
    print("6. Generate recommendation candidates")
    print("7. Generate personalized recommendations")
    print("8. Back to main menu")


def fetch_top_anime(profile_dir, limit=None):
    if limit is None:
        limit = prompt_int("Top anime to fetch", DEFAULT_TOP_ANIME_LIMIT, minimum=1)

    print_info("Requesting top anime from MyAnimeList...")
    access_token = get_access_token()
    top_anime_df = get_top_anime(limit=limit, access_token=access_token)

    if top_anime_df.empty:
        raise RuntimeError("MyAnimeList returned no top anime data.")

    output_file = profile_dir / "top_anime.csv"
    top_anime_df.to_csv(output_file, index=False)
    print_success(f"Saved {len(top_anime_df)} anime.")
    print_info(f"Output: {output_file}")
    return output_file


def fetch_completed_anime(username, profile_dir):
    print_info(f"Requesting completed anime for '{username}'...")
    access_token = get_access_token()
    completed_anime_df = get_user_completed_animes(username, access_token)

    if completed_anime_df.empty:
        raise RuntimeError(
            "No completed anime were returned. Check the username and MyAnimeList list privacy settings."
        )

    output_file = profile_dir / "completed_anime.csv"
    completed_anime_df.to_csv(output_file, index=False)
    print_success(f"Saved {len(completed_anime_df)} completed anime.")
    print_info(f"Output: {output_file}")
    return output_file


def impute_missing_scores(profile_dir):
    input_file = require_file(profile_dir / "completed_anime.csv", "Run 'Fetch completed anime' first.")
    print_info(f"Reading completed anime from {input_file}")
    completed_anime_df = pd.read_csv(input_file)
    genre_medians = calculate_genre_medians(completed_anime_df)
    imputed_df = handle_missing_scores_with_genre_medians(completed_anime_df, genre_medians)

    output_file = profile_dir / "completed_anime_imputed.csv"
    imputed_df.to_csv(output_file, index=False)
    print_success("Missing or zero scores handled.")
    print_info(f"Output: {output_file}")
    return output_file


def calculate_and_save_genre_importance(profile_dir):
    input_file = profile_dir / "completed_anime_imputed.csv"
    if not input_file.exists():
        input_file = require_file(
            profile_dir / "completed_anime.csv",
            "Run 'Fetch completed anime' first.",
        )

    print_info(f"Calculating genre importance from {input_file}")
    completed_anime_df = pd.read_csv(input_file)
    genre_medians = calculate_genre_medians(completed_anime_df)
    genre_importance = calculate_genre_importance(completed_anime_df, genre_medians)

    if not genre_importance:
        raise RuntimeError("No genre importance scores were generated. Check that user scores exist.")

    genre_importance_df = pd.DataFrame(
        sorted(genre_importance.items(), key=lambda item: item[1], reverse=True),
        columns=["Genre", "Importance_Score"],
    )
    output_file = profile_dir / "genre_importance.csv"
    genre_importance_df.to_csv(output_file, index=False)
    print_success(f"Saved {len(genre_importance_df)} genre importance scores.")
    print_info(f"Output: {output_file}")
    return output_file


def create_recommendation_candidates(profile_dir):
    completed_file = profile_dir / "completed_anime_imputed.csv"
    if not completed_file.exists():
        completed_file = require_file(
            profile_dir / "completed_anime.csv",
            "Run 'Fetch completed anime' first.",
        )

    top_anime_file = require_file(profile_dir / "top_anime.csv", "Run 'Fetch top anime list' first.")
    output_file = profile_dir / "recommendation_candidates.csv"

    print_info("Filtering out anime the user has already completed...")
    candidates_df = generate_recommendation_candidates(completed_file, top_anime_file, output_file)
    print_success(f"Saved {len(candidates_df)} recommendation candidates.")
    print_info(f"Output: {output_file}")
    return output_file


def generate_recommendations(
    username,
    profile_dir,
    num_recommendations=None,
    top_anime_count=None,
    randomness_factor=None,
):
    candidates_file = require_file(
        profile_dir / "recommendation_candidates.csv",
        "Run 'Generate recommendation candidates' first.",
    )
    genre_importance_file = require_file(
        profile_dir / "genre_importance.csv",
        "Run 'Calculate genre importance' first.",
    )

    if num_recommendations is None:
        num_recommendations = prompt_int(
            "Recommendations to generate",
            DEFAULT_RECOMMENDATION_COUNT,
            minimum=1,
        )
    if top_anime_count is None:
        candidate_pool_default = max(DEFAULT_CANDIDATE_POOL_SIZE, num_recommendations)
        top_anime_count = prompt_int(
            "Ranked candidates to consider",
            candidate_pool_default,
            minimum=num_recommendations,
        )
    if randomness_factor is None:
        randomness_factor = prompt_int(
            "Randomness factor, 1-10",
            DEFAULT_RANDOMNESS_FACTOR,
            minimum=1,
            maximum=10,
        )

    print_info("Ranking candidates against the user's genre profile...")
    recommendations = recommend_animes_with_randomness(
        candidates_file,
        genre_importance_file,
        safe_profile_name(username),
        num_recommendations,
        top_anime_count,
        randomness_factor,
        profile_dir,
    )

    if not recommendations:
        raise RuntimeError("No recommendations were generated. Try fetching more top anime.")

    output_file = profile_dir / f"{safe_profile_name(username)}_recommendations.csv"
    print_success(f"Generated {len(recommendations)} recommendations.")
    print_info(f"Output: {output_file}")
    print("\nRecommendations:")
    for index, title in enumerate(recommendations, start=1):
        print(f"  {index}. {title}")
    return output_file


def prepare_profile_dir(username):
    profile_dir = get_profile_dir(username)
    profile_dir.mkdir(parents=True, exist_ok=True)
    return profile_dir


def get_profile_dir(username):
    return PROFILES_DIR / safe_profile_name(username)


def safe_profile_name(username):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", username).strip("._")
    return safe_name or "mal_user"


def require_file(path, hint):
    if not path.exists():
        raise FileNotFoundError(f"Missing '{path}'. {hint}")
    return path


def prompt_username():
    username = input("MyAnimeList username: ").strip()
    if not username:
        print("A MyAnimeList username is required.")
        return None
    return username


def prompt_int(label, default, minimum=None, maximum=None):
    range_hint = ""
    if minimum is not None and maximum is not None:
        range_hint = f", {minimum}-{maximum}"
    elif minimum is not None:
        range_hint = f", minimum {minimum}"
    elif maximum is not None:
        range_hint = f", maximum {maximum}"

    raw_value = input(f"{label} (default: {default}{range_hint}): ").strip()
    if not raw_value:
        return default

    try:
        value = int(raw_value)
    except ValueError:
        print(f"Invalid number. Using default: {default}.")
        return default

    if minimum is not None and value < minimum:
        print(f"Value must be at least {minimum}. Using default: {default}.")
        return default

    if maximum is not None and value > maximum:
        print(f"Value must be at most {maximum}. Using default: {default}.")
        return default

    return value


def print_header(title):
    print(f"\n=== {title} ===")


def print_info(message):
    print(f"  {message}")


def print_success(message):
    print(f"  Success: {message}")


def print_step_start(index, total, label):
    print(f"\n[{index}/{total}] {label}")


def print_step_success(label):
    print(f"  Step complete: {label}")


def print_step_failure(label, error):
    print(f"  Step failed: {label}")
    print_user_friendly_error(error)


def print_user_friendly_error(error):
    if isinstance(error, FileNotFoundError):
        print(f"  Error: {error}")
        return

    if isinstance(error, requests.HTTPError):
        response = error.response
        status_code = response.status_code if response is not None else "unknown"
        print(f"  Error: MyAnimeList API request failed with status {status_code}.")
        if status_code == 401:
            print("  Check your OAuth token or run the OAuth flow again.")
        elif status_code == 403:
            print("  Check API permissions and whether the user's anime list is private.")
        elif status_code == 404:
            print("  Check the MyAnimeList username or API endpoint.")
        else:
            print("  Try again later or check the API response in the terminal output.")
        return

    if isinstance(error, requests.Timeout):
        print("  Error: The request timed out. Try again in a moment.")
        return

    if isinstance(error, requests.ConnectionError):
        print("  Error: Could not connect to MyAnimeList. Check your internet connection.")
        return

    message = str(error).strip() or error.__class__.__name__
    print(f"  Error: {message}")


if __name__ == "__main__":
    main()
