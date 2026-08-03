import math

import pytest

from genre_utils import parse_genres


def test_parse_genres_accepts_api_list():
    assert parse_genres(["Action", "Drama"]) == ["Action", "Drama"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (("Action", "Drama"), ["Action", "Drama"]),
        ("['Action', 'Drama']", ["Action", "Drama"]),
        ("Action, Drama", ["Action", "Drama"]),
        ("", []),
        ("   ", []),
        (None, []),
        (float("nan"), []),
        ("['  Bilim Kurgu  ', 'Çocuk']", ["Bilim Kurgu", "Çocuk"]),
    ],
)
def test_parse_genres_characterizes_supported_values(value, expected):
    if isinstance(value, float):
        assert math.isnan(value)
    assert parse_genres(value) == expected


def test_csv_fixtures_are_written_outside_the_repo(csv_fixture_dir, repo_root):
    assert repo_root not in csv_fixture_dir.parents
    assert (csv_fixture_dir / "completed_anime.csv").is_file()
    assert (csv_fixture_dir / "top_anime.csv").is_file()
    assert (csv_fixture_dir / "genre_importance.csv").is_file()
