from __future__ import annotations

import logging
import re
from pathlib import Path

import requests

try:
    from .application.pipeline import PipelineOrchestrator
    from .application.operations import (
        calculate_genre_importance_file,
        create_recommendation_candidates_file,
        fetch_completed_anime_to_file,
        fetch_top_anime_to_file,
        generate_recommendations_file,
        impute_missing_scores_file,
        require_file,
    )
    from .errors import AniRecError, presentable_error
    from .infrastructure.csv_storage import CsvStorage
    from .infrastructure.logging_config import configure_logging
    from .infrastructure.paths import profile_dir
    from .models import PipelineSettings
    from .services import AnimeDataService, ProfileService, RecommendationService
except ImportError:  # Backward compatibility for ``python AniRec/main.py``.
    from application.pipeline import PipelineOrchestrator
    from application.operations import (
        calculate_genre_importance_file,
        create_recommendation_candidates_file,
        fetch_completed_anime_to_file,
        fetch_top_anime_to_file,
        generate_recommendations_file,
        impute_missing_scores_file,
        require_file,
    )
    from errors import AniRecError, presentable_error
    from infrastructure.csv_storage import CsvStorage
    from infrastructure.logging_config import configure_logging
    from infrastructure.paths import profile_dir
    from models import PipelineSettings
    from services import AnimeDataService, ProfileService, RecommendationService

try:
    from .oauth_handler import get_access_token, initiate_oauth_flow
except ImportError:  # Backward compatibility for ``python AniRec/main.py``.
    from oauth_handler import get_access_token, initiate_oauth_flow

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


def build_cli_runtime():
    logger = configure_logging(logger_name="AniRec.cli")
    orchestrator = PipelineOrchestrator(
        anime_data=AnimeDataService(),
        profiles=ProfileService(),
        recommendations=RecommendationService(),
        storage=CsvStorage(),
        access_token_provider=get_access_token,
    )
    return orchestrator, logger


def _resolve_cli_runtime(orchestrator=None, logger=None):
    if orchestrator is None:
        return build_cli_runtime()
    if logger is None:
        logger = logging.getLogger("AniRec.cli.injected")
        if not logger.handlers:
            logger.addHandler(logging.NullHandler())
        logger.propagate = False
    return orchestrator, logger


def run_full_pipeline(orchestrator=None, logger=None):
    print_header("Full Recommendation Pipeline")
    username = prompt_username()
    if not username:
        return

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

    settings = PipelineSettings(
        top_anime_limit=top_anime_limit,
        recommendation_count=num_recommendations,
        candidate_pool_size=top_anime_count,
        randomness_factor=randomness_factor,
    )
    orchestrator, logger = _resolve_cli_runtime(orchestrator, logger)
    try:
        result = orchestrator.run_full(
            username,
            settings,
            progress_callback=print_pipeline_progress,
        )
    except Exception as error:
        logger.exception("Full recommendation pipeline failed")
        print_user_friendly_error(error)
        print("Pipeline stopped. Fix the issue above, then run the pipeline again.")
        return None

    print("\nPipeline complete.")
    if result.generated_files:
        print_info(f"Output folder: {Path(result.generated_files[-1]).parent}")
    print("\nRecommendations:")
    for index, recommendation in enumerate(result.recommendations, start=1):
        print(f"  {index}. {recommendation.anime.display_title}")
    return result


def run_step_by_step_mode(orchestrator=None, logger=None):
    print_header("Step-By-Step Mode")
    username = prompt_username()
    if not username:
        return

    orchestrator, logger = _resolve_cli_runtime(orchestrator, logger)
    step_ids = {
        "1": "fetch_top",
        "2": "fetch_completed",
        "3": "oauth",
        "4": "impute_scores",
        "5": "genre_importance",
        "6": "generate_candidates",
        "7": "generate_recommendations",
    }

    while True:
        print_step_by_step_menu()
        choice = input("Choose an option (1-8): ").strip()

        if choice == "8":
            print("Returning to main menu.")
            break
        if choice not in step_ids:
            print("Please choose a number from 1 to 8.")
            continue

        settings = _prompt_step_settings(choice)
        try:
            result = orchestrator.run_step(
                step_ids[choice],
                username,
                settings,
                progress_callback=print_pipeline_progress,
            )
        except Exception as error:
            logger.exception("Single pipeline step failed: %s", step_ids[choice])
            print_user_friendly_error(error)
            continue

        print_success("Operation completed.")
        for output in result.generated_files:
            print_info(f"Output: {output}")
        if result.recommendations:
            print("\nRecommendations:")
            for index, recommendation in enumerate(result.recommendations, start=1):
                print(f"  {index}. {recommendation.anime.display_title}")


