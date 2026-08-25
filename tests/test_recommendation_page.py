from __future__ import annotations

from AniRec.gui.recommendation_page import (
    RecommendationExplorerPage,
    RecommendationFilters,
    RecommendationSortMode,
    RecommendationViewMode,
    filter_and_sort_recommendations,
)
from AniRec.gui.recommendation_view_model import recommendation_view_models
from AniRec.gui_main import create_application
from AniRec.models import Anime, Recommendation
from AniRec.services import RecommendationStateService


def recommendations():
    return (
        Recommendation(
            Anime(
                "Alpha",
                mal_id=1,
                genres=("Action",),
                mean_score=8.5,
                status="currently_airing",
                episodes=12,
                year=2024,
                cover_url="https://cdn.example.test/1.jpg",
            ),
            match_score=80,
            rank=1,
        ),
        Recommendation(
            Anime(
                "Beta",
                mal_id=2,
                genres=("Drama",),
                mean_score=None,
                status="finished_airing",
                episodes=24,
                year=None,
                cover_url="https://cdn.example.test/2.jpg",
            ),
            match_score=float("nan"),
            rank=2,
        ),
        Recommendation(
            Anime(
                "Gamma",
                mal_id=3,
                genres=("Action", "Drama"),
                mean_score=9.0,
                status="finished_airing",
                episodes=100,
                year=2020,
                cover_url="https://cdn.example.test/3.jpg",
            ),
            match_score=90,
            rank=3,
        ),
        Recommendation(
            Anime(
                "Delta",
                mal_id=4,
                genres=("Comedy",),
                mean_score=8.5,
                status="currently_airing",
                episodes=None,
                year=2024,
                cover_url="https://cdn.example.test/4.jpg",
            ),
            match_score=80,
            rank=4,
        ),
    )


def titles(models):
    return [model.display_title for model in models]


def test_combined_filters_are_inclusive_and_exclude_missing_numeric_values():
    models = recommendation_view_models(recommendations())
    result = filter_and_sort_recommendations(
        models,
        RecommendationFilters(
            genre="Action",
            minimum_mal_score=8.7,
            status="Finished Airing",
            minimum_episodes=50,
            maximum_episodes=120,
        ),
    )
    assert titles(result) == ["Gamma"]


def test_all_four_sorts_are_stable_and_put_missing_numeric_values_last():
    models = recommendation_view_models(recommendations())

    assert titles(
        filter_and_sort_recommendations(
            models, sort_mode=RecommendationSortMode.PERSONAL_MATCH
        )
    ) == ["Gamma", "Alpha", "Delta", "Beta"]
    assert titles(
        filter_and_sort_recommendations(
            models, sort_mode=RecommendationSortMode.MAL_SCORE
        )
    ) == ["Gamma", "Alpha", "Delta", "Beta"]
    assert titles(
        filter_and_sort_recommendations(models, sort_mode=RecommendationSortMode.YEAR)
    ) == ["Alpha", "Delta", "Gamma", "Beta"]
    assert titles(
        filter_and_sort_recommendations(
            models, sort_mode=RecommendationSortMode.ALPHABETICAL
        )
    ) == ["Alpha", "Beta", "Delta", "Gamma"]


def test_cards_and_table_share_query_and_selection_survives_view_and_filter_changes():
    application = create_application([])
    page = RecommendationExplorerPage()
    page.set_recommendations(recommendations())
    page.select_key("mal:1")

    page.set_view_mode(RecommendationViewMode.TABLE)
    application.processEvents()
    assert page.table.rowCount() == len(page.visible_models) == 4
    assert page.selected_key == "mal:1"
    assert page.table.selectionModel().selectedRows()[0].row() == 1

    action_index = page.genre_filter.findData("Action")
    page.genre_filter.setCurrentIndex(action_index)
    assert titles(page.visible_models) == ["Gamma", "Alpha"]
    assert page.table.rowCount() == 2
    assert page.selected_key == "mal:1"

    page.set_view_mode(RecommendationViewMode.CARDS)
    assert page._cards_by_key["mal:1"].property("selected") is True
    page.close()


def test_empty_filter_result_offers_one_click_clear_and_restores_data():
    create_application([])
    page = RecommendationExplorerPage()
    page.set_recommendations(recommendations())
    page.minimum_episodes_filter.setValue(10_000)

    assert not page.visible_models
    assert page.content_stack.currentIndex() == page.empty_index
    assert page.clear_filters_button.isVisibleTo(page.empty_widget)
    page.clear_filters_button.click()
    assert len(page.visible_models) == 4
    page.close()


