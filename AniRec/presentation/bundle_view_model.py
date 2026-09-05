"""Grouping recommendations into series bundles.

A franchise with several entries - seasons, movies, OVAs, specials - is one
thing a person decides about, not five. Presenting it as five cards spends
five slots of a feed on one decision; presenting it as none at all is what
happens today, because ``collaborative.py`` withholds continuations.

The rule this implements: **a bundle is offered only when the user has
watched no entry in the series.** That extends the existing exclusion rather
than fighting it - continuations are withheld because the user "almost
certainly knows these already", which is true of a franchise they have
started and false of one they have not.

Everything here is deliberately free of Qt and of services, so the grouping
can be tested against plain data. What it cannot do is invent relation edges:
see ``docs/design/BUNDLE_HANDOFF.md`` for why the edges are missing for exactly the
franchises this wants to group, and what closing that costs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from ..scoring.collaborative import SEQUEL_RELATIONS
from .recommendation_view_model import RecommendationViewModel


# Below this a "bundle" is a single card wearing a stack, which is a lie about
# the shape of what is inside it.
MINIMUM_BUNDLE_SIZE = 2

# Ordering inside a bundle. `relation_type` says "sequel", never "season 2",
# so the running order has to come from the data that is actually present.
# Broadcast order is what a viewer would follow, and the media type breaks the
# tie so a movie never precedes the series it belongs to.
_MEDIA_ORDER = {"tv": 0, "ona": 1, "ova": 2, "special": 3, "movie": 4, "music": 5}


def _media_rank(model: RecommendationViewModel) -> int:
    kind = str(getattr(model, "media_type", "") or "").strip().casefold()
    return _MEDIA_ORDER.get(kind, 3)


def _sort_key(model: RecommendationViewModel) -> tuple:
    year = model.year if model.year is not None else 9999
    return (year, _media_rank(model), model.display_title)


@dataclass(frozen=True)
class BundleViewModel:
    """One franchise, and the entries of it that were recommended."""

    key: str
    title: str
    entries: tuple[RecommendationViewModel, ...]
    average_match: float
    lowest_match: float
    highest_match: float
    contributions: tuple[tuple[str, float], ...]
    reason: str

    @property
    def size(self) -> int:
        return len(self.entries)

    @property
    def mal_ids(self) -> tuple[int, ...]:
        return tuple(entry.mal_id for entry in self.entries if entry.mal_id is not None)

    @classmethod
    def from_entries(
        cls, entries: Sequence[RecommendationViewModel]
    ) -> "BundleViewModel":
        """Build a bundle from the entries of one franchise.

        The bundle's score is the **mean** of its members, not the best of
        them. A best-of number would rank every bundle by its strongest entry
        and make bundles systematically outscore the single titles beside them
        in the same grid, which is a presentation choice masquerading as a
        measurement. The spread is carried separately so the mean cannot
        quietly mislead.
        """
        ordered = tuple(sorted(entries, key=_sort_key))
        scores = [entry.personal_match for entry in ordered]
        average = sum(scores) / len(scores) if scores else 0.0
        # The origin of the franchise names it: the earliest entry is the one
        # a person would recognise the series by.
        title = ordered[0].display_title if ordered else ""
        return cls(
            key="bundle:%s" % ",".join(
                str(entry.mal_id) for entry in ordered if entry.mal_id is not None
            ),
            title=title,
            entries=ordered,
            average_match=average,
            lowest_match=min(scores) if scores else 0.0,
            highest_match=max(scores) if scores else 0.0,
            contributions=_average_contributions(ordered),
            reason=_bundle_reason(ordered),
        )


def _average_contributions(
    entries: Sequence[RecommendationViewModel],
) -> tuple[tuple[str, float], ...]:
    """Mean contribution per term, so a rail can decompose the mean score.

    Summing instead of averaging would produce a rail whose segments add to
    five times the number printed above it.
    """
    totals: dict[str, float] = {}
    for entry in entries:
        for name, value in entry.genre_contributions:
            cleaned = str(name).strip()
            if not cleaned:
                continue
            try:
                totals[cleaned] = totals.get(cleaned, 0.0) + float(value)
            except (TypeError, ValueError):
                continue
    if not entries:
        return ()
    averaged = [(name, total / len(entries)) for name, total in totals.items()]
    averaged.sort(key=lambda item: (-item[1], item[0]))
    return tuple(averaged)


def _bundle_reason(entries: Sequence[RecommendationViewModel]) -> str:
    """One sentence about the franchise, from what the entries already say.

    Never invented: the strongest entry's own explanation is quoted, and the
    only thing added is the fact that the rest belong to it - which is the
    reason the bundle exists.
    """
    if not entries:
        return ""
    strongest = max(entries, key=lambda entry: entry.personal_match)
    remainder = len(entries) - 1
    if not strongest.reason:
        if remainder <= 0:
            return ""
        return "%s and %d more in the same series." % (
            strongest.display_title,
            remainder,
        )
    if remainder <= 0:
        return strongest.reason
    return "%s %d more entries belong to the same series." % (
        strongest.reason,
        remainder,
    )


def franchise_components(
    graph: Mapping[int, Mapping[str, object]],
) -> dict[int, frozenset[int]]:
    """Group ids into franchises by walking the relation edges.

    ``related`` is a flat list of ``(mal_id, relation)`` pairs per title, so a
    franchise is the connected component containing them. Only relations that
    mean "more of the same story" join a component - a "recommendation" edge
    means something a viewer might also enjoy, which is a different claim.

    The result maps every id in a component to that whole component, so a
    lookup from any member finds the rest.
    """
    parent: dict[int, int] = {}

    def find(node: int) -> int:
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[right_root] = left_root

    for mal_id, entry in graph.items():
        try:
            source = int(mal_id)
        except (TypeError, ValueError):
            continue
        find(source)
        related = entry.get("related") if isinstance(entry, Mapping) else None
        for item in related or ():
            if not isinstance(item, Mapping):
                continue
            relation = str(item.get("relation") or "").strip().casefold()
            target = item.get("mal_id")
            if relation not in SEQUEL_RELATIONS or target is None:
                continue
            try:
                union(source, int(target))
            except (TypeError, ValueError):
                continue

    components: dict[int, set[int]] = {}
    for node in parent:
        components.setdefault(find(node), set()).add(node)
    return {
        node: frozenset(members)
        for members in components.values()
        for node in members
    }


def build_bundles(
    models: Sequence[RecommendationViewModel],
    graph: Mapping[int, Mapping[str, object]],
    watched_mal_ids: Iterable[int] = (),
    *,
    minimum_size: int = MINIMUM_BUNDLE_SIZE,
) -> tuple[tuple[object, ...], tuple[BundleViewModel, ...]]:
    """Fold recommendations that share a franchise into bundles.

    Returns ``(feed, bundles)`` where ``feed`` preserves the incoming order
    with each franchise collapsed to a single ``BundleViewModel`` at the
    position of its strongest member, and every other model left as it was.

    A franchise is bundled only when the user has watched none of it. The
    check is against the **full** completed list, not against the exclusion
    set the scorer builds: that set only covers titles rated above the user's
    own mean and is capped at forty seeds, so trusting it would offer someone
    "a series you have not started" for a series they watched and disliked.
    """
    watched = {int(value) for value in watched_mal_ids if value is not None}
    components = franchise_components(graph)

    grouped: dict[frozenset[int], list[RecommendationViewModel]] = {}
    for model in models:
        if model.mal_id is None:
            continue
        component = components.get(int(model.mal_id))
        if component is None or len(component) < minimum_size:
            continue
        # The whole franchise must be unknown to the user, including members
        # that were never recommended.
        if component & watched:
            continue
        grouped.setdefault(component, []).append(model)

    bundles: dict[frozenset[int], BundleViewModel] = {
        component: BundleViewModel.from_entries(entries)
        for component, entries in grouped.items()
        if len(entries) >= minimum_size
    }
    # A single recommended member of an unwatched franchise is still a single
    # recommendation; nothing is gained by wrapping one card in a stack.
    member_of = {
        model_id: component
        for component, bundle in bundles.items()
        for model_id in bundle.mal_ids
    }

    feed: list[object] = []
    placed: set[frozenset[int]] = set()
    for model in models:
        component = member_of.get(model.mal_id) if model.mal_id is not None else None
        if component is None:
            feed.append(model)
            continue
        if component in placed:
            continue
        placed.add(component)
        feed.append(bundles[component])
    return tuple(feed), tuple(bundles.values())
