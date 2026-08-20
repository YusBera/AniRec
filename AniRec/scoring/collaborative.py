"""An item to item signal built from MyAnimeList's own recommendation edges.

The graph is walked outward from the titles a user rated most highly rather
than inward from every candidate. A candidate-first pass would need one detail
request per candidate, hundreds of them; seeding from a few dozen favourites
covers the same ground for a fraction of the traffic, and the titles it reaches
are by construction the ones worth considering.

Edge weights are normalised per seed so that a heavily recommended blockbuster
does not drown out a seed with fewer, more specific neighbours, and the total
is normalised by the evidence behind it so the result stays comparable with the
other scoring terms.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


# Seeds are the user's strongest ratings. Beyond this the marginal value of
# another seed is small compared with the request it costs.
DEFAULT_SEED_LIMIT = 40

# Relations that mean "more of the same story" rather than "something you might
# also enjoy". The user almost certainly knows these already, so they are
# withheld from recommendations instead of being boosted.
SEQUEL_RELATIONS = frozenset(
    {
        "sequel",
        "prequel",
        "side_story",
        "parent_story",
        "alternative_version",
        "alternative_setting",
        "full_story",
        "summary",
    }
)


def select_seeds(
    rated: Iterable[tuple[int, float]],
    *,
    limit: int = DEFAULT_SEED_LIMIT,
) -> list[tuple[int, float]]:
    """Pick the titles worth spending a request on, strongest first.

    ``rated`` supplies ``(mal_id, centered_rating)`` pairs. Only titles the
    user liked more than their own average can seed the walk, since a title
    they disliked says nothing about what to look for next.
    """
    positive = [
        (int(mal_id), float(weight))
        for mal_id, weight in rated
        if mal_id is not None and weight > 0
    ]
    positive.sort(key=lambda item: (-item[1], item[0]))
    return positive[:limit]


def franchise_exclusions(graph: Mapping[int, Mapping[str, object]]) -> set[int]:
    """Titles that continue a story the user has already seen."""
    excluded: set[int] = set()
    for entry in graph.values():
        for related in entry.get("related") or ():
            if not isinstance(related, Mapping):
                continue
            relation = str(related.get("relation") or "").strip().casefold()
            mal_id = related.get("mal_id")
            if relation in SEQUEL_RELATIONS and mal_id is not None:
                excluded.add(int(mal_id))
    return excluded


def collaborative_scores(
    seeds: Iterable[tuple[int, float]],
    graph: Mapping[int, Mapping[str, object]],
) -> dict[int, float]:
    """Score candidates by how strongly the user's favourites point at them."""
    seeds = list(seeds)
    evidence = sum(abs(weight) for _mal_id, weight in seeds)
    if not seeds or evidence <= 0:
        return {}

    totals: dict[int, float] = {}
    for mal_id, weight in seeds:
        entry = graph.get(int(mal_id))
        if not entry:
            continue
        edges = [
            (int(item["mal_id"]), max(0.0, float(item.get("votes") or 0)))
            for item in entry.get("recommendations") or ()
            if isinstance(item, Mapping) and item.get("mal_id") is not None
        ]
        total_votes = sum(votes for _target, votes in edges)
        if total_votes <= 0:
            continue
        for target, votes in edges:
            totals[target] = totals.get(target, 0.0) + weight * (votes / total_votes)

    seed_ids = {int(mal_id) for mal_id, _weight in seeds}
    return {
        target: value / evidence
        for target, value in totals.items()
        if target not in seed_ids
    }
