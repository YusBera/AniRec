from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pandas as pd
import pytest


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO_ROOT / "AniRec"

# The baseline application uses sibling imports such as ``from anime_data import ...``.
# Keep that behavior explicit until the package layout is introduced in S02.
if str(SOURCE_DIR) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIR))


@pytest.fixture
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(autouse=True)
def isolated_default_appdata(monkeypatch):
    """Keep every implicit Windows app-data lookup inside the current test."""
    with tempfile.TemporaryDirectory(prefix="anirec-default-appdata-") as directory:
        root = Path(directory) / "roaming"
        monkeypatch.setenv("APPDATA", str(root))
        yield root


@pytest.fixture
def completed_anime_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Title": "Alpha Show",
                "Genres": ["Action", "Drama"],
                "Status": "Completed",
                "User Score": 8,
            },
            {
                "Title": "Beta Show",
                "Genres": ["Comedy"],
                "Status": "Completed",
                "User Score": 0,
            },
            {
                "Title": "Mixed Case",
                "Genres": ["Action"],
                "Status": "Completed",
                "User Score": float("nan"),
            },
        ]
    )


@pytest.fixture
def top_anime_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Title": "ALPHA SHOW", "Genres": ["Action"], "Mean Score": 8.7},
            {"Title": "Gamma Show", "Genres": ["Action"], "Mean Score": 8.2},
            {"Title": "Delta Show", "Genres": ["Comedy"], "Mean Score": None},
        ]
    )


@pytest.fixture
def genre_importance_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Genre": "Action", "Importance_Score": 120.0},
            {"Genre": "Comedy", "Importance_Score": 60.0},
        ]
    )


@pytest.fixture
def system_temp_dir():
    with tempfile.TemporaryDirectory(prefix="anirec-tests-") as directory:
        yield Path(directory)


@pytest.fixture
def csv_fixture_dir(
    system_temp_dir: Path,
    completed_anime_df: pd.DataFrame,
    top_anime_df: pd.DataFrame,
    genre_importance_df: pd.DataFrame,
) -> Path:
    completed_anime_df.to_csv(system_temp_dir / "completed_anime.csv", index=False)
    top_anime_df.to_csv(system_temp_dir / "top_anime.csv", index=False)
    genre_importance_df.to_csv(system_temp_dir / "genre_importance.csv", index=False)
    return system_temp_dir
