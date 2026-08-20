"""Turn a rating history into per-feature affinities.

Two ideas carry this module.

Mean centering asks whether a title beat *your* average rather than some
absolute bar, so a generous rater who scores everything 8 to 10 and a harsh
one who scores 4 to 7 produce comparable profiles.

Shrinkage asks how much evidence stands behind each feature. A genre seen
once contributes a fraction of its apparent strength; one seen twenty times
contributes nearly all of it. Without this a single rave review outranks a
long, consistent record, which is how the previous model behaved.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

try:
    from .features import (
        document_frequencies,
        extract_features,
        inverse_document_frequency,
    )
except ImportError:  # Compatibility with the sibling import path used by tests.
    from features import (
        document_frequencies,
        extract_features,
        inverse_document_frequency,
    )


# How much evidence a feature needs before it carries most of its apparent
# strength. At n == SHRINKAGE_STRENGTH a feature keeps half its measured
# affinity, so five consistent observations are treated as meaningful and a
# single one is not.
SHRINKAGE_STRENGTH = 5.0

# Ratings vary less than a full point for some users. Flooring the spread
# stops a narrow rating range from inflating every z score.
MINIMUM_RATING_SPREAD = 1.0

# Bounds on a learned affinity, matching the targets used by feedback.
AFFINITY_LIMIT = 1.0

# How strongly one explicit vote pulls an affinity toward its target. The
# update is a convex combination, so repeated votes converge instead of
# running away, and no clamp is needed to keep it bounded.
FEEDBACK_RATE = 0.25


def _rating(value: object) -> float | None:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(score) or score <= 0:
        return None
    return score


@dataclass(frozen=True)
class TasteProfile:
    """What a user tends to like, expressed per feature."""

    affinities: Mapping[str, float] = field(default_factory=dict)
    idf: Mapping[str, float] = field(default_factory=dict)
    observations: Mapping[str, int] = field(default_factory=dict)
    rated_count: int = 0
    mean_rating: float = 0.0
    rating_spread: float = MINIMUM_RATING_SPREAD

    def affinity(self, feature: str) -> float:
        return float(self.affinities.get(feature, 0.0))

    def feature_idf(self, feature: str) -> float:
        """Rare features weigh more; unseen ones still count a little."""
        return float(self.idf.get(feature, 1.0))

    def weight(self, feature: str) -> float:
        """The user-vector component for a feature."""
        return self.affinity(feature) * self.feature_idf(feature)

    def norm(self, features: Iterable[str] | None = None) -> float:
        keys = self.affinities.keys() if features is None else features
        return math.sqrt(sum(self.weight(feature) ** 2 for feature in keys))

    @property
    def is_empty(self) -> bool:
        return not self.affinities

    def with_feedback(
        self,
        updates: Iterable[tuple[frozenset[str], float, float]],
    ) -> "TasteProfile":
        """Return a profile moved toward explicit likes and dislikes.

        Each update carries a target and a strength drawn from how much
        feedback stands behind it, and moves the affected affinities that
        fraction of the way to the target. Because that is a convex
        combination the values stay bounded without a clamp, weak evidence
        nudges while consistent evidence commits, and a feature the user has
        never rated is created rather than discarded.
        """
        affinities = dict(self.affinities)
        for features, target, strength in updates:
            bounded = max(-AFFINITY_LIMIT, min(AFFINITY_LIMIT, float(target)))
            rate = max(0.0, min(1.0, float(strength)))
            for feature in features:
                current = affinities.get(feature, 0.0)
                affinities[feature] = current + rate * (bounded - current)
        return TasteProfile(
            affinities=affinities,
            idf=dict(self.idf),
            observations=dict(self.observations),
            rated_count=self.rated_count,
            mean_rating=self.mean_rating,
            rating_spread=self.rating_spread,
        )


def build_taste_profile(
    completed,
    *,
    catalog=None,
    shrinkage: float = SHRINKAGE_STRENGTH,
) -> TasteProfile:
    """Build a taste profile from a user's rated history.

    ``completed`` is the user's list. ``catalog`` is the wider pool used to
    judge how common each feature is; the user's own list is used when no
    catalogue is supplied, which is less discriminating but never wrong.

    Only genuinely rated titles inform the profile. Unrated entries say
    nothing about preference, and treating an imputed value as a real one is
    what previously let AniRec measure its own guesses.
    """
    rows = [row for _index, row in completed.iterrows()] if hasattr(completed, "iterrows") else list(completed)
    rated: list[tuple[frozenset[str], float]] = []
    for row in rows:
        score = _rating(row.get("User Score"))
        if score is None:
            continue
        rated.append((extract_features(row), score))

    if not rated:
        return TasteProfile()

    scores = [score for _features, score in rated]
    mean_rating = sum(scores) / len(scores)
    variance = sum((score - mean_rating) ** 2 for score in scores) / len(scores)
    spread = max(math.sqrt(variance), MINIMUM_RATING_SPREAD)

    totals: dict[str, float] = {}
    counts: dict[str, int] = {}
    for features, score in rated:
        centered = (score - mean_rating) / spread
        for feature in features:
            totals[feature] = totals.get(feature, 0.0) + centered
            counts[feature] = counts.get(feature, 0) + 1

    affinities = {}
    for feature, count in counts.items():
        confidence = count / (count + float(shrinkage))
        affinities[feature] = confidence * (totals[feature] / count)

    catalog_rows = (
        [row for _index, row in catalog.iterrows()]
        if catalog is not None and hasattr(catalog, "iterrows")
        else rows
    )
    frequencies = document_frequencies(catalog_rows)
    for feature in counts:
        frequencies.setdefault(feature, 1)
    idf = inverse_document_frequency(len(catalog_rows), frequencies)

    return TasteProfile(
        affinities=affinities,
        idf=idf,
        observations=counts,
        rated_count=len(rated),
        mean_rating=mean_rating,
        rating_spread=spread,
    )
