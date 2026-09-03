"""The one line a MyAnimeList sync gets, and what the window does with it."""

from __future__ import annotations

from AniRec.gui.sync_notice import SyncNotice, build_notice
from AniRec.services.mal_sync_service import MalSyncState, SyncedCompletion
from AniRec.gui_main import create_application


def completion(mal_id, title, score, *, credited=True, day=1):
    return SyncedCompletion(
        mal_id=mal_id,
        title=title,
        score=score,
        completed_at=f"2026-09-{day:02d}T10:00:00+00:00",
        from_watch_later=credited,
    )


def state(*records, acknowledged=()):
    return MalSyncState(
        completions=tuple(records), acknowledged_mal_ids=frozenset(acknowledged)
    )


# -- the sentence -----------------------------------------------------------


def test_nothing_to_report_produces_no_notice():
    assert build_notice(MalSyncState()).is_empty


def test_an_unscored_recommendation_leads_and_offers_the_rating_page():
    """The only case with a request in it, so it is the one that leads."""
    content = build_notice(state(completion(1, "Steins;Gate", 0)))

    assert content.sentence == (
        "You finished Steins;Gate, and it has no score on MyAnimeList yet."
    )
    assert content.rate_mal_id == 1


def test_several_unscored_titles_agree_with_their_verb():
    content = build_notice(
        state(completion(1, "Alpha", 0, day=1), completion(2, "Beta", 0, day=2))
    )

    assert "they have no score" in content.sentence
    assert "Beta and Alpha" in content.sentence


def test_a_long_list_stops_naming_and_starts_counting():
    """One conjunction, at the end.

    Joining the named titles with "and" and then appending "and N more" read
    as "C and B and 1 more" - two conjunctions doing one job.
    """
    content = build_notice(
        state(
            completion(1, "Alpha", 0, day=1),
            completion(2, "Beta", 0, day=2),
            completion(3, "Gamma", 0, day=3),
        )
    )

    assert "Gamma, Beta and 1 more" in content.sentence


def test_a_scored_recommendation_reports_the_loop_closing_and_asks_nothing():
    content = build_notice(state(completion(1, "Monster", 9)))

    assert "from your Watch Later list" in content.sentence
    assert content.rate_mal_id is None


def test_a_completion_anirec_did_not_recommend_claims_no_credit():
    """Reported, because it is why the title left the feed. Not claimed."""
    content = build_notice(state(completion(1, "Beta", 7, credited=False)))

    assert "Watch Later" not in content.sentence
    assert content.sentence == (
        "MyAnimeList shows you finished an anime. Removed from your feed."
    )
    assert content.rate_mal_id is None


def test_an_unscored_title_anirec_did_not_recommend_gets_no_prompt():
    """AniRec reads the whole list; it does not get to edit all of it."""
    content = build_notice(state(completion(1, "Beta", 0, credited=False)))

    assert content.rate_mal_id is None
    assert "no score" not in content.sentence


def test_acknowledged_completions_stop_being_reported():
    assert build_notice(
        state(completion(1, "Alpha", 0), acknowledged=[1])
    ).is_empty


# -- the widget -------------------------------------------------------------


def test_the_strip_hides_itself_when_there_is_nothing_to_say():
    create_application([])
    notice = SyncNotice()

    notice.set_state(state(completion(1, "Alpha", 0)))
    assert not notice.isHidden()
    assert not notice.rate_button.isHidden()

    notice.set_state(MalSyncState())
    assert notice.isHidden()


def test_the_rating_button_appears_only_when_there_is_something_to_rate():
    create_application([])
    notice = SyncNotice()

    notice.set_state(state(completion(1, "Monster", 9)))

    assert not notice.isHidden()
    assert notice.rate_button.isHidden()


def test_the_rating_button_carries_the_title_it_named():
    create_application([])
    notice = SyncNotice()
    seen = []
    notice.rate_requested.connect(seen.append)

    notice.set_state(state(completion(42, "Alpha", 0)))
    notice.rate_button.click()

    assert seen == [42]


def test_a_missing_state_clears_the_strip_rather_than_failing():
    create_application([])
    notice = SyncNotice()
    notice.set_state(state(completion(1, "Alpha", 0)))

    notice.set_state(None)

    assert notice.isHidden()
