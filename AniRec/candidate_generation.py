from pathlib import Path
import math

import pandas as pd

try:
    from .title_utils import normalize_title_key
except ImportError:  # Backward compatibility for direct script-style imports.
    from title_utils import normalize_title_key


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

    recommendation_candidates_df = filter_recommendation_candidates(
        completed_df,
        top_anime_df,
    )

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    recommendation_candidates_df.to_csv(output_path, index=False)
    return recommendation_candidates_df


def filter_recommendation_candidates(completed_df, top_anime_df):
    """Return candidates without performing filesystem I/O."""
    missing_completed = {"Title"} - set(completed_df.columns)
    missing_top = {"Title"} - set(top_anime_df.columns)
    if missing_completed or missing_top:
        missing = ", ".join(sorted(missing_completed | missing_top))
        raise ValueError(f"Anime data is missing required columns: {missing}")

    completed_records = [
        (_mal_id(row.get("Anime ID")), normalize_title_key(row["Title"]))
        for _, row in completed_df.iterrows()
    ]
    completed_ids = {mal_id for mal_id, _title in completed_records if mal_id is not None}
    completed_titles = {title for _mal_id_value, title in completed_records if title}
    legacy_completed_titles = {
        title for mal_id, title in completed_records if mal_id is None and title
    }

    kept_indexes = []
    seen_ids = set()
    seen_legacy_titles = set()
    for index, row in top_anime_df.iterrows():
        title = normalize_title_key(row["Title"])
        mal_id = _mal_id(row.get("Anime ID"))
        if mal_id is not None:
            if mal_id in completed_ids or (title and title in legacy_completed_titles):
                continue
            if not completed_ids and title and title in completed_titles:
                continue
            if mal_id in seen_ids:
                continue
            seen_ids.add(mal_id)
        else:
            # An untitled row carries no usable identity, so it cannot be
            # matched against the completed list or de-duplicated by title.
            if title and (title in completed_titles or title in seen_legacy_titles):
                continue
            if title:
                seen_legacy_titles.add(title)
        kept_indexes.append(index)

    return top_anime_df.loc[kept_indexes].copy()


def _mal_id(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        result = int(value)
    except (TypeError, ValueError):
        return None
    return result if result > 0 else None

