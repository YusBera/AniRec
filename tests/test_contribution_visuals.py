from __future__ import annotations

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from AniRec.gui.contribution_visuals import (
    ContributionKind,
    classify_contribution,
    contribution_colour,
    proportional_segment_widths,
    semantic_contributions,
    snapped_segment_edges,
)
from AniRec.gui.instrument_widgets import ScoreTrack
from AniRec.gui.match_badge import (
    PLATE_PADDING,
    RAIL_BOTTOM_GAP,
    RAIL_HEIGHT,
    MatchBadge,
)
from AniRec.gui.recommendation_page import _badge_colours
from AniRec.gui_main import create_application


def test_contributors_follow_the_same_genre_and_studio_semantics_as_tags():
    context = {"genres": ("Drama", "Suspense"), "studios": ("Shaft",)}

    assert classify_contribution("Drama", **context) is ContributionKind.GENRE
    assert classify_contribution("genre:Suspense", **context) is ContributionKind.GENRE
    assert classify_contribution("Shaft", **context) is ContributionKind.STUDIO
    assert classify_contribution("studio:Shaft", **context) is ContributionKind.STUDIO
    assert classify_contribution("Community score", **context) is ContributionKind.COMMUNITY


def test_repeated_categories_are_distinguishable_without_leaving_their_family():
    items = semantic_contributions(
        (("Drama", 20), ("Suspense", 15), ("Shaft", 12)),
        genres=("Drama", "Suspense"),
        studios=("Shaft",),
    )
    genre = QColor("#6FC6C0")
    studio = QColor("#C6A15B")
    neutral = QColor("#7C8C80")
    colours = [
        contribution_colour(
            item,
            genre=genre,
            studio=studio,
            community=neutral,
            other=neutral,
        )
        for item in items
    ]

    # Two genres must be told apart, and both must still read as genres
    # rather than as the studio. The previous form of this test required the
    # two genre hues to be within 2 degrees, which is what made three genres
    # on one card come out at an identical hue and saturation - separated only
    # by lightness, so the rail read as one region with faint steps in it.
    # The invariant that actually matters is the grouping, so that is what is
    # asserted, and more strictly than before: the gap to the studio must
    # exceed the whole spread of the genre family.
    assert colours[0].name() != colours[1].name()
    genre_spread = abs(colours[0].hue() - colours[1].hue())
    assert 8 <= genre_spread <= 80, "genres must differ, without leaving the family"
    to_studio = min(
        abs(colours[index].hue() - colours[2].hue()) for index in (0, 1)
    )
    assert to_studio > genre_spread
    assert to_studio > 60


def test_both_score_rails_publish_the_same_non_colour_explanation():
    create_application([])
    contributions = (("Drama", 20), ("Shaft", 12))
    context = {"genres": ("Drama",), "studios": ("Shaft",)}

    badge = MatchBadge(32)
    badge.set_contributions(contributions, **context)
    track = ScoreTrack()
    track.set_data(contributions, 32, **context)

    assert "Genre: Drama" in badge.accessibleDescription()
    assert "Studio: Shaft" in badge.accessibleDescription()
    assert track.accessibleDescription() == badge.accessibleDescription()


def test_raw_contributors_fill_the_displayed_score_length_proportionally():
    items = semantic_contributions(
        (("Drama", 12), ("Shaft", 8)),
        genres=("Drama",),
        studios=("Shaft",),
    )

    widths = proportional_segment_widths(items, 63.0)

    assert sum(widths) == pytest.approx(63.0)
    assert widths == pytest.approx((37.8, 25.2))


def test_fractional_segments_share_one_integer_pixel_boundary():
    edges = snapped_segment_edges((12.4, 3.2, 18.7), start=7.5)

    assert edges == (8, 20, 23, 42)
    assert all(isinstance(edge, int) for edge in edges)


def test_live_badge_palette_uses_readable_text_not_dark_accent_ink():
    create_application([])
    application = QApplication.instance()
    assert application is not None
    names = (
        "resolvedAccent",
        "resolvedAccentContrast",
        "resolvedBackground",
        "resolvedSignal",
        "resolvedText",
    )
    previous = {name: application.property(name) for name in names}
    try:
        application.setProperty("resolvedAccent", "#D9A441")
        application.setProperty("resolvedAccentContrast", "#0A0F0B")
        application.setProperty("resolvedBackground", "#070C09")
        application.setProperty("resolvedSignal", "#5FBFB5")
        application.setProperty("resolvedText", "#C6D4C2")

        track, _accent, neutral, _genre = _badge_colours()

        assert neutral.name() == "#c6d4c2"
        assert neutral.lightness() > track.lightness()
        assert neutral.name() != "#0a0f0b"

        # Exercise the same palette handoff and real contributor mix that
        # exposed the bug. The large community section around 55% must look
        # filled, not like the empty range beyond the 63% marker.
        badge = MatchBadge(63)
        badge.setFixedWidth(208)
        badge.set_colours(track, _accent, neutral, _genre)
        badge.set_contributions(
            (
                ("Samurai", 8.28),
                ("Studio Deen", 3.84),
                ("Historical", 1.68),
                ("Other tags", 1.09),
                ("Community rating", 24.43),
            ),
            genres=("Historical", "Samurai"),
            studios=("Studio Deen",),
        )
        badge.show()
        application.processEvents()
        image = badge.grab().toImage()
        rail_width = badge.width() - PLATE_PADDING * 2
        rail_mid_y = round(
            badge.height() - 0.5 - RAIL_BOTTOM_GAP - RAIL_HEIGHT / 2
        )
        community = QColor(
            image.pixel(round(PLATE_PADDING + rail_width * 0.55), rail_mid_y)
        )
        empty = QColor(
            image.pixel(round(PLATE_PADDING + rail_width * 0.85), rail_mid_y)
        )
        assert community.lightness() > empty.lightness() + 40
    finally:
        for name, value in previous.items():
            application.setProperty(name, value)
