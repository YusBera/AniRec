"""The Profile surface's opening statement, and the facts behind it.

The page now leads with a claim about the reader rather than with five equal
readings. That claim is derived, so it needs the same treatment as any other
derived figure on this page: it has to be right, it has to be stable, and it
has to decline to say anything when there is nothing to say.
"""

from __future__ import annotations

import pathlib

from AniRec.gui.profile_page import ProfilePage, unlisted_facts, unlisted_sentences
from AniRec.presentation.taste_profile import (
    EraBucket,
    EraPreferences,
    FingerprintReading,
    GenreDNA,
    GenreVerdict,
    HiddenGems,
    HotTakes,
    HypeKillers,
    RewatchNote,
    SampleTasteProfileProvider,
    StudioDNA,
    StudioReading,
    TasteProfile,
    TitleVerdict,
    WatchingHabits,
    archetype_for,
)
from AniRec.gui_main import create_application


ICON_DIR = (
    pathlib.Path(__file__).resolve().parents[1]
    / "AniRec"
    / "gui"
    / "resources"
    / "icons"
    / "ui"
)


def _reading(reading_id: str, position: float, value: str = "50%"):
    return FingerprintReading(
        reading_id, reading_id.upper(), value, position=position
    )


def test_the_verdict_names_the_reader_s_most_unusual_trait():
    """Not the largest number - the one furthest from an ordinary reader.

    Completion sits at 0.87 and contrarian at 0.31, so a rule that measured
    distance from the middle of the rail would call this reader a finisher.
    Almost everybody finishes most of what they start; almost nobody
    disagrees with the consensus on a third of their list.
    """
    profile = TasteProfile(
        fingerprint=(
            _reading("community-sync", 0.72),
            _reading("rating-bias", 0.36),
            _reading("contrarian", 0.31),
            _reading("completion", 0.87),
            _reading("mainstream", 0.63),
        )
    )

    archetype = archetype_for(profile)

    assert archetype is not None
    assert archetype.archetype_id == "contrarian-high"
    assert archetype.name == "the outlier"


def test_the_verdict_reads_both_directions_of_the_same_axis():
    low = TasteProfile(fingerprint=(_reading("contrarian", 0.02),))
    high = TasteProfile(fingerprint=(_reading("contrarian", 0.40),))

    assert archetype_for(low).archetype_id == "contrarian-low"
    assert archetype_for(high).archetype_id == "contrarian-high"


def test_a_balanced_reader_gets_a_truthful_positive_identity():
    profile = TasteProfile(
        fingerprint=(
            _reading("community-sync", 0.60),
            _reading("rating-bias", 0.50),
            _reading("contrarian", 0.21),
            _reading("completion", 0.76),
            _reading("mainstream", 0.65),
        )
    )

    archetype = archetype_for(profile)
    assert archetype is not None
    assert archetype.archetype_id == "balanced-curator"
    assert archetype.name == "the balanced curator"
    assert archetype_for(TasteProfile()) is None


def test_the_verdict_is_stable_for_the_same_profile():
    """Two readings equally far out must not alternate between runs."""
    profile = TasteProfile(
        fingerprint=(
            _reading("completion", 0.75 + 0.18),
            _reading("contrarian", 0.20 + 0.15),
        )
    )

    first = archetype_for(profile)
    assert first is not None
    for _repeat in range(5):
        assert archetype_for(profile).archetype_id == first.archetype_id


def test_no_archetype_name_is_an_insult():
    """This is shown to a person about themselves.

    "You have bad taste" is not an insight however well the arithmetic
    supports it, so both ends of every axis are named for something real
    rather than for a deficiency.
    """
    from AniRec.presentation.taste_profile import _ARCHETYPES

    banned = {"bad", "poor", "worst", "boring", "basic", "shallow", "wrong"}
    for name, sentence in _ARCHETYPES.values():
        words = set(name.replace("-", " ").split()) | set(
            sentence.casefold().replace(".", "").split()
        )
        assert not (words & banned), name


