"""Local Profile statistics derived without invoking recommendation ranking."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from AniRec.gui.compatibility import UnavailableReason
from AniRec.gui.main_window import MainWindow, PageId
from AniRec.gui.taste_profile import LocalTasteProfileProvider, TasteProfileUnavailable
from AniRec.gui_main import create_application
from AniRec.infrastructure.csv_storage import CsvStorage
from AniRec.infrastructure.json_storage import JsonStore
from AniRec.services.profile_service import ProfileService
from AniRec.services.taste_profile_service import (
    ProfileStatisticsService,
    ProfileStatisticsUnavailable,
    ProfileStatisticsUnavailableReason,
)


def _active_profile(root, username: str = "reader"):
    profiles = ProfileService(root_override=root)
    profile = profiles.create_profile(username)
    directory = profiles.directory(profile.profile_id, create=True)
    JsonStore().write(profile.to_dict(), directory / "profile.json")
    profiles.set_active(profile.profile_id)
    return profiles, profile, directory


def _completed_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Anime ID": 1,
                "Title": "Alpha",
                "Genres": ["Drama", "Mystery"],
                "Studios": ["Studio A"],
                "User Score": 10,
                "Mean Score": 8.0,
                "Episodes": 12,
                "Year": 2011,
                "Start Date": "2011-04-01",
                "Large Picture URL": "https://img.example/alpha.jpg",
                "Scoring Users": 1000,
            },
            {
                "Anime ID": 2,
                "Title": "Beta",
                "Genres": ["Drama", "Romance"],
                "Studios": ["Studio A"],
                "User Score": 4,
                "Mean Score": 8.5,
                "Episodes": 24,
                "Year": 2012,
                "Start Date": "2012-07-01",
                "Scoring Users": 500000,
            },
            {
                "Anime ID": 3,
                "Title": "Gamma",
                "Genres": ["Drama", "Mystery"],
                "Studios": ["Studio A"],
                "User Score": 8,
                "Mean Score": 7.8,
                "Episodes": 13,
                "Year": 2013,
                "Start Date": "2013-10-01",
                "Scoring Users": 9000,
            },
            {
                "Anime ID": 4,
                "Title": "Delta",
                "Genres": ["Action", "Romance"],
                "Studios": ["Studio B"],
                "User Score": 6,
                "Mean Score": 7.0,
                "Episodes": 12,
                "Year": 2016,
                "Start Date": "2016-01-01",
                "Scoring Users": 120000,
            },
            {
                "Anime ID": 5,
                "Title": "Epsilon",
                "Genres": ["Action", "Romance"],
                "Studios": ["Studio B"],
                "User Score": 7,
                "Mean Score": 7.1,
                "Episodes": 12,
                "Year": 2017,
                "Start Date": "2017-04-01",
                "Scoring Users": 80000,
            },
            {
                "Anime ID": 6,
                "Title": "Zeta",
                "Genres": ["Action", "Romance"],
                "Studios": ["Studio B"],
                "User Score": 9,
                "Mean Score": 7.0,
                "Episodes": 1,
                "Year": 2018,
                "Start Date": "2018-07-01",
                "Scoring Users": 500,
            },
            {
                "Anime ID": 7,
                "Title": "Unrated",
                "Genres": ["Drama"],
                "Studios": ["Studio C"],
                "User Score": 0,
                "Mean Score": 6.5,
                "Episodes": 2,
                "Year": 2021,
                "Start Date": "2021-10-01",
                "Scoring Users": 50,
            },
        ]
    )


def test_local_statistics_build_real_sections_from_the_synced_snapshot(
    system_temp_dir,
):
    profiles, _profile, directory = _active_profile(system_temp_dir)
    storage = CsvStorage()
    storage.write(_completed_frame(), directory / "completed_anime.csv")
    storage.write(
        pd.DataFrame(
            [
                {"Anime ID": 2, "Title": "Beta"},
                {"Anime ID": 1, "Title": "Alpha"},
                {"Anime ID": 4, "Title": "Delta"},
            ]
        ),
        directory / "top_anime.csv",
    )

    payload = ProfileStatisticsService(profiles, storage=storage).profile_payload()

    assert payload["identity"]["username"] == "reader"
    assert payload["identity"]["completed"] == 7
    assert payload["identity"]["episodes"] == 76
    assert payload["identity"]["mean_score"] == pytest.approx(44 / 6)
    assert sum(
        bucket["count"] for bucket in payload["rating_distribution"]["buckets"]
    ) == 6
    assert {reading["id"] for reading in payload["fingerprint"]} == {
        "community-sync",
        "rating-bias",
        "contrarian",
    }
    overlap = payload["fingerprint"][0]
    assert overlap["caption"] == "TASTE OVERLAP"
    assert overlap["value_text"] == "61%"
    assert overlap["label"] == "IN STEP"
    assert "1.63 points" in overlap["detail"]
    assert payload["hot_takes"]["higher"][0]["title"] == "Alpha"
    assert payload["hot_takes"]["lower"][0]["title"] == "Beta"
    assert payload["hype_killers"]["biggest"]["title"] == "Beta"
    assert payload["genres"]["readings"][0]["name"] == "Drama"
    assert payload["genres"]["readings"][0]["watched"] == 4
    assert payload["genres"]["divisive"]["detail"] == "WIDE SCORE RANGE"
    assert payload["studios"]["most_watched"]["name"] == "Studio A"
    assert payload["eras"]["golden"]["label"] == "2010-2014"
    assert payload["eras"]["season_of_choice"] == "SPRING"
    # The completed-only snapshot cannot truthfully answer these yet.
    assert "habits" not in payload
    assert "timeline" not in payload
    assert "hidden_gems" not in payload


def test_unrated_rows_count_as_completed_but_not_as_zero_scores(system_temp_dir):
    profiles, _profile, directory = _active_profile(system_temp_dir)
    CsvStorage().write(_completed_frame(), directory / "completed_anime.csv")

    payload = ProfileStatisticsService(profiles).profile_payload()

    buckets = {
        item["score"]: item["count"]
        for item in payload["rating_distribution"]["buckets"]
    }
    assert payload["identity"]["completed"] == 7
    assert sum(buckets.values()) == 6
    assert 0 not in buckets


def test_provider_maps_missing_connection_and_missing_sync_to_ui_reasons(
    system_temp_dir,
):
    profiles = ProfileService(root_override=system_temp_dir)
    provider = LocalTasteProfileProvider(ProfileStatisticsService(profiles))

    with pytest.raises(TasteProfileUnavailable) as disconnected:
        provider.taste_profile()
    assert disconnected.value.reason is UnavailableReason.NOT_CONNECTED

    _active_profile(system_temp_dir)
    with pytest.raises(TasteProfileUnavailable) as unsynced:
        provider.taste_profile()
    assert unsynced.value.reason is UnavailableReason.USER_NOT_FOUND
    assert "Sync" in unsynced.value.message


def test_invalid_snapshot_fails_at_the_provider_boundary(system_temp_dir):
    profiles, _profile, directory = _active_profile(system_temp_dir)
    CsvStorage().write(
        pd.DataFrame([{"Title": "Missing score column"}]),
        directory / "completed_anime.csv",
    )

    with pytest.raises(ProfileStatisticsUnavailable) as raised:
        ProfileStatisticsService(profiles).profile_payload()

    assert raised.value.reason is ProfileStatisticsUnavailableReason.INVALID_DATA


def test_statistics_service_has_no_recommendation_engine_dependency():
    source = (
        Path(__file__)
        .parents[1]
        .joinpath("AniRec", "services", "taste_profile_service.py")
        .read_text(encoding="utf-8")
    )

    assert "recommendation_system" not in source
    assert "RecommendationService" not in source
    assert "candidate_generation" not in source


def test_profile_navigation_loads_the_local_provider_automatically(system_temp_dir):
    application = create_application([])
    profiles, _profile, directory = _active_profile(system_temp_dir)
    CsvStorage().write(_completed_frame(), directory / "completed_anime.csv")
    window = MainWindow(profile_service=profiles)

    window.navigate_to(PageId.PROFILE)
    application.processEvents()

    assert window.profile_page.is_showing_profile
    assert window.profile_page.header.username_label.text() == "reader"
    assert not window.profile_page.header.sample_stamp.isVisibleTo(
        window.profile_page.header
    )
    window.close()
