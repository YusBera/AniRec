from __future__ import annotations

import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, BrokenBarrierError

import pytest

from AniRec.infrastructure.json_storage import JsonStore
from AniRec.errors import StorageError
from AniRec.services import (
    RecommendationFeedback,
    RecommendationLocalState,
    RecommendationStateService,
)


def _process_state_write(root, action, entered, release, finished, attempting):
    class ObservedStore(JsonStore):
        def read(self, path):
            state = super().read(path)
            entered.set()
            if action == "hidden" and not release.wait(timeout=10):
                raise TimeoutError("fixture writer was not released")
            return state

    service = RecommendationStateService(root_override=root, store=ObservedStore())
    try:
        attempting.set()
        if action == "hidden":
            service.set_hidden("profile-a", 10, True)
        else:
            service.set_watch_later("profile-a", 20, True)
    finally:
        finished.set()


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
        "schema_version": 3,
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
    assert len(liked.feedback) == 1
    assert liked.feedback[0].mal_id == 52991
    assert liked.feedback[0].sentiment == "liked"
    assert liked.feedback[0].genres == ("Action", "Fantasy")
    assert liked.feedback[0].title == "Frieren"
    assert liked.feedback[0].recorded_at is not None

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


def test_concurrent_writes_from_separate_services_keep_both_decisions(system_temp_dir):
    rendezvous = Barrier(2)

    class RacingStore(JsonStore):
        def read(self, path):
            state = super().read(path)
            try:
                rendezvous.wait(timeout=0.5)
            except BrokenBarrierError:
                pass
            return state

    RecommendationStateService(root_override=system_temp_dir).save(
        "profile-a", RecommendationLocalState()
    )
    first = RecommendationStateService(root_override=system_temp_dir, store=RacingStore())
    second = RecommendationStateService(root_override=system_temp_dir, store=RacingStore())
    with ThreadPoolExecutor(max_workers=2) as workers:
        a = workers.submit(first.set_hidden, "profile-a", 10, True)
        b = workers.submit(second.set_watch_later, "profile-a", 20, True)
        a.result(timeout=5)
        b.result(timeout=5)
    state = RecommendationStateService(root_override=system_temp_dir).load("profile-a")
    assert state.hidden_mal_ids == frozenset({10})
    assert state.watch_later_mal_ids == frozenset({20})


def test_separate_processes_serialize_profile_read_modify_write(system_temp_dir):
    RecommendationStateService(root_override=system_temp_dir).save(
        "profile-a", RecommendationLocalState()
    )
    context = multiprocessing.get_context("spawn")
    first_read, second_read = context.Event(), context.Event()
    release, first_done, second_done = context.Event(), context.Event(), context.Event()
    first_attempting, second_attempting = context.Event(), context.Event()
    first = context.Process(
        target=_process_state_write,
        args=(system_temp_dir, "hidden", first_read, release, first_done, first_attempting),
    )
    second = context.Process(
        target=_process_state_write,
        args=(system_temp_dir, "watch_later", second_read, release, second_done, second_attempting),
    )
    try:
        first.start()
        assert first_read.wait(timeout=10)
        second.start()
        assert second_attempting.wait(timeout=10)
        assert not second_read.wait(timeout=2), "second process read before first committed"
    finally:
        release.set()
        for process in (first, second):
            if process.pid is not None:
                process.join(timeout=10)
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=5)
    assert first.exitcode == second.exitcode == 0
    assert first_done.is_set() and second_done.is_set()
    assert second_read.is_set()
    state = RecommendationStateService(root_override=system_temp_dir).load("profile-a")
    assert state.hidden_mal_ids == frozenset({10})
    assert state.watch_later_mal_ids == frozenset({20})


def test_busy_profile_lock_refuses_write_without_changing_saved_state(system_temp_dir):
    service = RecommendationStateService(root_override=system_temp_dir)
    service.save("profile-a", RecommendationLocalState())
    context = multiprocessing.get_context("spawn")
    entered, release, finished, attempting = (
        context.Event() for _ in range(4)
    )
    holder = context.Process(
        target=_process_state_write,
        args=(system_temp_dir, "hidden", entered, release, finished, attempting),
    )
    try:
        holder.start()
        assert entered.wait(timeout=10)
        service._LOCK_TIMEOUT_SECONDS = 0.2
        with pytest.raises(StorageError, match="busy; no changes were saved"):
            service.set_watch_later("profile-a", 20, True)
        assert service.load("profile-a") == RecommendationLocalState()
    finally:
        release.set()
        if holder.pid is not None:
            holder.join(timeout=10)
            if holder.is_alive():
                holder.terminate()
                holder.join(timeout=5)
    assert holder.exitcode == 0
    assert service.load("profile-a").hidden_mal_ids == frozenset({10})


@pytest.mark.parametrize("mutation", ["set_hidden", "set_watch_later", "set_show_hidden", "set_feedback", "save"])
def test_corrupt_state_is_never_overwritten_by_a_write(system_temp_dir, mutation):
    service = RecommendationStateService(root_override=system_temp_dir)
    path = service.path("profile-a")
    path.parent.mkdir(parents=True)
    original = b"{broken saved decisions"
    path.write_bytes(original)

    with pytest.raises(StorageError, match="no changes were saved"):
        if mutation == "set_hidden":
            service.set_hidden("profile-a", 10, True)
        elif mutation == "set_watch_later":
            service.set_watch_later("profile-a", 20, True)
        elif mutation == "set_show_hidden":
            service.set_show_hidden("profile-a", True)
        elif mutation == "set_feedback":
            service.set_feedback("profile-a", 30, "liked")
        else:
            service.save("profile-a", RecommendationLocalState())
    assert path.read_bytes() == original


def test_unreadable_state_is_never_overwritten(system_temp_dir):
    healthy = RecommendationStateService(root_override=system_temp_dir)
    healthy.set_hidden("profile-a", 10, True)
    path = healthy.path("profile-a")
    original = path.read_bytes()

    class UnreadableStore(JsonStore):
        def read(self, _path):
            raise OSError("fixture read denied")

    service = RecommendationStateService(
        root_override=system_temp_dir, store=UnreadableStore()
    )
    with pytest.raises(StorageError, match="no changes were saved"):
        service.set_watch_later("profile-a", 20, True)
    with pytest.raises(StorageError, match="no changes were saved"):
        service.save("profile-a", RecommendationLocalState())
    assert path.read_bytes() == original
