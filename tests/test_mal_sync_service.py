"""The read-only MyAnimeList reconciliation loop."""

from __future__ import annotations

import json

import pytest

from AniRec.errors import NetworkError
from AniRec.services.mal_sync_service import (
    MAL_SYNC_STATE_SCHEMA_VERSION,
    MalListEntry,
    MalSyncService,
    MalSyncState,
    SyncedCompletion,
    reconcile,
)
from AniRec.user_data import fetch_recent_list_entries


def entry(mal_id, *, status="completed", score=0, updated_at="2026-09-01T10:00:00+00:00",
          title=None):
    return {
        "mal_id": mal_id,
        "title": title or f"Anime {mal_id}",
        "status": status,
        "score": score,
        "updated_at": updated_at,
        "episodes_watched": 12,
    }


# -- reconcile: the decision, without a network or a clock -------------------


def test_only_completions_are_recorded_but_everything_moves_the_watermark():
    """A dropped title says nothing worth announcing and must not be re-read.

    If only completions advanced the watermark, a list whose recent activity
    was all drops would be walked from the top on every single sync.
    """
    state, watched = reconcile(
        MalSyncState(),
        [
            entry(1, status="dropped", updated_at="2026-09-03T10:00:00+00:00"),
            entry(2, status="completed", score=8, updated_at="2026-09-02T10:00:00+00:00"),
            entry(3, status="watching", updated_at="2026-09-01T10:00:00+00:00"),
        ],
        watch_later_mal_ids=frozenset(),
        synced_at="2026-09-03T12:00:00+00:00",
    )

    assert [item.mal_id for item in state.completions] == [2]
    assert state.watermark == "2026-09-03T10:00:00+00:00"
    assert state.last_synced_at == "2026-09-03T12:00:00+00:00"
    assert watched == frozenset()


def test_a_completion_is_credited_to_anirec_only_when_it_was_saved_from_a_card():
    """Seeing a recommendation and watching it elsewhere is not causation.

    Watch Later is the whole of the attribution evidence, because the Later
    control is the only thing that writes to it.
    """
    state, watched = reconcile(
        MalSyncState(),
        [entry(1, score=9), entry(2, score=7)],
        watch_later_mal_ids=frozenset({1}),
        synced_at="2026-09-03T12:00:00+00:00",
    )

    credited = {item.mal_id: item.from_watch_later for item in state.completions}
    assert credited == {1: True, 2: False}
    # The saved one has been watched, so it should leave Watch Later.
    assert watched == frozenset({1})


def test_attribution_survives_the_title_leaving_watch_later():
    """The credit is decided once and carried.

    Watch Later is emptied as titles are watched, so re-deriving attribution
    on the next sync would quietly demote a completion AniRec really earned.
    """
    first, _watched = reconcile(
        MalSyncState(),
        [entry(1, score=0, updated_at="2026-09-01T10:00:00+00:00")],
        watch_later_mal_ids=frozenset({1}),
        synced_at="2026-09-01T12:00:00+00:00",
    )
    assert first.completions[0].from_watch_later

    # The caller has since removed it from Watch Later, and the reader went
    # back and scored it.
    second, _watched = reconcile(
        first,
        [entry(1, score=9, updated_at="2026-09-02T10:00:00+00:00")],
        watch_later_mal_ids=frozenset(),
        synced_at="2026-09-02T12:00:00+00:00",
    )

    assert len(second.completions) == 1
    assert second.completions[0].from_watch_later
    assert second.completions[0].score == 9


