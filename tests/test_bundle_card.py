"""The collapsed bundle keeps a card's footprint and its state stays legible.

The geometry here is load-bearing: a bundle that is a different size from the
cards beside it breaks the row, and that is invisible in a screenshot until
someone measures it.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPixmap

from AniRec.gui.bundle_card import (
    COUNT_FROM,
    BundleCard,
    BundleInfoBlock,
)
from AniRec.gui.bundle_view_model import BundleViewModel
from AniRec.gui.design_tokens import SPACE
from AniRec.gui.recommendation_card import (
    CARD_WIDTH,
    COVER_HEIGHT,
    COVER_WIDTH,
    RecommendationCard,
)
from AniRec.gui.recommendation_view_model import RecommendationViewModel
from AniRec.gui_main import create_application
from AniRec.models import Anime, Recommendation


def entry(mal_id, title, match=80.0, year=2010):
    return RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                title,
                mal_id=mal_id,
                genres=("Drama", "Mystery"),
                mean_score=8.0,
                status="finished_airing",
                episodes=12,
                year=year,
                media_type="tv",
            ),
            match_score=match,
            reason="Because you rated Drama highly.",
            genre_contributions=(("Drama", 20.0), ("Mystery", 10.0)),
        )
    )


def bundle(count=5):
    return BundleViewModel.from_entries(
        [entry(index, "Entry %d" % index, match=90 - index * 5, year=2000 + index)
         for index in range(1, count + 1)]
    )


def test_the_stack_occupies_exactly_a_covers_footprint():
    """Otherwise the bundle's title sits off the row's baseline.

    Single covers float 108-176px wide with their artwork; a bundle pins the
    canonical frame because a 2x2 tile block is only poster-shaped there.
    """
    create_application([])
    card = BundleCard(bundle())

    assert card.stack_label.width() == COVER_WIDTH
    assert card.stack_label.height() == COVER_HEIGHT


def test_a_bundle_never_makes_the_grid_taller_than_the_cards_do():
    """The feed pins every cell to the tallest one in it.

    So a bundle does not need to match a card's natural height - it will be
    stretched to it. What it must not do is *exceed* it, because then one
    bundle would add its own surplus to every card in the feed. A bundle
    carries less text than a card (no genres, metadata, MAL score or reason),
    so this holds by construction; the test is here to catch someone adding
    a row to it without noticing what that costs the grid.
    """
    create_application([])
    card = BundleCard(bundle())
    single = RecommendationCard(entry(99, "Single"))

    assert card.sizeHint().height() <= single.sizeHint().height()


def test_four_entries_show_four_covers_and_five_show_a_count():
    """Three covers and a "+1" is worse than showing all four."""
    create_application([])
    assert COUNT_FROM == 5
    assert BundleCard(bundle(4)).bundle.size == 4
    assert BundleCard(bundle(5)).bundle.size == 5
    # The count only exists to stand in for covers there is no room for.
    four = BundleCard(bundle(4))._render_stack().toImage()
    five = BundleCard(bundle(5))._render_stack().toImage()
    assert four != five


def test_opening_and_closing_changes_how_the_card_reads():
    create_application([])
    card = BundleCard(bundle())
    card.show()

    closed = card.grab().toImage()
    card.set_expanded(True)
    opened = card.grab().toImage()

    assert card.is_expanded()
    assert card.open_button.text() == "Close"
    assert opened != closed, "an opened bundle must not look identical to a closed one"


def test_the_card_reports_the_mean_not_the_best_entry():
    create_application([])
    model = BundleViewModel.from_entries(
        [entry(1, "High", match=94.0), entry(2, "Low", match=60.0)]
    )
    card = BundleCard(model)

    assert "77" in card.match_label.text()
    assert "94" not in card.match_label.text()


def test_artwork_arriving_late_redraws_the_stack():
    """Covers are fetched after the card exists; the stack must not stay blank."""
    create_application([])
    card = BundleCard(bundle())
    before = card.stack_label.pixmap().toImage()

    art = QPixmap(120, 180)
    art.fill(QColor("#C64F2A"))
    card.set_cover(1, art)

    assert card.stack_label.pixmap().toImage() != before


def test_the_info_block_is_exactly_two_cells_wide():
    """Two cells and the gap between them - it is a cell in the same flow."""
    create_application([])
    block = BundleInfoBlock(bundle())

    assert block.width() == CARD_WIDTH * 2 + SPACE["lg"]


def test_the_info_block_states_the_spread_as_well_as_the_mean():
    """A mean alone hides that the members disagree."""
    create_application([])
    model = BundleViewModel.from_entries(
        [entry(1, "High", match=94.0), entry(2, "Low", match=61.0)]
    )
    block = BundleInfoBlock(model)

    assert block.value_label.text() == "78"
    assert "61" in block.range_label.text()
    assert "94" in block.range_label.text()


def test_the_rail_carries_the_averaged_contributions():
    create_application([])
    model = bundle()
    block = BundleInfoBlock(model)

    assert block.track.contributions == model.contributions


def test_entries_inside_a_bundle_carry_no_controls_of_their_own():
    """Ten buttons in one panel leave the eye nowhere to rest."""
    create_application([])
    card = RecommendationCard(entry(1, "Inside"))
    card.set_actions_visible(False)

    for button in (
        card.like_button,
        card.dislike_button,
        card.watch_later_button,
        card.details_button,
        card.mal_button,
        card.hide_button,
    ):
        assert not button.isVisible()