def test_cover_requests_are_limited_to_visible_batch_instead_of_whole_collection():
    application = create_application([])
    page = RecommendationExplorerPage()
    many = tuple(
        Recommendation(
            Anime(
                f"Anime {index}",
                mal_id=100 + index,
                cover_url=f"https://cdn.example.test/{index}.jpg",
            ),
            match_score=100 - index,
        )
        for index in range(20)
    )
    page.resize(900, 700)
    page.set_recommendations(many)
    page.show()
    application.processEvents()
    page._request_visible_covers()

    assert 0 < len(page._cover_attempted) <= page.MAX_COVER_REQUESTS_PER_PASS
    assert len(page._cover_attempted) < len(many)
    page.close()


def test_hidden_and_watch_later_actions_persist_by_mal_id_across_title_change_and_restart(
    system_temp_dir,
):
    create_application([])
    service = RecommendationStateService(root_override=system_temp_dir)
    page = RecommendationExplorerPage(state_service=service)
    page.set_profile("profile-a")
    page.set_recommendations(recommendations())
    page.select_key("mal:1")
    page._toggle_watch_later(page.selected_model())
    page._toggle_hidden(page.selected_model())

    assert 1 in service.load("profile-a").watch_later_mal_ids
    assert 1 in service.load("profile-a").hidden_mal_ids
    assert "Alpha" not in titles(page.visible_models)
    page.close()

    reopened = RecommendationExplorerPage(
        state_service=RecommendationStateService(root_override=system_temp_dir)
    )
    reopened.set_profile("profile-a")
    renamed = (
        Recommendation(
            Anime("Renamed Alpha", english_title="Localized Alpha", mal_id=1),
            match_score=80,
        ),
    )
    reopened.set_recommendations(renamed)
    assert not reopened.visible_models
    reopened.set_show_hidden_preference(True)
    assert titles(reopened.visible_models) == ["Localized Alpha"]
    reopened.state_filter.setCurrentIndex(
        reopened.state_filter.findData("watch-later")
    )
    assert titles(reopened.visible_models) == ["Localized Alpha"]
    reopened._toggle_watch_later(reopened.visible_models[0])
    assert not reopened.visible_models
    reopened.close()


def test_profile_switch_isolates_local_state_and_missing_mal_id_disables_actions(
    system_temp_dir,
):
    create_application([])
    service = RecommendationStateService(root_override=system_temp_dir)
    service.set_hidden("profile-a", 1, True)
    page = RecommendationExplorerPage(state_service=service)
    page.set_recommendations(recommendations())
    page.set_profile("profile-a")
    assert "Alpha" not in titles(page.visible_models)

    page.set_profile("profile-b")
    assert "Alpha" in titles(page.visible_models)
    page.set_recommendations((Recommendation(Anime("No MAL identity")),))
    page.select_key("local:0:no mal identity")
    assert not page.hide_selected_button.isEnabled()
    assert not page.watch_later_selected_button.isEnabled()
    page.close()


def test_feedback_moves_cards_between_real_taste_folders_and_updates_live_counts(
    system_temp_dir,
):
    application = create_application([])
    service = RecommendationStateService(root_override=system_temp_dir)
    page = RecommendationExplorerPage(state_service=service)
    page.set_profile("profile-a")
    page.set_recommendations(recommendations())
    changed = []
    page.feedback_changed.connect(changed.append)

    card = page._cards_by_key["mal:1"]
    card.like_button.click()
    application.processEvents()
    assert service.load("profile-a").liked_mal_ids == frozenset((1,))
    assert "1 liked" in page.feedback_summary_label.text()
    assert "Alpha" not in titles(page.visible_models)
    assert page.liked_folder_action.text() == "Liked (1)"
    assert changed

    page.library_tabs["liked"].click()
    application.processEvents()
    assert titles(page.visible_models) == ["Alpha"]
    assert page._cards_by_key["mal:1"].like_button.text() == "Remove like"
    assert page._cards_by_key["mal:1"].dislike_button.text() == "Move to Disliked"
    page._cards_by_key["mal:1"].dislike_button.click()
    application.processEvents()
    state = service.load("profile-a")
    assert state.liked_mal_ids == frozenset()
    assert state.disliked_mal_ids == frozenset((1,))
    assert not page.visible_models
    assert page.liked_folder_action.text() == "Liked (0)"
    assert page.disliked_folder_action.text() == "Disliked (1)"

    page.library_tabs["disliked"].click()
    application.processEvents()
    assert titles(page.visible_models) == ["Alpha"]
    assert page._cards_by_key["mal:1"].like_button.text() == "Move to Liked"
    assert page._cards_by_key["mal:1"].dislike_button.text() == "Remove dislike"
    page._cards_by_key["mal:1"].dislike_button.click()
    page.library_tabs["all"].click()
    application.processEvents()
    assert "Alpha" in titles(page.visible_models)
    assert service.load("profile-a").disliked_mal_ids == frozenset()
    assert page.state_filter.findData("liked") >= 0
    assert page.state_filter.findData("disliked") >= 0
    page.close()