def test_a_later_observation_replaces_an_earlier_one_for_the_same_title():
    """Finish today, score tomorrow: the second reading is the true one."""
    first, _ = reconcile(
        MalSyncState(),
        [entry(1, score=0, updated_at="2026-09-01T10:00:00+00:00")],
        watch_later_mal_ids=frozenset({1}),
        synced_at="2026-09-01T12:00:00+00:00",
    )
    assert first.unscored and first.unscored[0].needs_score

    second, _ = reconcile(
        first,
        [entry(1, score=8, updated_at="2026-09-02T10:00:00+00:00")],
        watch_later_mal_ids=frozenset({1}),
        synced_at="2026-09-02T12:00:00+00:00",
    )

    assert second.unscored == ()
    assert second.watermark == "2026-09-02T10:00:00+00:00"


def test_the_score_prompt_covers_only_what_anirec_recommended():
    """AniRec reads the whole list; it does not get to edit all of it.

    Prompting about every unrated title on somebody's account would be the
    application appointing itself editor of data it only has read access to.
    """
    state, _ = reconcile(
        MalSyncState(),
        [entry(1, score=0), entry(2, score=0)],
        watch_later_mal_ids=frozenset({1}),
        synced_at="2026-09-03T12:00:00+00:00",
    )

    assert [item.mal_id for item in state.unscored] == [1]
    # Both are still worth reporting as finished; only the prompt is narrow.
    assert {item.mal_id for item in state.unacknowledged} == {1, 2}


def test_acknowledging_a_completion_stops_it_being_announced():
    state = MalSyncState(
        completions=(
            SyncedCompletion(1, "Alpha", 0, "2026-09-01T10:00:00+00:00", True),
            SyncedCompletion(2, "Beta", 9, "2026-09-02T10:00:00+00:00", True),
        ),
        acknowledged_mal_ids=frozenset({2}),
    )

    assert [item.mal_id for item in state.unacknowledged] == [1]
    assert [item.mal_id for item in state.unscored] == [1]


# -- the fetcher: the walk stops at the watermark ----------------------------


class RecordingClient:
    """A MALClient stand-in that serves fixed pages and counts requests."""

    def __init__(self, pages):
        self._pages = pages
        self.requests = 0

    def iter_pages(self, url, *, params=None, access_token=None, client_id=None,
                   cancellation=None):
        self.params = params
        for page in self._pages:
            self.requests += 1
            yield page


def node(mal_id, updated_at, *, status="completed", score=0):
    return {
        "node": {"id": mal_id, "title": f"Anime {mal_id}"},
        "list_status": {
            "status": status,
            "score": score,
            "num_episodes_watched": 12,
            "updated_at": updated_at,
        },
    }


def test_the_walk_stops_at_the_watermark_instead_of_paging_the_whole_list():
    """This is what makes a routine sync one request rather than a hundred.

    MyAnimeList returns most-recently-touched first, so the first entry the
    previous run already saw ends the walk - and the second page is never
    requested at all.
    """
    client = RecordingClient([
        {"data": [
            node(1, "2026-09-03T10:00:00+00:00"),
            node(2, "2026-09-01T10:00:00+00:00"),
        ]},
        {"data": [node(3, "2026-08-01T10:00:00+00:00")]},
    ])

    seen = list(fetch_recent_list_entries(
        "someone", client=client, since="2026-09-01T10:00:00+00:00"
    ))

    assert [item["mal_id"] for item in seen] == [1]
    assert client.requests == 1
    assert client.params["sort"] == "list_updated_at"


def test_an_entry_equal_to_the_watermark_is_not_replayed():
    """Equality means it was the newest thing the last run saw."""
    client = RecordingClient([{"data": [node(1, "2026-09-01T10:00:00+00:00")]}])

    seen = list(fetch_recent_list_entries(
        "someone", client=client, since="2026-09-01T10:00:00+00:00"
    ))

    assert seen == []


def test_a_first_sync_with_no_watermark_reads_everything_offered():
    client = RecordingClient([
        {"data": [node(1, "2026-09-03T10:00:00+00:00")]},
        {"data": [node(2, "2026-08-01T10:00:00+00:00")]},
    ])

    seen = list(fetch_recent_list_entries("someone", client=client))

    assert [item["mal_id"] for item in seen] == [1, 2]


