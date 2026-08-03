from __future__ import annotations

from AniRec.gui.genre_analysis_page import (
    NO_EXAMPLES,
    NOT_RATED,
    GenreAnalysisPage,
    genre_stat_view_models,
)
from AniRec.gui_main import create_application
from AniRec.models import GenreStat


def genre_stats():
    return (
        GenreStat(
            "Drama",
            importance_score=40,
            completed_count=12,
            average_user_score=8.25,
            missing_score_count=2,
            example_titles=("Violet Evergarden", "Vinland Saga"),
        ),
        GenreStat(
            "Action",
            importance_score=80,
            completed_count=20,
            average_user_score=7.5,
            missing_score_count=1,
            example_titles=("Attack on Titan",),
        ),
        GenreStat(
            "A genre name that remains readable even when it is unusually long",
            importance_score=40,
            completed_count=3,
            average_user_score=None,
            missing_score_count=3,
            example_titles=(),
        ),
    )


def test_view_models_are_stably_sorted_and_format_partial_data():
    models = genre_stat_view_models(genre_stats())
    assert [model.genre for model in models] == [
        "Action",
        "Drama",
        "A genre name that remains readable even when it is unusually long",
    ]
    assert models[0].importance_text == "80.00"
    assert models[0].average_user_score_text == "7.50 / 10"
    assert models[1].examples_text == "Violet Evergarden · Vinland Saga"
    assert models[2].average_user_score_text == NOT_RATED
    assert models[2].examples_text == NO_EXAMPLES


def test_summary_bars_and_table_use_the_same_sorted_collection_and_exact_values():
    create_application([])
    page = GenreAnalysisPage()
    page.set_genre_stats(genre_stats())

    assert page.metric_values["genres"].text() == "3"
    assert page.metric_values["strongest"].text() == "Action"
    assert page.metric_values["completed"].text() == "35"
    assert page.metric_values["average"].text() == "7.88 / 10"
    assert [bar.value() for _label, bar, _score in page.bar_widgets] == [1000, 500, 500]
    assert [score.text() for _label, _bar, score in page.bar_widgets] == [
        "80.00",
        "40.00",
        "40.00",
    ]
    assert page.table.rowCount() == len(page.models) == 3
    assert [page.table.item(row, 0).text() for row in range(3)] == [
        model.genre for model in page.models
    ]
    assert page.table.item(1, 2).text() == "12"
    assert page.table.item(1, 3).text() == "8.25 / 10"
    assert page.table.item(1, 4).text() == "2"
    assert "Violet Evergarden" in page.table.item(1, 5).text()
    page.close()


def test_empty_and_single_genre_states_are_meaningful_and_resize_safe():
    application = create_application([])
    page = GenreAnalysisPage()
    page.resize(640, 480)
    page.show()
    application.processEvents()
    assert page.empty_label.isVisible()
    assert not page.scroll.isVisible()

    page.set_genre_stats((GenreStat("Fantasy", importance_score=15),))
    application.processEvents()
    assert not page.empty_label.isVisible()
    assert page.scroll.isVisible()
    assert page.metric_values["strongest"].text() == "Fantasy"
    assert page.bar_widgets[0][1].value() == 1000
    assert page.table.rowCount() == 1
    page.resize(1280, 720)
    application.processEvents()
    assert page.scroll.viewport().width() > 0
    page.close()