def test_exhausted_recommendations_feed_offers_exact_ten_pick_refill(system_temp_dir):
    application = create_application([])
    page = RecommendationExplorerPage(
        state_service=RecommendationStateService(root_override=system_temp_dir)
    )
    page.set_profile("profile-a")
    page.set_recommendations(recommendations())
    page.set_more_available(True)
    requested = []
    page.refill_requested.connect(lambda: requested.append(10))

    while page.visible_models:
        page._toggle_feedback(page.visible_models[0], "liked")
    application.processEvents()

    assert page.content_stack.currentIndex() == page.empty_index
    assert page.empty_title_label.text() == "You’re all caught up"
    assert "Generate 10 fresh anime" in page.empty_label.text()
    assert page.refill_button.isVisibleTo(page.empty_widget)
    assert page.browse_liked_button.isVisibleTo(page.empty_widget)
    assert page.refill_button.isEnabled()
    page.refill_button.click()
    assert requested == [10]

    page.set_more_running(True)
    assert not page.refill_button.isEnabled()
    page.close()


def test_visible_library_tabs_allow_watch_later_to_be_reviewed_and_removed(
    system_temp_dir,
):
    application = create_application([])
    page = RecommendationExplorerPage(
        state_service=RecommendationStateService(root_override=system_temp_dir)
    )
    page.set_profile("profile-a")
    page.set_recommendations(recommendations())
    page.resize(1280, 720)
    page.show()
    application.processEvents()

    assert set(page.library_tabs) == {"all", "liked", "disliked", "watch-later"}
    assert all(button.isVisibleTo(page) for button in page.library_tabs.values())
    assert not page.selected_actions_frame.isVisibleTo(page)

    page._cards_by_key["mal:1"].watch_later_button.click()
    page.library_tabs["watch-later"].click()
    application.processEvents()
    assert titles(page.visible_models) == ["Alpha"]
    saved_card = page._cards_by_key["mal:1"]
    # Shortened for BUG2: the longer wording clipped at 75% GUI scale.
    assert saved_card.watch_later_button.text() == "Saved"
    assert saved_card.watch_later_button.isChecked()
    saved_card.watch_later_button.click()
    application.processEvents()
    assert not page.visible_models
    assert page.library_tabs["watch-later"].text() == "Watch Later  0"
    page.close()


def test_selected_action_strip_only_appears_for_a_selected_table_row():
    application = create_application([])
    page = RecommendationExplorerPage()
    page.set_recommendations(recommendations())
    page.resize(1280, 720)
    page.show()
    application.processEvents()

    page.select_key("mal:1")
    assert not page.selected_actions_frame.isVisibleTo(page)
    page.set_view_mode(RecommendationViewMode.TABLE)
    application.processEvents()
    assert page.selected_actions_frame.isVisibleTo(page)
    page.set_view_mode(RecommendationViewMode.CARDS)
    application.processEvents()
    assert not page.selected_actions_frame.isVisibleTo(page)
    page.close()


def test_library_tabs_and_view_controls_fit_at_compact_desktop_width():
    application = create_application([])
    page = RecommendationExplorerPage()
    page.set_recommendations(recommendations())
    page.resize(720, 640)
    page.show()
    application.processEvents()

    assert all(button.isVisibleTo(page) for button in page.library_tabs.values())
    assert all(
        button.geometry().right() <= page.library_bar.contentsRect().right()
        for button in page.library_tabs.values()
    )
    assert page.cards_button.geometry().right() <= page.library_bar.contentsRect().right()
    assert page.table_button.geometry().right() <= page.library_bar.contentsRect().right()
    page.close()
