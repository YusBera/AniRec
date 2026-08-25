"""The card grid must actually be a grid, and artwork must be rounded.

Addresses: BUG7.

Two separate faults produced one complaint. Cards sized themselves to their
own content, so a wrapped title or a fourth genre made one card taller than
its neighbours and left ragged gaps in the row. And a stylesheet
``border-radius`` does not clip a QLabel's pixmap, so every portrait stayed a
hard rectangle inside a rounded card, which is invisible on muted art and
obvious on a saturated one.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap

from AniRec.gui.cover_art import rounded_cover
from AniRec.gui.recommendation_page import (
    RecommendationExplorerPage,
    RecommendationViewMode,
)
from AniRec.gui_main import create_application
from AniRec.models import Anime, Recommendation
from AniRec.services import RecommendationStateService


# Deliberately uneven: a long title that wraps, a four-genre list that wraps,
# and an entry with no English title at all. Every one of these used to change
# a card's height.
CASES = (
    ("Cowboy Bebop", "Cowboy Bebop", ("Action", "Sci-Fi", "Drama")),
    (
        "Mushishi Zoku Shou: The Shadow that Devours the Sun",
        "Mushi-shi The Next Passage",
        ("Adventure", "Mystery", "Slice of Life", "Supernatural"),
    ),
    ("K-On!", None, ("Comedy",)),
)


def _recommendations():
    return tuple(
        Recommendation(
            Anime(
                title,
                mal_id=index,
                english_title=english,
                genres=genres,
                mean_score=8.0,
                status="finished_airing",
                episodes=12,
                year=2010,
                cover_url=f"https://cdn.example.test/{index}.jpg",
            ),
            match_score=90 - index * 10,
            rank=index,
        )
        for index, (title, english, genres) in enumerate(CASES, start=1)
    )


def _page(system_temp_dir, application):
    page = RecommendationExplorerPage(
        state_service=RecommendationStateService(root_override=system_temp_dir)
    )
    page.set_profile("profile-a")
    page.set_view_mode(RecommendationViewMode.CARDS)
    page.set_recommendations(_recommendations())
    page.resize(1200, 1100)
    page.show()
    for _ in range(4):
        application.processEvents()
    return page


def test_every_card_in_the_grid_has_the_same_height(system_temp_dir):
    application = create_application([])
    page = _page(system_temp_dir, application)

    heights = {card.height() for card in page._cards_by_key.values()}

    assert len(heights) == 1, (
        f"cards disagree on height: {sorted(heights)}. A QGridLayout row is as "
        "tall as its tallest card, so the shorter ones leave a ragged gap."
    )
    page.close()


def test_each_row_sits_at_the_same_place_in_every_card(system_temp_dir):
    """Equal outer heights are not enough: the contents must line up too."""
    application = create_application([])
    page = _page(system_temp_dir, application)
    cards = list(page._cards_by_key.values())

    ragged = {}
    for name in (
        "cover_label",
        "match_label",
        "title_label",
        "secondary_title_label",
        "like_button",
        "mal_score_label",
        "details_button",
        "mal_button",
    ):
        offsets = {
            getattr(card, name).mapTo(card, getattr(card, name).rect().topLeft()).y()
            for card in cards
        }
        if len(offsets) != 1:
            ragged[name] = sorted(offsets)

    assert not ragged, f"these rows sit at different heights per card: {ragged}"
    page.close()


def test_the_grid_stays_aligned_after_a_gui_scale_change(system_temp_dir):
    """Cards are reused, so a scale change re-applies sizes in place."""
    application = create_application([])
    page = _page(system_temp_dir, application)

    from AniRec.gui.scaling import set_gui_scale

    for target in (1.5, 0.75, 1.0):
        set_gui_scale(target)
        page.rebuild_for_scale()
        for _ in range(4):
            application.processEvents()
        heights = {card.height() for card in page._cards_by_key.values()}
        assert len(heights) == 1, f"ragged at scale {target}: {sorted(heights)}"

    set_gui_scale(1.0)
    page.close()


def test_cover_artwork_is_clipped_to_rounded_corners():
    """A stylesheet radius cannot do this; the image itself must be clipped."""
    create_application([])
    source = QPixmap(120, 180)
    source.fill(Qt.GlobalColor.red)

    result = rounded_cover(source, 120, 180, 16)
    image = result.toImage()

    assert image.pixelColor(0, 0).alpha() == 0, "top-left corner is not rounded"
    assert image.pixelColor(119, 0).alpha() == 0, "top-right corner is not rounded"
    assert image.pixelColor(0, 179).alpha() == 0, "bottom-left corner is not rounded"
    assert image.pixelColor(119, 179).alpha() == 0, "bottom-right corner is not rounded"
    assert image.pixelColor(60, 90).alpha() == 255, "the middle should be opaque"


def test_cover_artwork_fills_the_frame_without_distortion():
    """A wide source is centre-cropped, never squashed to fit."""
    create_application([])
    source = QPixmap(400, 100)
    source.fill(Qt.GlobalColor.blue)

    result = rounded_cover(source, 120, 180, 16)

    assert result.width() == 120
    assert result.height() == 180
    assert result.toImage().pixelColor(60, 90).alpha() == 255
