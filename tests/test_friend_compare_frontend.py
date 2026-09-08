from __future__ import annotations

from types import SimpleNamespace

import pytest

from AniRec.gui.compare_page import ComparePage, CompatibilityHeader
from AniRec.gui.compatibility import (
    FriendSummary,
    SampleCompatibilityProvider,
    report_from_payload,
)
from AniRec.gui.discover_filters import (
    ActiveFilter,
    DiscoverFilterState,
    FilterKind,
    ProfileStatus,
)
from AniRec.gui.filter_pills import FilterPillBar
from AniRec.gui.metadata_index import MetadataCatalog
from AniRec.gui.metadata_tags import MetadataTagStrip
from AniRec.gui.scaling import set_gui_scale
from AniRec.gui_main import create_application


def test_filter_state_deduplicates_and_only_queries_ready_profiles():
    state = DiscoverFilterState()
    changes = []
    state.changed.connect(lambda: changes.append(state.query_parameters()))

    state.begin_batch()
    assert state.add_value(FilterKind.GENRE, "Mystery")
    assert not state.add_value(FilterKind.GENRE, "mystery")
    assert state.add_value(
        FilterKind.PROFILE, "Kurisu", status=ProfileStatus.PENDING
    )
    state.end_batch()

    assert len(changes) == 1
    assert state.group_mode
    assert state.query_parameters() == {"genre": ["Mystery"]}

    assert state.update_profile("kurisu", status=ProfileStatus.READY)
    assert state.query_parameters() == {
        "genre": ["Mystery"],
        "profile": ["Kurisu"],
    }


def test_metadata_catalog_ranks_prefixes_by_occurrence_and_honours_exclusions():
    catalog = MetadataCatalog()
    catalog.ingest(
        (
            SimpleNamespace(genres=("Sci-Fi",), studios=("Shaft",)),
            SimpleNamespace(genres=("Science Fiction",), studios=("Shaft",)),
            SimpleNamespace(genres=("Sci-Fi",), studios=("Science SARU",)),
        )
    )

    suggestions = catalog.search("sci")
    assert [(item.kind, item.value) for item in suggestions[:2]] == [
        (FilterKind.GENRE, "Sci-Fi"),
        (FilterKind.GENRE, "Science Fiction"),
    ]

    without_scifi = catalog.search(
        "sci", exclude=((FilterKind.GENRE, "sci-fi"),)
    )
    assert all(item.value != "Sci-Fi" for item in without_scifi)


def test_filter_pills_wrap_and_keep_full_values_accessible():
    application = create_application([])
    bar = FilterPillBar()
    filters = (
        ActiveFilter(FilterKind.GENRE, "Psychological"),
        ActiveFilter(FilterKind.STUDIO, "CoMix Wave Films"),
        ActiveFilter(
            FilterKind.PROFILE,
            "an_extremely_long_sample_username_for_layout",
            status=ProfileStatus.READY,
        ),
    )

    bar.resize(260, 180)
    bar.set_filters(filters)
    bar.show()
    application.processEvents()

    assert bar._rows_layout.count() >= 2
    profile_pill = next(
        pill for pill in bar.pills if pill.filter.kind is FilterKind.PROFILE
    )
    assert profile_pill.value_label.accessibleName() == filters[-1].display_value
    assert filters[-1].display_value in profile_pill.accessibleName()
    assert profile_pill.dismiss_button.accessibleName().startswith(
        "Remove the Profile filter"
    )
    bar.close()


@pytest.mark.parametrize("width", (180, 208, 240))
def test_metadata_overflow_counter_never_overwrites_the_last_tag(width):
    application = create_application([])
    strip = MetadataTagStrip()
    strip.resize(width, 42)
    strip.reserve_height(42)
    strip.set_values(
        (
            (FilterKind.STUDIO, "Shaft"),
            (FilterKind.GENRE, "Award Winning"),
            (FilterKind.GENRE, "Drama"),
            (FilterKind.GENRE, "Mahou Shoujo"),
            (FilterKind.GENRE, "Psychological"),
            (FilterKind.GENRE, "Suspense"),
        )
    )
    strip.show()
    application.processEvents()

    assert strip.overflow is not None
    visible = [tag for tag in (*strip.tags, strip.overflow) if tag.isVisible()]
    for index, tag in enumerate(visible):
        assert tag.x() >= 0
        assert tag.geometry().right() < strip.width()
        for other in visible[index + 1 :]:
            assert not tag.geometry().intersects(other.geometry())
    assert "Suspense" in strip.overflow.hidden
    strip.close()


def test_compatibility_payload_preserves_backend_order_and_difference():
    payload = {
        "friend": {
            "username": "kurisu",
            "match_score": "86",
            "shared_anime": "4",
        },
        "sections": [
            {
                "id": "different",
                "title": "Most different ratings",
                "entries": [
                    {
                        "anime": {
                            "mal_id": 30,
                            "title": "Neon Genesis Evangelion",
                            "genres": ["Drama"],
                            "studios": ["Gainax"],
                            "mean_score": 8.35,
                        },
                        "scores": {
                            "your_score": 9,
                            "friend_score": 3,
                            "difference": -4,
                        },
                    },
                    {"anime": {"title": ""}},
                ],
            },
            {"id": "empty", "title": "Nothing here", "entries": []},
        ],
    }

    report = report_from_payload(payload, is_sample=True)

    assert report.is_sample
    assert report.friend.username == "kurisu"
    assert report.friend.match_score_text == "86%"
    assert [section.section_id for section in report.sections] == [
        "different",
        "empty",
    ]
    assert len(report.sections[0].entries) == 1
    scores = report.sections[0].entries[0].scores
    assert scores.difference == -4
    assert scores.difference_text == "4"
    assert scores.agreement == "opposed"


def test_compare_requires_a_username_inline_and_keeps_focus_on_the_field():
    application = create_application([])
    page = ComparePage()
    page.show()
    application.processEvents()
    requested = []
    page.compare_requested.connect(requested.append)

    page.request("   ")
    application.processEvents()

    assert requested == []
    assert page.input_message.isVisibleTo(page)
    assert page.input_message.text() == "Enter a MyAnimeList username."
    assert page.username_input.accessibleDescription() == page.input_message.text()
    assert page.username_input.hasFocus()
    page.close()


def test_compatibility_header_reelides_a_long_username_after_resize():
    application = create_application([])
    header = CompatibilityHeader()
    username = "an_extremely_long_sample_username_for_layout"
    header.resize(900, 120)
    header.show()
    header.set_summary(FriendSummary(username=username, match_score=51))
    application.processEvents()
    wide_text = header.username_label.text()

    header.resize(420, 120)
    application.processEvents()
    narrow_text = header.username_label.text()

    assert len(narrow_text) <= len(wide_text)
    assert header.username_label.toolTip() == username
    assert header.username_label.accessibleName() == f"Compatibility with {username}"
    header.close()


@pytest.mark.parametrize("scale", (1.0, 1.5))
def test_compare_report_avoids_horizontal_scrolling_at_minimum_content_width(scale):
    application = create_application([])
    set_gui_scale(scale)
    try:
        page = ComparePage()
        page.resize(1000, 650)
        page.show()
        report = SampleCompatibilityProvider().compare(
            "an_extremely_long_sample_username_for_layout"
        )
        page.show_report(report)
        application.processEvents()

        assert page.result_scroll.horizontalScrollBar().maximum() == 0
        assert page.header.width() <= page.result_scroll.viewport().width()
        page.close()
    finally:
        set_gui_scale(1.0)