def test_unlisted_facts_are_the_derived_ones_and_skip_what_is_missing():
    """The wink only works if every line is genuinely off-MAL.

    A half-populated profile produces a shorter list rather than a column of
    "N/A", which is the same rule the detail dialog follows.
    """
    full = TasteProfile(
        studios=StudioDNA(
            most_trusted=StudioReading("Kyoto Animation", 12, 8.42),
            nemesis=StudioReading("Studio Pierrot", 14, 5.10),
        ),
        genres=GenreDNA(divisive=GenreVerdict("Romance")),
        eras=EraPreferences(
            golden=EraBucket("2010-2014", 40, 8.13), season_of_choice="FALL"
        ),
        hidden_gems=HiddenGems(rate_text="14%"),
        hype_killers=HypeKillers(count=17),
    )

    facts = unlisted_facts(full)

    assert len(facts) == 7
    # CHANGE [FUN-FACTS]: each fact is a card - a mark, the figure, and a
    # sentence - so the value has to be the part worth reading, not something
    # buried mid-prose. These are the strings somebody screenshots.
    assert [fact.value for fact in facts] == [
        "Studio Pierrot",
        "Kyoto Animation",
        "Romance",
        "2010-2014",
        "Fall",
        "14%",
        "17",
    ]
    # A studio you clash with and a show you rated below the crowd are the
    # two facts that are not compliments, and they are the two drawn in the
    # danger role rather than in "yours".
    assert [fact.tone for fact in facts if fact.tone == "against"] == [
        "against",
        "against",
    ]
    # Every mark exists as a real asset; a card with a missing glyph is a
    # card with a hole in it.
    for fact in facts:
        assert (
            ICON_DIR / f"{fact.icon}.svg"
        ).is_file(), fact.icon
    assert not any("N/A" in fact.caption for fact in facts)

    assert unlisted_facts(TasteProfile()) == ()
    assert unlisted_sentences(TasteProfile()) == ()


def test_the_page_leads_with_the_verdict_and_folds_the_instrument():
    create_application([])
    page = ProfilePage()
    page.show_profile(SampleTasteProfileProvider().taste_profile())

    assert page.verdict.name_label.text() == "You are the outlier."
    # CHANGE [ONE-BOARD]: the readings, the named titles and the derived
    # facts are one grid. As three stacked grids each ended in its own
    # leftover space - three figures spread across a full-width row, then a
    # lone receipt beside 1100px of nothing, then a ragged card row.
    assert len(page.unlisted.facts) == 5 + 3 + 7
    assert len(page.unlisted.widgets) == len(page.unlisted.facts)
    legends = [fact.legend for fact in page.unlisted.facts]
    # Broad to specific: the shape of the reader, then the proof, then the
    # curiosities.
    assert legends[0] == "TASTE OVERLAP"
    assert legends[5] == "BIGGEST HYPE KILL"
    assert legends[8] == "NEMESIS"
    # Every instrument exists and every one of them starts shut: the reader
    # has already been told what they are, above.
    assert len(page.instrument_grid.widgets) == 10
    assert not any(section.is_expanded for section in page.instrument_grid.widgets)


def test_an_instrument_opens_and_closes_from_its_legend():
    create_application([])
    page = ProfilePage()
    page.show_profile(SampleTasteProfileProvider().taste_profile())
    section = page.sections["distribution"]

    section.title_label.click()
    assert section.is_expanded
    section.title_label.click()
    assert not section.is_expanded


def test_instrument_expansion_settles_before_the_click_is_painted():
    application = create_application([])
    page = ProfilePage()
    page.resize(1200, 700)
    page.show_profile(SampleTasteProfileProvider().taste_profile())
    page.show()
    application.processEvents()
    section = page.sections["hot-takes"]

    section.title_label.click()
    immediate = (
        page.scroll.widget().height(),
        page.instrument_grid.height(),
        section.height(),
    )
    application.processEvents()

    assert immediate == (
        page.scroll.widget().height(),
        page.instrument_grid.height(),
        section.height(),
    )
    page.close()


def test_profile_cover_requests_are_delivered_to_the_waiting_title():
    create_application([])
    url = "https://cdn.myanimelist.net/images/anime/1/1.jpg"
    page = ProfilePage()
    page.show_profile(
        TasteProfile(
            hot_takes=HotTakes(
                higher=(TitleVerdict("Cover Test", cover_url=url),),
            )
        )
    )
    requested = []
    page.cover_requested.connect(requested.append)
    row = page.hot_takes.widgets[0].rows[0]
    delivered = []
    row.set_cover_data = delivered.append

    page.request_visible_covers()
    page.deliver_cover(url, b"image-data")

    assert requested == [url]
    assert delivered == [b"image-data"]


def test_more_data_columns_do_not_share_their_vertical_row_height():
    from PySide6.QtWidgets import QFrame

    from AniRec.gui.profile_page import ReflowGrid

    application = create_application([])
    grid = ReflowGrid(
        320,
        spacing="lg",
        avoid_orphans=False,
        independent_columns=True,
    )
    cards = [QFrame() for _index in range(4)]
    for card, height in zip(cards, (80, 300, 80, 80), strict=True):
        card.setFixedHeight(height)

    grid.resize(700, 500)
    grid.set_widgets(cards)
    grid.show()
    application.processEvents()

    assert grid._columns == 2
    assert abs(cards[0].width() - cards[1].width()) <= 1
    assert cards[2].y() < cards[3].y()
    assert cards[2].y() >= cards[0].height()
    assert cards[3].y() >= cards[1].height()

    grid.resize(300, 800)
    application.processEvents()

    assert grid._columns == 1
    assert all(card.x() == cards[0].x() for card in cards)
    assert all(cards[index].y() < cards[index + 1].y() for index in range(3))
    grid.close()


