"""The Profile surface: what it parses, what it draws, and what it refuses to.

The through-line of these tests is the same boundary the module docstrings
argue for. The interface must render a prepared profile faithfully, must fail
one section at a time, and must never invent a figure - so the provider that
ships wired up is checked for refusing, and the sample is checked for being
stamped.
"""

from __future__ import annotations

import pytest

from AniRec.gui.compatibility import UnavailableReason
from AniRec.gui.main_window import MainWindow, PAGE_DEFINITIONS, PageId
from AniRec.gui.profile_page import ProfilePage, VerdictRow
from AniRec.gui.taste_profile import (
    RatingBucket,
    RatingDistribution,
    SampleTasteProfileProvider,
    TasteProfileUnavailable,
    UnavailableTasteProfileProvider,
    profile_from_payload,
)
from AniRec.gui.texts import PROFILE_TEXT
from AniRec.gui_main import create_application


@pytest.fixture(scope="module")
def application():
    return create_application([])


@pytest.fixture(scope="module")
def sample_profile(application):
    return SampleTasteProfileProvider().taste_profile()


# ---------------------------------------------------------------------------
# The data layer
# ---------------------------------------------------------------------------


def test_the_provider_that_ships_refuses_with_a_reason():
    """Nothing about this surface pretends to have data it does not have."""
    provider = UnavailableTasteProfileProvider()

    with pytest.raises(TasteProfileUnavailable) as raised:
        provider.taste_profile()

    assert raised.value.reason is UnavailableReason.BACKEND_MISSING


def test_the_sample_is_parsed_whole_and_stamped_as_a_sample(sample_profile):
    assert sample_profile.is_sample
    assert sample_profile.identity.username
    assert sample_profile.fingerprint
    assert sample_profile.rating_distribution
    assert sample_profile.hot_takes.higher and sample_profile.hot_takes.lower
    assert sample_profile.hype_killers.biggest is not None
    assert sample_profile.hidden_gems.deepest is not None
    assert sample_profile.genres.readings
    assert sample_profile.studios.most_watched is not None
    assert sample_profile.eras.buckets and sample_profile.eras.seasons
    assert sample_profile.habits.readings
    assert len(sample_profile.timeline.points) > 1


def test_summary_statistics_are_read_off_the_histogram_they_sit_under():
    """The four derived figures must agree with the bars, by construction."""
    distribution = RatingDistribution(
        buckets=(
            RatingBucket(10, 2),
            RatingBucket(9, 4),
            RatingBucket(8, 4),
            RatingBucket(7, 0),
        )
    )

    assert distribution.total == 10
    assert distribution.peak == 4
    assert distribution.mean == pytest.approx(8.8)
    assert distribution.median == 9
    # A tie between two counts is broken toward the higher score, so the mode
    # never silently reports the lower of two equally common opinions.
    assert distribution.mode == 9
    assert distribution.scale_usage == (3, 4)
    assert distribution.scale_usage_text == "3 / 4"


def test_an_unrated_reader_reports_nothing_rather_than_zero():
    """"Not measured" and "measured zero" must not format the same."""
    distribution = RatingDistribution(buckets=(RatingBucket(8, 0),))

    assert not distribution
    assert distribution.mean_text == "N/A"
    assert distribution.median_text == "N/A"
    assert distribution.mode_text == "N/A"


def test_a_malformed_payload_loses_one_section_and_not_the_page():
    """A boundary is tolerant about shape and strict about identity."""
    profile = profile_from_payload(
        {
            "identity": {"username": "reader", "completed": "not a number"},
            "genres": "this should have been an object",
            "rating_distribution": {"buckets": [{"score": 9, "count": 3}]},
            "hot_takes": {"higher": [{"mal_id": 1}]},
        }
    )

    assert profile.identity.username == "reader"
    assert profile.identity.completed is None
    assert not profile.genres.readings
    assert profile.rating_distribution.total == 3
    # An entry with no title is dropped rather than drawn as a row about
    # nothing.
    assert profile.hot_takes.higher == ()


