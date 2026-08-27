from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QSizePolicy

from AniRec.gui.recommendation_card import (
    COVER_HEIGHT,
    COVER_WIDTH,
    MEMORY_COVER_CACHE,
    RecommendationCard,
    open_mal_url,
)
from AniRec.gui.recommendation_view_model import RecommendationViewModel
from AniRec.gui_main import create_application
from AniRec.models import Anime, Recommendation


def model():
    return RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                "Sousou no Frieren",
                english_title="Frieren: Beyond Journey's End",
                mal_id=52991,
                mean_score=9.1,
                genres=("Adventure", "Drama", "Fantasy"),
                episodes=28,
                status="finished_airing",
                year=2023,
                cover_url="https://cdn.example.test/frieren.jpg",
                mal_url="https://myanimelist.net/anime/52991/Sousou_no_Frieren",
            ),
            match_score=94.2,
            reason="Matches your interest in Fantasy and Drama.",
        )
    )


def png_bytes():
    image = QImage(20, 30, QImage.Format.Format_RGB32)
    image.fill(0xFF6F8CFF)
    array = QByteArray()
    buffer = QBuffer(array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    return bytes(array)


def test_card_preserves_two_by_three_cover_and_reference_text_hierarchy():
    create_application([])
    card = RecommendationCard(model())

    assert card.cover_label.width() == COVER_WIDTH
    assert card.cover_label.height() == COVER_HEIGHT
    assert COVER_WIDTH * 3 == COVER_HEIGHT * 2
    assert card.title_label.text() == "Frieren: Beyond Journey's End"
    assert card.secondary_title_label.text() == "Sousou no Frieren"
    assert card.match_label.text() == "Personal match: 94.2%"
    assert card.mal_score_label.text() == "MAL score: 9.10 / 10"
    assert "2023 · Finished Airing · 28 episodes" == card.meta_label.text()
    assert card.focusPolicy().name == "StrongFocus"


def test_the_review_decision_sits_above_the_supporting_detail():
    """Like and Not for me must precede the metadata in the card.

    A 2:3 poster plus six buttons does not fit the default window, so the
    ordering decides what falls below the fold. Reviewing a pick is the core
    loop, so the two feedback actions belong directly under the title, and the
    detail a user reads only when undecided belongs beneath them.

    Asserted against the layout rather than against pixel positions: geometry
    depends on whether the widget has been realised and on the font metrics of
    whichever Qt platform is in use, which made an earlier version of this test
    pass alone and fail inside the full suite.
    """
    create_application([])
    card = RecommendationCard(model())
    layout = card.layout()

    def row_of(widget):
        for index in range(layout.count()):
            item = layout.itemAt(index)
            if item.widget() is widget:
                return index
            child = item.layout()
            if child is not None:
                for inner in range(child.count()):
                    if child.itemAt(inner).widget() is widget:
                        return index
        raise AssertionError(f"{widget} is not in the card layout")

    assert card.sizePolicy().verticalPolicy() is QSizePolicy.Policy.Maximum
    assert row_of(card.title_label) < row_of(card.like_button)
    assert row_of(card.like_button) == row_of(card.dislike_button)
    for later in (card.mal_score_label, card.meta_label, card.reason_label,
                  card.details_button, card.watch_later_button):
        assert row_of(card.like_button) < row_of(later)


def test_card_requests_cover_lazily_and_uses_placeholder_for_corrupt_bytes():
    create_application([])
    card = RecommendationCard(model())
    requested = []
    card.cover_requested.connect(requested.append)
    assert not card.cover_label.pixmap().isNull()

    card.request_cover()
    assert requested == ["https://cdn.example.test/frieren.jpg"]
    assert not card.set_cover_data(b"not-an-image")
    assert not card.cover_label.pixmap().isNull()
    assert card.set_cover_data(png_bytes())


def test_mal_button_opens_only_safe_numeric_anime_https_url():
    create_application([])
    opened = []
    card = RecommendationCard(model(), mal_opener=lambda url: not opened.append(url.toString()))
    card.mal_button.click()
    assert opened == ["https://myanimelist.net/anime/52991/Sousou_no_Frieren"]

    assert not open_mal_url("http://myanimelist.net/anime/1", opener=lambda _url: True)
    assert not open_mal_url("https://example.test/anime/1", opener=lambda _url: True)
    assert not open_mal_url("https://myanimelist.net/anime/not-a-number", opener=lambda _url: True)
    assert open_mal_url(
        "https://myanimelist.net/anime/1/Fixture",
        opener=lambda url: isinstance(url, QUrl),
    )


def large_png_bytes(width=450, height=700):
    """A poster far bigger than the frame, with detail on the top edge."""
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(0xFF3A1C18)
    for y in range(height // 10):
        for x in range(width):
            image.setPixel(x, y, 0xFFD9A441)
    array = QByteArray()
    buffer = QBuffer(array)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    assert image.save(buffer, "PNG")
    buffer.close()
    return bytes(array.data())


def test_a_cached_cover_is_fitted_to_the_frame_not_cropped_by_it():
    """Addresses: the covers that came back cropped after a scroll.

    The memory cache holds the original at full resolution on purpose, so a
    GUI scale change can re-fit from it instead of enlarging a shrunken copy.
    ``request_cover`` used to hand that original straight to the cover label,
    which is a fixed 132x198 with no scaledContents - so Qt drew a 450x700
    image at full size and clipped it to the label. A centre crop: the top of
    the title lockup and both side edges were gone, the rounded corners with
    them, and ``_source_cover`` was never set so a later rescale fell back to
    the placeholder.

    It only showed once a cover had been cached, which is why it looked like
    an intermittent fault rather than a fitting bug.
    """
    create_application([])
    MEMORY_COVER_CACHE.clear()

    first = RecommendationCard(model())
    assert first.set_cover_data(large_png_bytes())
    fitted = first.cover_label.pixmap()

    # A second card for the same title takes the cached path.
    second = RecommendationCard(model())
    second.request_cover()
    cached = second.cover_label.pixmap()

    assert not cached.isNull()
    assert (cached.width(), cached.height()) == (fitted.width(), fitted.height())
    assert cached.width() == second.cover_label.width()
    assert cached.height() == second.cover_label.height()

    # The top band survives across the full width: nothing was cropped off it.
    image = cached.toImage()
    band = [
        image.pixelColor(x, 2)
        for x in range(4, cached.width() - 4, 4)
    ]
    assert band, "no samples taken"
    assert all(
        pixel.red() > 150 and pixel.green() > 110 and pixel.blue() < 120
        for pixel in band
    ), "the top of the artwork was cut away"

    # And the original is kept, so a scale change can re-fit from it.
    assert second._source_cover is not None
    assert second._source_cover.width() == 450
    MEMORY_COVER_CACHE.clear()
