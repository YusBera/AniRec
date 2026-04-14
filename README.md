# AniRec

AniRec is a command-line anime recommendation project built around the MyAnimeList API. It fetches a user's completed anime list, builds a simple genre preference profile from the user's scores, filters out titles the user has already watched, and writes personalized recommendations to CSV files.

This project is intentionally small and readable. It is designed to show practical backend fundamentals: API integration, OAuth token handling, CSV data processing, input validation, and a reproducible local workflow.

## Features

- MyAnimeList OAuth 2.0 authentication with local token caching
- Fetches top-ranked anime from the MyAnimeList API
- Fetches a user's completed anime list and user scores
- Handles missing or zero user scores with genre-based median imputation
- Calculates genre importance scores from completed anime history
- Removes already completed anime from the recommendation candidate pool
- Generates CSV outputs for each pipeline step
- Provides a guided full-pipeline mode for first-time users
- Keeps a step-by-step mode for debugging and transparent review
- Keeps credentials and generated user data out of version control

## Tech Stack

- Python 3.10+
- MyAnimeList API v2
- pandas for CSV and tabular data processing
- requests for HTTP API calls

## Project Structure

```text
AniRec-main/
|-- AniRec/
|   |-- main.py                    # Command-line entry point
|   |-- anime_data.py              # MyAnimeList top anime fetcher
|   |-- user_data.py               # MyAnimeList completed-list fetcher
|   |-- oauth_handler.py           # OAuth flow and token cache
|   |-- handle_missing_scores.py   # Missing score imputation
|   |-- genre_importance.py        # User genre preference scoring
|   |-- recommendation_system.py   # Recommendation ranking and output
|   |-- candidate_generation.py    # CSV loading and candidate generation
|   `-- genre_utils.py             # Shared genre parsing helpers
|-- profiles/                      # Generated locally, ignored by Git
|-- .env.example                   # Example environment variables
|-- .gitignore
|-- requirements.txt
|-- LICENSE
`-- README.md
```

## Setup

Clone the repository and create a virtual environment:

```bash
python -m venv .venv
```

Activate it:

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## MyAnimeList OAuth Setup

AniRec requires a MyAnimeList API application.

1. Create an API client in the MyAnimeList API settings.
2. Set the redirect URI to:

```text
http://localhost:8080/callback
```

3. Export your credentials before running the app.

Windows PowerShell:

```powershell
$env:MAL_CLIENT_ID="your_client_id"
$env:MAL_CLIENT_SECRET="your_client_secret"
$env:MAL_REDIRECT_URI="http://localhost:8080/callback"
```

macOS/Linux:

```bash
export MAL_CLIENT_ID="your_client_id"
export MAL_CLIENT_SECRET="your_client_secret"
export MAL_REDIRECT_URI="http://localhost:8080/callback"
```

`MAL_CLIENT_SECRET` may be required depending on how your MyAnimeList API client is configured. The generated `token.json` file contains OAuth tokens and is intentionally ignored by Git.

## Running Locally

From the repository root, run:

```bash
python AniRec/main.py
```

The CLI starts with three options:

```text
1. Run full recommendation pipeline
2. Run step-by-step mode
3. Exit
```

### Recommended: Full Pipeline Mode

Choose option `1` for the easiest path. AniRec will guide you through the required inputs, then run the complete workflow in order:

1. Fetch top anime from MyAnimeList.
2. Fetch the user's completed anime list.
3. Impute missing or zero user scores.
4. Calculate genre importance.
5. Generate recommendation candidates.
6. Generate personalized recommendations.

The guided mode provides sensible defaults:

- Top anime to fetch: `500`
- Recommendations to generate: `10`
- Ranked candidates to consider: `150`
- Randomness factor: `5`

Press Enter at any prompt to use the default value.

### Advanced: Step-By-Step Mode

Choose option `2` if you want to inspect or rerun individual pipeline stages. This mode is useful for debugging API setup, reviewing intermediate CSV files, or explaining the project flow during a portfolio review.

Available step-by-step actions:

1. Fetch top anime list.
2. Fetch completed anime for user.
3. Start MyAnimeList OAuth flow.
4. Impute missing user scores.
5. Calculate genre importance.
6. Generate recommendation candidates.
7. Generate personalized recommendations.
8. Back to main menu.

Generated CSV files are written to:

```text
profiles/<username>/
```

That directory is ignored because it can contain personal viewing history.

## How The Recommendation Logic Works

AniRec uses a lightweight content-based approach:

1. The project reads completed anime and user scores from MyAnimeList.
2. For each genre, it calculates how often the genre appears and how highly the user scored anime in that genre.
3. Missing or zero user scores can be filled using the median score for matching genres.
4. Top anime are fetched from MyAnimeList and titles already completed by the user are removed.
5. Each candidate anime is scored by summing the user's genre importance values for that anime's genres.
6. The highest-scoring candidates are ranked, then a configurable randomness factor adds some variety to the final list.

This is not a machine learning model. It is a clear, explainable recommendation pipeline suitable for demonstrating backend data processing and API integration.

## Why This Project Matters

For a backend internship portfolio, AniRec demonstrates practical skills that reviewers can inspect quickly:

- Integrating with a real third-party API
- Managing OAuth credentials without committing secrets
- Building a multi-step data pipeline
- Reading and writing structured CSV data
- Handling incomplete data safely
- Keeping recommendation logic explainable instead of hiding it behind a black box

## Current Limitations

- The recommendation algorithm is simple and genre-based; it does not use collaborative filtering.
- Matching completed anime by title can miss edge cases where MyAnimeList titles differ across versions or languages.
- The project is currently a CLI workflow, not a deployed web service.
- There is no automated test suite yet.

## Suggested Next Improvements

- Add unit tests for genre parsing, score imputation, candidate filtering, and recommendation scoring.
- Store anime IDs when fetching data so filtering does not rely only on titles.
- Add a small FastAPI endpoint layer if you want to showcase API design in addition to data processing.
- Add structured logging for cleaner debugging.