def test_the_direction_of_a_disagreement_is_a_word_not_only_a_colour(
    sample_profile,
):
    lower = sample_profile.hot_takes.lower[0]
    higher = sample_profile.hot_takes.higher[0]

    assert lower.direction == "below"
    assert lower.delta_text.startswith("-")
    assert higher.direction == "above"
    assert higher.delta_text.startswith("+")


def test_initials_fall_back_without_borrowing_punctuation():
    profile = profile_from_payload({"identity": {"username": "yuu_r"}})

    assert profile.identity.initials == "YR"


def test_profile_channel_uses_the_bundled_latin_interface_alphabet():
    """The profile legend must not depend on decorative CJK font coverage."""
    assert PROFILE_TEXT.channel == "PROFILE // TASTE READOUT"
    assert PROFILE_TEXT.channel.isascii()


# ---------------------------------------------------------------------------
# The surface
# ---------------------------------------------------------------------------


@pytest.fixture
def page(application, sample_profile):
    page = ProfilePage()
    page.resize(1200, 900)
    page.show_profile(sample_profile)
    application.processEvents()
    yield page
    page.deleteLater()


def test_every_section_of_the_sample_renders_its_content(page):
    assert page.is_showing_profile
    for section_id, section in page.sections.items():
        assert section.stack.currentWidget() is section.body, section_id


def test_fingerprint_modules_share_one_frame_height_after_reflow(
    page, application
):
    assert len({module.height() for module in page.fingerprint.widgets}) == 1

    page.resize(760, 760)
    application.processEvents()

    assert len({module.height() for module in page.fingerprint.widgets}) == 1


def test_the_header_carries_the_counts_and_the_sample_stamp(page, sample_profile):
    assert page.header.stats["completed"].value_label.text() == "312"
    assert page.header.stats["episodes"].value_label.text() == "4,829"
    assert page.header.stats["mean"].value_label.text() == "7.42"
    assert sample_profile.is_sample
    assert page.header.sample_stamp.isVisibleTo(page.header)


def test_the_histogram_draws_one_rail_per_score_with_its_count_beside_it(page):
    assert len(page.histogram.rails) == 10
    # The tallest bar is full length and nothing exceeds it.
    fractions = [rail._fraction for rail in page.histogram.rails]
    assert max(fractions) == pytest.approx(1.0)
    assert all(0.0 <= fraction <= 1.0 for fraction in fractions)
    assert page.histogram.summary_readouts["mode"].value_label.text() == "8"


def test_a_section_with_no_data_reads_as_absent_rather_than_broken(
    application, sample_profile
):
    """An absence and a fault must not look the same."""
    from dataclasses import replace

    from AniRec.gui.taste_profile import GenreDNA

    page = ProfilePage()
    page.show_profile(replace(sample_profile, genres=GenreDNA()))
    application.processEvents()

    section = page.sections["genres"]
    assert section.stack.currentWidget() is section.empty_panel
    # And the rest of the page is untouched by it.
    assert page.sections["distribution"].stack.currentWidget() is (
        page.sections["distribution"].body
    )
    page.deleteLater()


def test_a_section_that_cannot_be_drawn_offers_a_retry_and_spares_the_others(
    application, sample_profile
):
    page = ProfilePage()
    page.show_profile(sample_profile)
    application.processEvents()

    section = page.sections["eras"]
    section.show_error()

    assert section.stack.currentWidget() is section.error_panel
    assert section.retry_button.isEnabled()
    assert page.sections["habits"].stack.currentWidget() is page.sections["habits"].body
    page.deleteLater()


def test_selecting_a_genre_marks_the_row_and_lists_its_titles(page, application):
    rows = page.genres.rows
    assert rows
    # The first genre is selected on arrival, so the drill-down is never empty
    # for a reader who has not clicked anything.
    assert rows[0].property("selected")

    target = rows[2]
    target.selected.emit(target.reading.name)
    application.processEvents()

    assert target.property("selected")
    assert not rows[0].property("selected")
    from PySide6.QtWidgets import QLabel

    listed = [label.text() for label in page.genres.drill.findChildren(QLabel)]
    assert any(target.reading.name.upper() in text for text in listed)
    for entry in target.reading.titles:
        assert entry.title in listed


