from __future__ import annotations

from PySide6.QtCore import QBuffer, QByteArray, QIODevice
from PySide6.QtGui import QImage

from AniRec.gui.recommendation_detail_dialog import (
    DETAIL_COVER_HEIGHT,
    DETAIL_COVER_WIDTH,
    NO_GENRE_CONTRIBUTIONS,
    RecommendationDetailDialog,
)
from AniRec.gui.recommendation_page import RecommendationExplorerPage
from AniRec.gui.recommendation_view_model import RecommendationViewModel
from AniRec.gui_main import create_application
from AniRec.models import Anime, Recommendation


def full_model():
    return RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                "Sousou no Frieren",
                english_title="Frieren: Beyond Journey's End",
                alternative_titles=("Frieren at the Funeral", "葬送のフリーレン"),
                mal_id=52991,
                genres=("Adventure", "Drama", "Fantasy"),
                mean_score=9.1,
                episodes=28,
                status="finished_airing",
                year=2023,
                start_date="2023-09-29",
                end_date="2024-03-22",
                synopsis="An elf mage retraces a meaningful journey.",
                mal_url="https://myanimelist.net/anime/52991/Sousou_no_Frieren",
            ),
            match_score=94.2,
            reason="Matches your interest in Fantasy and Drama.",
            genre_contributions=(("Fantasy", 52.25), ("Drama", 21.5)),
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


def test_detail_dialog_renders_all_metadata_reason_and_scored_contributions():
    create_application([])
    dialog = RecommendationDetailDialog()
    dialog.set_model(full_model())

    assert dialog.title_label.text() == "Frieren: Beyond Journey's End"
    assert dialog.secondary_title_label.text() == "Sousou no Frieren"
    assert "Frieren at the Funeral" in dialog.alternative_titles_label.text()
    assert dialog.personal_match_label.text() == "Personal match: 94.2%"
    assert dialog.mal_score_label.text() == "MAL score: 9.10 / 10"
    assert dialog.episodes_label.text() == "Episodes: 28 episodes"
    assert dialog.status_label.text() == "Status: Finished Airing"
    assert dialog.year_label.text() == "Airing year: 2023"
    assert dialog.dates_label.text() == "Aired: 2023-09-29 to 2024-03-22"
    assert dialog.synopsis_label.text().startswith("An elf mage")
    assert dialog.reason_label.text().startswith("Matches your interest")
    assert dialog.contributions_label.text() == "Fantasy: +52.25\nDrama: +21.50"
    assert dialog.score_track.contributions == (
        ("Fantasy", 52.25),
        ("Drama", 21.5),
    )
    assert dialog.sum_total_label.text() == "73.75  →  94.2%"
    assert dialog.synopsis_label.isHidden()
    assert dialog.scroll.widgetResizable()
    dialog.close()


def test_detail_dialog_fallbacks_never_show_raw_none_nan_or_collections():
    create_application([])
    dialog = RecommendationDetailDialog()
    dialog.set_model(RecommendationViewModel.from_recommendation(Recommendation(Anime("Fixture"))))
    rendered = " ".join(
        widget.text()
        for widget in (
            dialog.alternative_titles_label,
            dialog.personal_match_label,
            dialog.mal_score_label,
            dialog.genres_label,
            dialog.episodes_label,
            dialog.status_label,
            dialog.year_label,
            dialog.dates_label,
            dialog.synopsis_label,
            dialog.reason_label,
            dialog.contributions_label,
        )
    )

    # CHANGE [NO-NULL-PROSE]: a title with no alternative names hides the
    # row rather than spending the line under the heading saying so.
    assert dialog.alternative_titles_label.text() == ""
    assert not dialog.alternative_titles_label.isVisible()
    assert dialog.dates_label.text() == ""
    assert not dialog.dates_label.isVisible()
    assert dialog.contributions_label.text() == NO_GENRE_CONTRIBUTIONS
    assert "None" not in rendered
    assert "nan" not in rendered.casefold()
    assert "[]" not in rendered
    assert not dialog.mal_button.isEnabled()
    dialog.close()


def test_large_cover_keeps_two_by_three_ratio_and_corrupt_data_uses_placeholder():
    create_application([])
    dialog = RecommendationDetailDialog()
    assert dialog.cover_label.width() == DETAIL_COVER_WIDTH
    assert dialog.cover_label.height() == DETAIL_COVER_HEIGHT
    assert DETAIL_COVER_WIDTH * 3 == DETAIL_COVER_HEIGHT * 2
    assert not dialog.cover_label.pixmap().isNull()
    assert not dialog.set_cover_data(b"corrupt")
    assert not dialog.cover_label.pixmap().isNull()
    assert dialog.set_cover_data(png_bytes())
    dialog.close()


def test_mal_action_uses_the_same_validated_url_boundary_as_cards():
    create_application([])
    opened = []
    dialog = RecommendationDetailDialog(
        mal_opener=lambda url: not opened.append(url.toString())
    )
    dialog.set_model(full_model())
    dialog.mal_button.click()
    assert opened == ["https://myanimelist.net/anime/52991/Sousou_no_Frieren"]
    dialog.close()


def test_explorer_reuses_one_owned_dialog_across_repeated_open_close_cycles():
    application = create_application([])
    page = RecommendationExplorerPage()
    page.set_recommendations((Recommendation(Anime("First", mal_id=1)), Recommendation(Anime("Second", mal_id=2))))
    first_model, second_model = page.visible_models

    page._open_details(first_model)
    first_dialog = page.detail_dialog
    assert first_dialog is not None and first_dialog.isVisible()
    first_dialog.close()
    application.processEvents()
    page._open_details(second_model)

    assert page.detail_dialog is first_dialog
    assert page.detail_dialog.model is second_model
    assert page.detail_dialog.title_label.text() == "Second"
    assert page.detail_dialog.navigation_label.text() == "02 / 02"
    page.detail_dialog.next_requested.emit()
    assert page.detail_dialog.model is first_model
    assert page.detail_dialog.navigation_label.text() == "01 / 02"
    page.close()