def test_malformed_entries_are_skipped_rather_than_ending_the_walk():
    """One bad row must not silently truncate somebody's history."""
    client = RecordingClient([{"data": [
        {"node": {"id": 1}},                       # no list_status
        {"list_status": {"updated_at": "x"}},      # no node
        {"node": {"id": "nope"}, "list_status": {"updated_at": "y"}},
        node(4, "2026-09-03T10:00:00+00:00"),
    ]}])

    seen = list(fetch_recent_list_entries("someone", client=client))

    assert [item["mal_id"] for item in seen] == [4]


# -- the service: persistence and failure --------------------------------


def test_state_round_trips_through_a_versioned_file(system_temp_dir):
    service = MalSyncService(root_override=system_temp_dir)
    state = MalSyncState(
        watermark="2026-09-03T10:00:00+00:00",
        last_synced_at="2026-09-03T12:00:00+00:00",
        completions=(SyncedCompletion(1, "Alpha", 8, "2026-09-03T10:00:00+00:00", True),),
        acknowledged_mal_ids=frozenset({1}),
    )

    service.save("profile-a", state)
    payload = json.loads(service.path("profile-a").read_text(encoding="utf-8"))

    assert payload["schema_version"] == MAL_SYNC_STATE_SCHEMA_VERSION
    assert payload["watermark"] == "2026-09-03T10:00:00+00:00"
    assert service.load("profile-a") == state


def test_unreadable_state_starts_over_instead_of_failing_a_launch(system_temp_dir):
    """Costs one full walk. Refusing to open the application costs more."""
    service = MalSyncService(root_override=system_temp_dir)
    path = service.path("profile-a")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")

    assert service.load("profile-a") == MalSyncState()
    assert service.last_error is not None


def test_a_failed_walk_does_not_advance_the_watermark(system_temp_dir):
    """A sync that never reached MyAnimeList has learned nothing.

    Advancing on failure would skip whatever changed while the network was
    down, and nothing would ever go back for it.
    """
    service = MalSyncService(root_override=system_temp_dir)
    service.save("profile-a", MalSyncState(watermark="2026-09-01T10:00:00+00:00"))

    def failing(*_args, **_kwargs):
        raise NetworkError("MyAnimeList is unreachable.")
        yield  # pragma: no cover - generator marker

    service._fetcher = failing
    with pytest.raises(NetworkError):
        service.sync(
            "profile-a", "someone", synced_at="2026-09-03T12:00:00+00:00"
        )

    assert service.load("profile-a").watermark == "2026-09-01T10:00:00+00:00"


def test_sync_reports_which_saved_titles_have_now_been_watched(system_temp_dir):
    """The service reports; the caller owns Watch Later and does the removing."""
    service = MalSyncService(
        root_override=system_temp_dir,
        fetcher=lambda *_a, **_k: iter([entry(1, score=9), entry(2, score=7)]),
    )

    state, watched = service.sync(
        "profile-a",
        "someone",
        watch_later_mal_ids=frozenset({1, 3}),
        synced_at="2026-09-03T12:00:00+00:00",
    )

    assert watched == frozenset({1})
    assert service.load("profile-a") == state


def test_acknowledgements_do_not_accumulate_for_titles_no_longer_recorded(
    system_temp_dir,
):
    service = MalSyncService(root_override=system_temp_dir)
    service.save(
        "profile-a",
        MalSyncState(
            completions=(SyncedCompletion(1, "Alpha", 8, "2026-09-01T10:00:00+00:00"),),
        ),
    )

    state = service.acknowledge("profile-a", [1, 999])

    assert state.acknowledged_mal_ids == frozenset({1})


def test_a_list_entry_rejects_an_impossible_identity():
    with pytest.raises(ValueError):
        MalListEntry(mal_id=0, title="", status="completed", score=0, updated_at="")
