"""Build a feed from an already ranked, already eligible candidate pool.

Selection is the stage after scoring. It decides which ranked rows are shown,
never how they are scored: rows are returned untouched and in their original
rank order, so every score, rank and explanation still describes the ranking
that produced it.

The policy is deterministic. It uses no random source, no hash ordering and no
clock, so the same ranked rows and the same adventurousness always produce the
same feed.

Adventurousness (the stored ``randomness_factor``, 1-10) sets ``max_leap``,
the number of rank positions a title may be moved past for adding variety:

* ``max_leap = 2 * (adventurousness - 1)``, so 1 is exactly the top ``count``
  in rank order and 10 allows a leap of up to 18 positions.
* Only the top ``count + max_leap`` ranked rows are ever considered.
* The top-ranked row is always selected.
* Each further slot is filled greedily by the row maximising
  ``-rank_position - max_leap * redundancy``, where ``redundancy`` in [0, 1] is
  the row's highest similarity to any row already selected. Ties keep the
  higher-ranked row. A row therefore displaces a higher-ranked one only when it
  is less redundant, and never by ``max_leap`` or more positions.

Similarity uses only catalogue metadata the serving rows carry: genres,
studios, source and media type, each compared as a label set (Jaccard) and
weighted below. Only facets present on both rows are compared, and their
weights are renormalised over those facets, so a row identical on every fact
both rows share is fully redundant. A pair with no comparable facet earns no
novelty and counts as fully redundant, so an undescribed title can keep its
rank position but never overtakes a described one for "variety". A partly
described title is judged only on the facets it shares with the other row, so
one verified differing fact can count as full novelty. A pool with no metadata
at all is served in rank order.
No franchise identity is inferred: titles, numbering and shared words are not
relation evidence.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

try:
    from ..genre_utils import parse_genres
except ImportError:  # Compatibility with the sibling import path used by tests.
    from genre_utils import parse_genres


SELECTION_POLICY_VERSION = "rank-diversity-v1"

MIN_ADVENTUROUSNESS = 1
MAX_ADVENTUROUSNESS = 10

# Rank positions a fully novel title may gain per adventurousness step.
LEAP_PER_STEP = 2

# Columns compared for redundancy and their share of the similarity. The same
# columns feed the heuristic feature vocabulary in ``scoring.features``.
FACET_WEIGHTS = (
    ("Genres", 0.5),
    ("Studios", 0.2),
    ("Source", 0.15),
    ("Media Type", 0.15),
)

# Placeholder values that state a fact is unknown rather than shared.
_UNKNOWN_LABELS = frozenset({"unknown", "none", "nan", "null", "n/a", "<na>"})


def clamp_adventurousness(value: object) -> int:
    """Map a stored setting onto the supported 1-10 range."""
    try:
        number = int(value)
    except (TypeError, ValueError):
        return MIN_ADVENTUROUSNESS
    return min(max(number, MIN_ADVENTUROUSNESS), MAX_ADVENTUROUSNESS)


def max_leap(adventurousness: object) -> int:
    """Rank positions a title may move ahead for adding variety."""
    return LEAP_PER_STEP * (clamp_adventurousness(adventurousness) - 1)


def select_feed(
    ranked_rows: Sequence[Mapping[str, object]],
    count: int,
    adventurousness: object,
) -> tuple[int, ...]:
    """Return the positions of the rows to present, in ascending rank order.

    ``ranked_rows`` must already be final-eligible and sorted best first by the
    ranking engine's own stable tie-breakers.
    """
    count = max(int(count), 0)
    if not ranked_rows or count == 0:
        return ()
    leap = max_leap(adventurousness)
    window = min(len(ranked_rows), count + leap)
    if window <= count or leap == 0:
        return tuple(range(min(count, len(ranked_rows))))

    facets = [_facets(ranked_rows[position]) for position in range(window)]
    selected = [0]
    redundancy = [0.0] * window
    remaining = list(range(1, window))
    while len(selected) < count and remaining:
        latest = facets[selected[-1]]
        best_position = None
        best_value = -math.inf
        for position in remaining:
            redundancy[position] = max(
                redundancy[position], _similarity(facets[position], latest)
            )
            value = -position - leap * redundancy[position]
            if value > best_value:
                best_value = value
                best_position = position
        selected.append(best_position)
        remaining.remove(best_position)
    return tuple(sorted(selected))


def _facets(row: Mapping[str, object]) -> tuple[frozenset[str], ...]:
    return tuple(_labels(row.get(column)) for column, _weight in FACET_WEIGHTS)


def _similarity(
    left: tuple[frozenset[str], ...],
    right: tuple[frozenset[str], ...],
) -> float:
    total = 0.0
    compared = 0.0
    for (_column, weight), a, b in zip(FACET_WEIGHTS, left, right):
        if a and b:
            total += weight * len(a & b) / len(a | b)
            compared += weight
    if compared == 0.0:
        # Nothing comparable is not evidence of variety.
        return 1.0
    return total / compared


def _labels(value: object) -> frozenset[str]:
    """Normalised label set, parsed the same way the feature extractor does."""
    if value is None:
        return frozenset()
    if hasattr(value, "tolist") and not isinstance(value, str):
        value = value.tolist()
    if not isinstance(value, (str, list, tuple, set, frozenset)):
        try:
            if value != value:  # NaN
                return frozenset()
        except (TypeError, ValueError):  # pandas.NA and other undecidable scalars
            return frozenset()
    labels = set()
    for label in parse_genres(value):
        key = " ".join(label.split()).casefold()
        if key and key not in _UNKNOWN_LABELS:
            labels.add(key)
    return frozenset(labels)