def test_a_reader_with_no_nameable_trait_still_gets_a_sentence():
    """The hero must never render blank - it is the reason the page exists."""
    create_application([])
    page = ProfilePage()
    page.show_profile(TasteProfile(habits=WatchingHabits()))

    assert "still writing the profile" in page.verdict.name_label.text()
    assert page.verdict.sentence_label.text()
    assert page.unlisted.facts == ()


def test_a_claim_the_reader_cannot_check_carries_its_titles():
    """The three facts that are meaningless without evidence.

    "Your nemesis studio is Tezuka Productions" invites "who?" - most people
    cannot name a thing that studio made, so the card reads as the application
    asserting something rather than showing the reader themselves. "Military
    is your most divisive genre" invites "I have watched something tagged
    Military?". Both become interesting the moment the anime are named.
    """
    create_application([])
    page = ProfilePage()
    page.show_profile(SampleTasteProfileProvider().taste_profile())
    by_legend = {fact.legend: fact for fact in page.unlisted.facts}

    for legend in ("NEMESIS", "MOST TRUSTED", "MOST DIVISIVE"):
        assert by_legend[legend].evidence, f"{legend} states a claim with no proof"

    # A nemesis is a nemesis because of its low scores; listing a 7 beside the
    # 4s muddles the point the card exists to make.
    nemesis = by_legend["NEMESIS"].evidence
    assert nemesis == ("Bleach 4", "Naruto: Shippuuden 5")

    # Divisive means both ends. One end alone states the claim and hides the
    # half that proves it.
    divisive = by_legend["MOST DIVISIVE"].evidence
    assert divisive[0].endswith("10") and divisive[-1].endswith("2")

    # A percentage explains itself and needs no titles.
    assert by_legend["TASTE OVERLAP"].evidence == ()


def test_evidence_never_names_the_same_title_twice():
    """A title can sit at the top of one list and inside the other."""
    from AniRec.gui.profile_page import _evidence
    from AniRec.presentation.taste_profile import TasteTitle

    high = (TasteTitle("Bleach", 4.0), TasteTitle("Naruto", 5.0))
    low = (TasteTitle("Bleach", 4.0), TasteTitle("Gintama", 6.0))

    lines = _evidence(high, low)

    assert lines == ("Bleach 4", "Naruto 5", "Gintama 6")


def test_a_profile_with_no_recorded_titles_still_renders_its_cards():
    """Evidence is an improvement to a card, never a precondition for one."""
    create_application([])
    page = ProfilePage()
    page.show_profile(
        TasteProfile(studios=StudioDNA(nemesis=StudioReading("Bare Studio", 6, 5.0)))
    )

    fact = page.unlisted.facts[0]
    assert fact.value == "Bare Studio"
    assert fact.evidence == ()
    assert len(page.unlisted.widgets) == 1


def test_every_board_tile_is_a_legend_a_figure_and_a_sentence():
    """One shape, or the board is three grids wearing a costume.

    A reading, a named title and a derived fact are the same kind of claim -
    something true about this reader that comes out of comparing them against
    everybody else - and they only belong in one grid if they genuinely read
    the same. Anything that arrives without a figure would be a hole in the
    row.
    """
    create_application([])
    page = ProfilePage()
    page.show_profile(SampleTasteProfileProvider().taste_profile())

    for fact in page.unlisted.facts:
        assert fact.legend and fact.legend == fact.legend.upper(), fact
        assert fact.value and fact.value != "N/A", fact
        assert fact.caption, fact
        assert (ICON_DIR / f"{fact.icon}.svg").is_file(), fact.icon


def test_a_missing_group_leaves_no_hole_in_the_board():
    """A profile with only some of its facts still fills whole rows.

    This is the failure the single board exists to prevent: with three
    separate grids, a reader with three readings and one receipt got two
    half-empty rows before the facts even started.
    """
    create_application([])
    page = ProfilePage()
    page.show_profile(
        TasteProfile(
            fingerprint=(
                FingerprintReading("contrarian", "CONTRARIAN", "10%", position=0.1,
                                   detail="Rarely disagrees."),
            ),
            studios=StudioDNA(nemesis=StudioReading("Tezuka Productions", 6, 6.0)),
        )
    )

    # One reading and one fact, in one grid, with nothing between them.
    assert [fact.legend for fact in page.unlisted.facts] == [
        "CONTRARIAN",
        "NEMESIS",
    ]
    assert len(page.unlisted.widgets) == 2
