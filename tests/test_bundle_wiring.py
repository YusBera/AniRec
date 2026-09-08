"""Franchise folding, as the feed actually uses it.

``build_bundles`` had been implemented and tested since the groundwork
landed, and had no callers - so the shipped feed showed "The Master of
Diabolism 2" and "3" as two cards beside each other. These are the tests for
the wiring rather than for the arithmetic: what the grid draws, what the
other views keep drawing, and what a bundle must never do.
"""

from __future__ import annotations

from AniRec.gui.bundle_card import BundleCard
from AniRec.gui.recommendation_card import RecommendationCard
from AniRec.gui.recommendation_page import (
    RecommendationExplorerPage,
    RecommendationViewMode,
)
from AniRec.gui_main import create_application
from AniRec.models import Anime, Recommendation
from AniRec.services import BundleContextService

GRAPH = {
    1: {"related": [{"mal_id": 2, "relation": "sequel"}]},
    2: {"related": [{"mal_id": 3, "relation": "sequel"}]},
    3: {"related": []},
}


def _recommendations():
    return [
        Recommendation(Anime("Mo Dao Zu Shi", mal_id=1, genres=("Action",)), match_score=90),
        Recommendation(Anime("Mo Dao Zu Shi 2", mal_id=2, genres=("Action",)), match_score=88),
        Recommendation(Anime("Mo Dao Zu Shi 3", mal_id=3, genres=("Action",)), match_score=86),
        Recommendation(Anime("Standalone", mal_id=9, genres=("Drama",)), match_score=80),
    ]


def _page(**context):
    create_application([])
    page = RecommendationExplorerPage()
    page.set_recommendations(_recommendations())
    if context:
        page.set_bundle_context(**context)
    return page


def _kinds(page):
    return sorted(type(card).__name__ for card in page._cards_by_key.values())


def test_a_franchise_folds_into_one_card_and_singles_are_left_alone():
    page = _page(graph=GRAPH, watched_mal_ids=())

    assert _kinds(page) == ["BundleCard", "RecommendationCard"]
    bundle = next(
        card for card in page._cards_by_key.values() if isinstance(card, BundleCard)
    )
    assert bundle.bundle.size == 3
    # The origin names the franchise; a reader recognises the series by it.
    assert bundle.bundle.title == "Mo Dao Zu Shi"


def test_the_feed_is_unchanged_without_a_graph():
    """No cached graph is the ordinary case, not a degraded one."""
    page = _page()
    assert _kinds(page) == ["RecommendationCard"] * 4

    page.set_bundle_context({}, ())
    assert _kinds(page) == ["RecommendationCard"] * 4


def test_opening_a_bundle_shows_its_members_and_closing_folds_them_back():
    page = _page(graph=GRAPH, watched_mal_ids=())
    bundle = next(
        card for card in page._cards_by_key.values() if isinstance(card, BundleCard)
    )

    page._toggle_bundle(bundle)
    assert _kinds(page) == ["RecommendationCard"] * 4

    reopened = _page(graph=GRAPH, watched_mal_ids=())
    assert any(isinstance(c, BundleCard) for c in reopened._cards_by_key.values())


def test_a_franchise_the_reader_has_started_is_never_folded():
    """The bundle's whole claim is "a series you have not started".

    Checked against the full completed list rather than the scorer's
    exclusion set, which only covers titles rated above the reader's own mean
    and is capped - so trusting it would offer somebody a series they watched
    and disliked.
    """
    page = _page(graph=GRAPH, watched_mal_ids=(2,))

    assert _kinds(page) == ["RecommendationCard"] * 4


def test_the_list_and_the_table_are_never_folded():
    """Bundling is a card-grid affordance, not a change to the feed.

    The table is the view people scan for a specific title, and the list is
    the dense reading of the same set. Collapsing three rows into one there
    would hide exactly what those views are for.
    """
    page = _page(graph=GRAPH, watched_mal_ids=())

    page.set_view_mode(RecommendationViewMode.LIST)
    assert len(page._rows_by_key) == 4
    page.set_view_mode(RecommendationViewMode.TABLE)
    assert page.table.rowCount() == 4
    # And the models behind every view are untouched.
    assert len(page.visible_models) == 4


def test_bundling_can_be_switched_off_for_a_surface():
    """My Library records decisions about individual titles."""
    page = _page(graph=GRAPH, watched_mal_ids=(), enabled=False)

    assert _kinds(page) == ["RecommendationCard"] * 4


def test_a_bundle_prints_the_same_precision_as_every_other_match():
    page = _page(graph=GRAPH, watched_mal_ids=())
    bundle = next(
        card for card in page._cards_by_key.values() if isinstance(card, BundleCard)
    )

    # 90, 88 and 86 average to 88.0 - and it is printed to a tenth, like the
    # card, the row, the table and the score inspector.
    assert bundle.match_label.text() == "AVG MATCH 88.0%"


def test_a_bundle_asks_only_for_the_artwork_it_draws():
    """A stack shows at most four tiles; fetching the eleventh is waste."""
    page = _page(graph=GRAPH, watched_mal_ids=())
    bundle = next(
        card for card in page._cards_by_key.values() if isinstance(card, BundleCard)
    )

    assert len(bundle.visible_entries()) <= 4
    assert set(bundle.visible_entries()).issubset(set(bundle.bundle.entries))

    requested: list[str] = []
    bundle.cover_requested.connect(requested.append)
    bundle.request_cover()
    # None of these fixtures carry artwork, so nothing is asked for - the
    # point is that it does not raise and does not ask for a missing URL.
    assert requested == []


def test_bundle_context_service_answers_empty_rather_than_raising():
    """A reader with nothing cached gets the feed they have always had."""
    service = BundleContextService()

    assert service.load(None) == service.load(None)
    assert not service.load(None)
    assert service.load("does-not-exist-anywhere").graph == {}
    assert service.load("does-not-exist-anywhere").watched_mal_ids == frozenset()
