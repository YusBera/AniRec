from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QUrl
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QSizePolicy

from AniRec.gui.recommendation_card import (
    COVER_HEIGHT,
    COVER_WIDTH,
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


def test_card_actions_follow_content_without_viewport_sized_vertical_gap():
    application = create_application([])
    card = RecommendationCard(model())
    card.show()
    application.processEvents()

    content_bottom = card.reason_label.geometry().bottom()
    action_top = card.like_button.geometry().top()
    assert card.sizePolicy().verticalPolicy() is QSizePolicy.Policy.Maximum
    assert 0 <= action_top - content_bottom <= 24
    card.close()


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
