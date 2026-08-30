"""The Profile surface's opening statement, and the facts behind it.

The page now leads with a claim about the reader rather than with five equal
readings. That claim is derived, so it needs the same treatment as any other
derived figure on this page: it has to be right, it has to be stable, and it
has to decline to say anything when there is nothing to say.
"""

from __future__ import annotations

from AniRec.gui.profile_page import ProfilePage, unlisted_sentences
from AniRec.gui.taste_profile import (
    EraBucket,
    EraPreferences,
    FingerprintReading,
    GenreDNA,
    GenreVerdict,
    HiddenGems,
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


def test_an_ordinary_reader_is_not_given_an_invented_personality():
    """A label for someone who is typical on every axis is a made-up one."""
    profile = TasteProfile(
        fingerprint=(
            _reading("community-sync", 0.60),
            _reading("rating-bias", 0.50),
            _reading("contrarian", 0.21),
            _reading("completion", 0.76),
            _reading("mainstream", 0.65),
        )
    )

    assert archetype_for(profile) is None
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
    from AniRec.gui.taste_profile import _ARCHETYPES

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

    sentences = unlisted_sentences(full)

    assert len(sentences) == 7
    assert any("Studio Pierrot" in line for line in sentences)
    assert any("Romance" in line for line in sentences)
    assert any("2010-2014" in line for line in sentences)
    assert not any("N/A" in line for line in sentences)

    assert unlisted_sentences(TasteProfile()) == ()


def test_the_page_leads_with_the_verdict_and_folds_the_instrument():
    create_application([])
    page = ProfilePage()
    page.show_profile(SampleTasteProfileProvider().taste_profile())

    assert page.verdict.name_label.text() == "You are the outlier."
    assert page.verdict.evidence_label.text()
    # Three named titles, not three percentages.
    assert len(page.receipts.widgets) == 3
    assert page.unlisted.sentences
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


def test_a_reader_with_no_nameable_trait_still_gets_a_sentence():
    """The hero must never render blank - it is the reason the page exists."""
    create_application([])
    page = ProfilePage()
    page.show_profile(TasteProfile(habits=WatchingHabits()))

    assert "hard to pin down" in page.verdict.name_label.text()
    assert page.verdict.sentence_label.text()
    assert not page.verdict.evidence_label.isVisibleTo(page.verdict)


def test_a_rewatch_receipt_does_not_reserve_columns_for_scores_it_lacks():
    """A rewatch note has a count, not two opinions to set against each other."""
    create_application([])
    page = ProfilePage()
    page.show_profile(
        TasteProfile(
            hype_killers=HypeKillers(
                biggest=TitleVerdict(
                    "A", your_score=3, community_score=8.7, delta=-5.7
                )
            ),
            habits=WatchingHabits(
                most_rewatched=RewatchNote("Steins;Gate", watches=6)
            ),
        )
    )

    spoken = {
        panel.row._title_text: panel.row.accessibleName()
        for panel in page.receipts.widgets
    }
    # The comparison row still announces both opinions, because it has both.
    assert "You 3" in spoken["A"]
    assert "community 8.70" in spoken["A"]
    # The rewatch row announces the figure it actually shows, and does not
    # reserve two columns for a comparison that does not exist here.
    assert "times 6" in spoken["Steins;Gate"]
    assert "N/A" not in spoken["Steins;Gate"]
    assert "community" not in spoken["Steins;Gate"]
