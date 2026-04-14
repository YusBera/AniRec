from pathlib import Path

import pandas as pd


def load_anime_data(file_path, required_columns=None):
    """Load a CSV file and validate the columns used by the pipeline."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    df = pd.read_csv(path)
    if required_columns:
        missing_columns = set(required_columns) - set(df.columns)
        if missing_columns:
            missing = ", ".join(sorted(missing_columns))
            raise ValueError(f"{path} is missing required columns: {missing}")
    return df


def generate_recommendation_candidates(user_completed_file, top_anime_file, output_file):
    """Create a candidate list by removing anime the user has already completed."""
    completed_df = load_anime_data(user_completed_file, required_columns=["Title"])
    top_anime_df = load_anime_data(top_anime_file, required_columns=["Title"])

    completed_titles = set(completed_df["Title"].astype(str).str.casefold())
    recommendation_candidates_df = top_anime_df[
        ~top_anime_df["Title"].astype(str).str.casefold().isin(completed_titles)
    ]

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    recommendation_candidates_df.to_csv(output_path, index=False)
    return recommendation_candidates_df