def test_genre_summary_uses_equal_columns_even_with_a_long_legend(
    page, application
):
    blocks = page.genres.verdict_blocks
    assert len(blocks) == 3

    for width in (1200, 760):
        page.resize(width, 760)
        application.processEvents()
        widths = [block.width() for block in blocks]
        assert max(widths) - min(widths) <= 1


def test_a_genre_row_is_reachable_and_activated_from_the_keyboard(page, application):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    row = page.genres.rows[1]
    seen: list[str] = []
    row.selected.connect(seen.append)

    row.keyPressEvent(
        QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    )

    assert seen == [row.reading.name]
    assert row.focusPolicy() & Qt.FocusPolicy.TabFocus


def test_every_figure_on_a_verdict_row_is_named_for_a_screen_reader(page):
    """Whatever figures a row draws, it says them.

    CHANGE [RECEIPTS]: this used to assert the word "community" on every row,
    which held only while every row was a comparison between two opinions.
    The rewatch receipt is a title and a count, so it announces a count - the
    property worth pinning is that the spoken version matches the drawn one,
    not that one particular word is always present.
    """
    rows = page.findChildren(VerdictRow)
    assert rows
    for row in rows:
        name = row.accessibleName()
        assert row.verdict.title in name
        # Values, not captions: a comparison row abbreviates to "MAL" in the
        # column and says "community" aloud, which is right in both places.
        # What must never differ is the figure itself.
        for _caption, value, _tone in row.figures:
            assert value in name, (value, name)


def test_genre_rows_and_bars_never_claim_more_than_the_widest_genre(page):
    fractions = [row.rail._fraction for row in page.genres.rows]
    assert max(fractions) == pytest.approx(1.0)
    assert all(fraction <= 1.0 for fraction in fractions)


def test_the_page_refuses_honestly_before_it_has_a_provider(application):
    page = ProfilePage()

    page.show_unavailable(
        TasteProfileUnavailable(UnavailableReason.BACKEND_MISSING), offer_sample=True
    )

    assert not page.is_showing_profile
    assert page.state_panel.secondary_button.isVisibleTo(page.state_panel)
    assert page.state_panel.secondary_button.text()
    page.deleteLater()


def test_a_network_failure_offers_a_retry_and_a_private_list_does_not(application):
    page = ProfilePage()

    page.show_unavailable(TasteProfileUnavailable(UnavailableReason.NETWORK))
    assert page.state_panel.retry_button.text()
    network_retry = page.state_panel.retry_button.isVisibleTo(page.state_panel)

    page.show_unavailable(TasteProfileUnavailable(UnavailableReason.PRIVATE_LIST))
    private_retry = page.state_panel.retry_button.isVisibleTo(page.state_panel)

    assert network_retry and not private_retry
    page.deleteLater()


# ---------------------------------------------------------------------------
# The shell
# ---------------------------------------------------------------------------


def test_profile_is_a_destination_between_the_library_and_the_comparison():
    order = [definition.page_id for definition in PAGE_DEFINITIONS]

    assert order.index(PageId.LIBRARY) < order.index(PageId.PROFILE)
    assert order.index(PageId.PROFILE) < order.index(PageId.COMPARE)


def test_the_shell_wires_the_sample_but_ships_the_refusing_provider(application):
    window = MainWindow()

    with pytest.raises(TasteProfileUnavailable):
        window.taste_profile_provider.taste_profile()

    window.profile_page.sample_requested.emit()
    application.processEvents()

    assert window.profile_page.is_showing_profile
    assert window.profile_page.header.sample_stamp.isVisibleTo(
        window.profile_page.header
    )
    window.close()


def test_a_genre_pressed_on_the_profile_filters_discover_and_goes_there(application):
    from AniRec.gui.discover_filters import FilterKind

    window = MainWindow()
    window.profile_page.metadata_filter_requested.emit(FilterKind.GENRE, "Psychological")
    application.processEvents()

    assert window.current_page_id is PageId.DISCOVER
    assert window.recommendations_page.filter_state.query_parameters() == {
        "genre": ["Psychological"]
    }
    window.close()
