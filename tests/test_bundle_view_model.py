"""Franchises are grouped, ordered and scored the way the design says.

The rule under test: a bundle is offered only when the user has watched no
entry in the series. Getting that wrong is the worst failure this feature can
have - presenting "a series you have not started" to somebody who has seen
half of it.
"""

from __future__ import annotations

from AniRec.gui.bundle_view_model import (
    BundleViewModel,
    build_bundles,
    franchise_components,
)
from AniRec.gui.recommendation_view_model import RecommendationViewModel
from AniRec.models import Anime, Recommendation


def model(
    mal_id,
    title,
    *,
    match=80.0,
    year=2010,
    media_type="tv",
    reason="Because you rated Drama highly.",
    contributions=(("Drama", 20.0), ("Mystery", 10.0)),
):
    return RecommendationViewModel.from_recommendation(
        Recommendation(
            Anime(
                title,
                mal_id=mal_id,
                genres=("Drama", "Mystery"),
                mean_score=8.0,
                status="finished_airing",
                episodes=12,
                year=year,
                media_type=media_type,
            ),
            match_score=match,
            reason=reason,
            genre_contributions=contributions,
        )
    )


def graph(*edges):
    """Build a relation graph from (source, target, relation) triples."""
    built: dict[int, dict] = {}
    for source, target, relation in edges:
        built.setdefault(source, {"related": []})["related"].append(
            {"mal_id": target, "relation": relation}
        )
        built.setdefault(target, {"related": []})
    return built


def test_related_titles_collapse_into_one_component():
    components = franchise_components(
        graph((1, 2, "sequel"), (2, 3, "sequel"), (3, 4, "side_story"))
    )
    assert components[1] == frozenset({1, 2, 3, 4})
    assert components[4] == components[1]


def test_a_recommendation_edge_does_not_join_a_franchise():
    """"You might also enjoy" is a different claim from "same story"."""
    components = franchise_components(graph((1, 2, "recommendation"), (1, 3, "other")))
    assert components[1] == frozenset({1})
    assert components[2] == frozenset({2})


def test_an_unwatched_franchise_is_offered_as_one_bundle():
    models = [model(1, "Origin", year=2011), model(2, "Origin 2", year=2018)]
    feed, bundles = build_bundles(models, graph((1, 2, "sequel")), watched_mal_ids=())

    assert len(bundles) == 1
    assert len(feed) == 1
    bundle = feed[0]
    assert isinstance(bundle, BundleViewModel)
    assert bundle.size == 2
    # The origin names the series - it is what a person recognises it by.
    assert bundle.title == "Origin"


def test_a_franchise_the_user_has_started_is_never_bundled():
    """Even when the watched entry is not one of the recommendations.

    This is the whole rule. The user has seen entry 3; entries 1 and 2 were
    recommended and belong to the same series, so the series is known to them
    and must not arrive as "a series you have not started".
    """
    models = [model(1, "Origin"), model(2, "Origin 2")]
    relations = graph((1, 2, "sequel"), (2, 3, "sequel"))

    feed, bundles = build_bundles(models, relations, watched_mal_ids=[3])

    assert bundles == ()
    assert [item.mal_id for item in feed] == [1, 2]


def test_a_lone_recommended_member_stays_a_single_card():
    """One card wearing a stack would be a lie about what is inside it."""
    models = [model(1, "Origin"), model(9, "Unrelated")]
    feed, bundles = build_bundles(models, graph((1, 2, "sequel")), watched_mal_ids=())

    assert bundles == ()
    assert [item.mal_id for item in feed] == [1, 9]


def test_the_bundle_takes_the_position_of_its_strongest_member():
    models = [
        model(9, "Unrelated", match=95.0),
        model(1, "Origin", match=90.0),
        model(8, "Other", match=70.0),
        model(2, "Origin 2", match=60.0),
    ]
    feed, _bundles = build_bundles(models, graph((1, 2, "sequel")), watched_mal_ids=())

    kinds = [type(item).__name__ for item in feed]
    assert kinds == ["RecommendationViewModel", "BundleViewModel", "RecommendationViewModel"]
    assert [getattr(item, "mal_id", None) for item in feed][0] == 9


