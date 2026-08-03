from __future__ import annotations

import json

import pytest

from AniRec.infrastructure.json_storage import JsonStore
from AniRec.services import (
    RecommendationFeedback,
    RecommendationLocalState,
    RecommendationStateService,
)


def test_state_is_schema_versioned_sorted_and_round_trips_atomically(system_temp_dir):
    service = RecommendationStateService(root_override=system_temp_dir)
    state = RecommendationLocalState(
        hidden_mal_ids=frozenset((30, 10)),
        watch_later_mal_ids=frozenset((20, 10)),
        show_hidden=True,
    )
    service.save("profile-a", state)

    payload = json.loads(service.path("profile-a").read_text(encoding="utf-8"))
    assert payload == {
        "schema_version": 2,
        "hidden_mal_ids": [10, 30],
        "watch_later_mal_ids": [10, 20],
        "show_hidden": True,
        "feedback": [],
    }
    assert service.load("profile-a") == state


def test_mutations_use_mal_id_and_survive_title_independent_restart(system_temp_dir):
    first = RecommendationStateService(root_override=system_temp_dir)
    first.set_hidden("profile-a", 52991, True)
    first.set_watch_later("profile-a", 52991, True)

    reopened = RecommendationStateService(root_override=system_temp_dir)
    assert reopened.load("profile-a") == RecommendationLocalState(
        hidden_mal_ids=frozenset((52991,)),
        watch_later_mal_ids=frozenset((52991,)),
    )
    reopened.set_hidden("profile-a", 52991, False)
    assert reopened.load("profile-a").hidden_mal_ids == frozenset()


def test_like_and_dislike_feedback_is_mutually_exclusive_and_persists_taste_metadata(
    system_temp_dir,
):
    service = RecommendationStateService(root_override=system_temp_dir)
    service.set_feedback(
        "profile-a", 52991, "liked", genres=("Action", "Fantasy"), title="Frieren"
    )
    liked = service.load("profile-a")
    assert liked.liked_mal_ids == frozenset((52991,))
    assert liked.disliked_mal_ids == frozenset()
    assert liked.feedback == (
        RecommendationFeedback(52991, "liked", ("Action", "Fantasy"), "Frieren"),
    )

    service.set_feedback("profile-a", 52991, "disliked", genres=("Action",))
    disliked = RecommendationStateService(root_override=system_temp_dir).load("profile-a")
    assert disliked.liked_mal_ids == frozenset()
    assert disliked.disliked_mal_ids == frozenset((52991,))

    service.set_feedback("profile-a", 52991, None)
    assert service.load("profile-a").feedback == ()


def test_version_one_state_migrates_without_losing_existing_lists(system_temp_dir):
    service = RecommendationStateService(root_override=system_temp_dir)
    path = service.path("profile-a")
    path.parent.mkdir(parents=True)
    path.write_text(
        '{"schema_version":1,"hidden_mal_ids":[1],"watch_later_mal_ids":[2],"show_hidden":true}',
        encoding="utf-8",
    )
    state = service.load("profile-a")
    assert state.hidden_mal_ids == frozenset((1,))
    assert state.watch_later_mal_ids == frozenset((2,))
    assert state.feedback == ()


def test_profiles_are_isolated_and_unsafe_profile_ids_are_rejected(system_temp_dir):
    service = RecommendationStateService(root_override=system_temp_dir)
    service.set_watch_later("profile-a", 1, True)
    service.set_hidden("profile-b", 2, True)

    assert service.load("profile-a").watch_later_mal_ids == frozenset((1,))
    assert service.load("profile-a").hidden_mal_ids == frozenset()
    assert service.load("profile-b").hidden_mal_ids == frozenset((2,))
    assert service.load("profile-b").watch_later_mal_ids == frozenset()
    with pytest.raises(ValueError):
        service.load("../escape")


def test_corrupt_or_unknown_schema_falls_back_without_crashing(system_temp_dir):
    service = RecommendationStateService(root_override=system_temp_dir)
    path = service.path("profile-a")
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    assert service.load("profile-a") == RecommendationLocalState()
    assert service.last_error is not None
    path.write_text('{"schema_version": 999}', encoding="utf-8")
    assert service.load("profile-a") == RecommendationLocalState()
    assert service.last_error is not None


def test_failed_atomic_replace_preserves_previous_state(system_temp_dir):
    valid = RecommendationStateService(root_override=system_temp_dir)
    valid.set_hidden("profile-a", 1, True)

    def fail_replace(_source, _destination):
        raise OSError("fixture replace failure")

    failing = RecommendationStateService(
        root_override=system_temp_dir,
        store=JsonStore(replace_func=fail_replace),
    )
    with pytest.raises(OSError):
        failing.set_watch_later("profile-a", 2, True)
    assert valid.load("profile-a") == RecommendationLocalState(
        hidden_mal_ids=frozenset((1,))
    )