def _prompt_step_settings(choice):
    top_limit = DEFAULT_TOP_ANIME_LIMIT
    recommendation_count = DEFAULT_RECOMMENDATION_COUNT
    candidate_pool_size = DEFAULT_CANDIDATE_POOL_SIZE
    randomness = DEFAULT_RANDOMNESS_FACTOR
    if choice == "1":
        top_limit = prompt_int("Top anime to fetch", top_limit, minimum=1)
    elif choice == "7":
        recommendation_count = prompt_int(
            "Recommendations to generate",
            recommendation_count,
            minimum=1,
        )
        candidate_pool_size = prompt_int(
            "Ranked candidates to consider",
            max(candidate_pool_size, recommendation_count),
            minimum=recommendation_count,
        )
        randomness = prompt_int(
            "Randomness factor, 1-10",
            randomness,
            minimum=1,
            maximum=10,
        )
    return PipelineSettings(
        top_anime_limit=top_limit,
        recommendation_count=recommendation_count,
        candidate_pool_size=candidate_pool_size,
        randomness_factor=randomness,
    )


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
    result = fetch_top_anime_to_file(
        profile_dir,
        limit=limit,
        access_token=access_token,
    )
    print_success(f"Saved {result.row_count} anime.")
    print_info(f"Output: {result.path}")
    return result.path


def fetch_completed_anime(username, profile_dir):
    print_info(f"Requesting completed anime for '{username}'...")
    access_token = get_access_token()
    result = fetch_completed_anime_to_file(
        username,
        profile_dir,
        access_token=access_token,
    )
    print_success(f"Saved {result.row_count} completed anime.")
    print_info(f"Output: {result.path}")
    return result.path


def impute_missing_scores(profile_dir):
    print_info(f"Reading completed anime from {profile_dir}")
    result = impute_missing_scores_file(profile_dir)
    print_success("Missing or zero scores handled.")
    print_info(f"Output: {result.path}")
    return result.path


def calculate_and_save_genre_importance(profile_dir):
    print_info(f"Calculating genre importance from {profile_dir}")
    result = calculate_genre_importance_file(profile_dir)
    print_success(f"Saved {result.row_count} genre importance scores.")
    print_info(f"Output: {result.path}")
    return result.path


def create_recommendation_candidates(profile_dir):
    print_info("Filtering out anime the user has already completed...")
    result = create_recommendation_candidates_file(profile_dir)
    print_success(f"Saved {result.row_count} recommendation candidates.")
    print_info(f"Output: {result.path}")
    return result.path


def generate_recommendations(
    username,
    profile_dir,
    num_recommendations=None,
    top_anime_count=None,
    randomness_factor=None,
):
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
    result = generate_recommendations_file(
        safe_profile_name(username),
        profile_dir,
        num_recommendations=num_recommendations,
        top_anime_count=top_anime_count,
        randomness_factor=randomness_factor,
    )
    print_success(f"Generated {result.row_count} recommendations.")
    print_info(f"Output: {result.path}")
    print("\nRecommendations:")
    for index, title in enumerate(result.titles, start=1):
        print(f"  {index}. {title}")
    return result.path


def prepare_profile_dir(username, root_override=None):
    directory = get_profile_dir(username, root_override=root_override)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def get_profile_dir(username, root_override=None):
    return profile_dir(safe_profile_name(username), root_override=root_override)


def safe_profile_name(username):
    safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", username).strip("._")
    return safe_name or "mal_user"


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


def print_pipeline_progress(progress):
    print_step_start(progress.current, progress.total, progress.message)


def print_user_friendly_error(error):
    if isinstance(error, AniRecError):
        model = error.to_user_error()
        print(f"  Error: {model.title}")
        print(f"  {model.description}")
        print(f"  Suggested action: {model.solution}")
        return

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

    model = presentable_error(error)
    print(f"  Error: {model.title}")
    print(f"  {model.description}")
    print(f"  Suggested action: {model.solution}")


if __name__ == "__main__":
    main()