def test_entries_run_in_broadcast_order_with_the_movie_after_its_series():
    models = [
        model(3, "Movie", year=2013, media_type="movie"),
        model(1, "Season 1", year=2011),
        model(2, "Season 2", year=2018),
    ]
    feed, _ = build_bundles(
        models, graph((1, 2, "sequel"), (1, 3, "side_story")), watched_mal_ids=()
    )
    assert [entry.display_title for entry in feed[0].entries] == [
        "Season 1",
        "Movie",
        "Season 2",
    ]


def test_a_movie_never_precedes_a_series_released_the_same_year():
    models = [
        model(3, "The Movie", year=2011, media_type="movie"),
        model(1, "The Series", year=2011, media_type="tv"),
    ]
    feed, _ = build_bundles(models, graph((1, 3, "side_story")), watched_mal_ids=())
    assert [entry.display_title for entry in feed[0].entries] == [
        "The Series",
        "The Movie",
    ]


def test_the_bundle_score_is_the_mean_and_the_spread_is_kept():
    """Best-of would rank every bundle by its strongest entry.

    That would make bundles systematically outscore the single cards beside
    them in the same grid - a presentation choice wearing the clothes of a
    measurement. The spread is carried so the mean cannot quietly mislead.
    """
    models = [model(1, "Origin", match=94.0), model(2, "Origin 2", match=60.0)]
    feed, _ = build_bundles(models, graph((1, 2, "sequel")), watched_mal_ids=())
    bundle = feed[0]

    assert bundle.average_match == 77.0
    assert bundle.lowest_match == 60.0
    assert bundle.highest_match == 94.0


def test_the_rail_decomposes_the_mean_rather_than_the_sum():
    """A summed rail would add up to twice the number printed above it."""
    models = [
        model(1, "Origin", match=90.0, contributions=(("Drama", 30.0), ("Mystery", 10.0))),
        model(2, "Origin 2", match=70.0, contributions=(("Drama", 10.0), ("Mystery", 30.0))),
    ]
    feed, _ = build_bundles(models, graph((1, 2, "sequel")), watched_mal_ids=())

    assert dict(feed[0].contributions) == {"Drama": 20.0, "Mystery": 20.0}


def test_the_reason_quotes_the_strongest_entry_and_never_invents_one():
    models = [
        model(1, "Origin", match=94.0, reason="Because you rated Death Note highly."),
        model(2, "Origin 2", match=60.0, reason="Because you rated something else."),
    ]
    feed, _ = build_bundles(models, graph((1, 2, "sequel")), watched_mal_ids=())
    reason = feed[0].reason

    assert reason.startswith("Because you rated Death Note highly.")
    assert "1 more entries belong to the same series." in reason


def test_a_written_explanation_is_not_needed_for_the_bundle_to_have_one():
    """An entry with no reason of its own still derives one from its score.

    ``RecommendationViewModel`` fills an empty explanation from the genres
    that carried the score, so the bundle quotes that rather than inventing
    anything.
    """
    models = [
        model(1, "Origin", match=94.0, reason=None),
        model(2, "Origin 2", match=60.0, reason=None),
    ]
    feed, _ = build_bundles(models, graph((1, 2, "sequel")), watched_mal_ids=())

    assert feed[0].reason.startswith("Matched on Drama and Mystery.")
    assert "1 more entries belong to the same series." in feed[0].reason


def test_a_franchise_with_nothing_to_say_falls_back_to_naming_itself():
    """No explanation and no contributions - the only honest line left."""
    models = [
        model(1, "Origin", match=94.0, reason=None, contributions=()),
        model(2, "Origin 2", match=60.0, reason=None, contributions=()),
    ]
    feed, _ = build_bundles(models, graph((1, 2, "sequel")), watched_mal_ids=())

    assert feed[0].reason == "Origin and 1 more in the same series."


def test_no_relations_means_no_bundles_and_an_untouched_feed():
    """The state the app is actually in today, per the handoff."""
    models = [model(1, "One"), model(2, "Two"), model(3, "Three")]
    feed, bundles = build_bundles(models, {}, watched_mal_ids=())

    assert bundles == ()
    assert [item.mal_id for item in feed] == [1, 2, 3]
