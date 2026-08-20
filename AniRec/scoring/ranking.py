"""Score candidates against a taste profile, and explain the result.

The final score is a weighted sum:

    final = w_content * content + w_quality * quality + w_collaborative * collab

``content`` is the cosine between the user vector and the anime's feature
vector, which keeps a broadly tagged title from outscoring a precise match
simply by carrying more tags. ``quality`` is a confidence weighted community
score, so an obscure title with a handful of perfect ratings does not displace
a widely loved one.

Because the total is a sum, and cosine is itself a sum over features, each
feature's share is an exact identity rather than an estimate. That is what
lets the interface show a breakdown that adds up to the number beside it.

Any term whose input is unavailable is dropped and the remaining weights are
renormalised, so scores stay comparable whether or not the optional signals
are present.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

try:
    from .features import extract_features
    from .taste import TasteProfile
except ImportError:  # Compatibility with the sibling import path used by tests.
    from features import extract_features
    from taste import TasteProfile


CONTENT_WEIGHT = 0.55
COLLABORATIVE_WEIGHT = 0.30
QUALITY_WEIGHT = 0.15

# Community score prior. A title needs a comparable number of ratings before
# its own average outweighs the catalogue average.
QUALITY_PRIOR_SCORE = 6.5
QUALITY_PRIOR_VOTES = 2000.0
QUALITY_SCORE_RANGE = 10.0

# Fixed calibration constants. They are deliberately not derived from the data
# so that an anime's match percentage means the same thing in every run and in
# every batch, rather than being relative to whatever else was ranked with it.
CALIBRATION_MIDPOINT = 0.35
CALIBRATION_TEMPERATURE = 0.15

# Scale used to present the parts of a title whose blended score came out at or
# below zero. Any positive value keeps the signs truthful; the difference from
# the headline percentage is shown as a baseline term.
NEGATIVE_MATCH_SCALE = 100.0


def calibrate(final_score: float) -> float:
    """Map a blended score onto a stable 0 to 100 percentage."""
    try:
        exponent = -(float(final_score) - CALIBRATION_MIDPOINT) / CALIBRATION_TEMPERATURE
    except (TypeError, ValueError):
        return 0.0
    # math.exp overflows for very negative scores; the limit is simply 0.
    if exponent > 700:
        return 0.0
    return 100.0 / (1.0 + math.exp(exponent))


def quality_prior(mean_score: object, vote_count: object) -> float | None:
    """A confidence weighted community score in the range 0 to 1."""
    try:
        mean = float(mean_score)
    except (TypeError, ValueError):
        return None
    if math.isnan(mean) or mean <= 0:
        return None
    try:
        votes = float(vote_count)
    except (TypeError, ValueError):
        votes = 0.0
    if math.isnan(votes) or votes < 0:
        votes = 0.0
    weighted = (votes * mean + QUALITY_PRIOR_VOTES * QUALITY_PRIOR_SCORE) / (
        votes + QUALITY_PRIOR_VOTES
    )
    return max(0.0, min(1.0, weighted / QUALITY_SCORE_RANGE))


@dataclass(frozen=True)
class ScoredCandidate:
    """One ranked anime, with the parts its score was built from."""

    index: object
    features: frozenset[str] = frozenset()
    content_score: float = 0.0
    quality_score: float | None = None
    collaborative_score: float | None = None
    final_score: float = 0.0
    match_score: float = 0.0
    contributions: tuple[tuple[str, float], ...] = ()
    quality_contribution: float = 0.0
    collaborative_contribution: float = 0.0

    @property
    def explained_total(self) -> float:
        """The sum of every displayed part, which must equal ``match_score``."""
        return (
            sum(value for _feature, value in self.contributions)
            + self.quality_contribution
            + self.collaborative_contribution
        )


def _active_weights(
    has_quality: bool,
    has_collaborative: bool,
) -> tuple[float, float, float]:
    content = CONTENT_WEIGHT
    quality = QUALITY_WEIGHT if has_quality else 0.0
    collaborative = COLLABORATIVE_WEIGHT if has_collaborative else 0.0
    total = content + quality + collaborative
    if total <= 0:
        return 1.0, 0.0, 0.0
    return content / total, quality / total, collaborative / total


def score_candidate(
    row: Mapping[str, object],
    profile: TasteProfile,
    *,
    index: object = None,
    collaborative_score: float | None = None,
    vote_column: str = "Scoring Users",
) -> ScoredCandidate:
    """Score one candidate and keep the terms that produced the score."""
    features = extract_features(row)
    quality = quality_prior(row.get("Mean Score"), row.get(vote_column))
    content_weight, quality_weight, collaborative_weight = _active_weights(
        quality is not None, collaborative_score is not None
    )

    user_norm = profile.norm()
    anime_norm = math.sqrt(
        sum(profile.feature_idf(feature) ** 2 for feature in features)
    )

    # Per-feature share of the cosine. These sum to the cosine exactly.
    per_feature: dict[str, float] = {}
    if user_norm > 0 and anime_norm > 0:
        divisor = user_norm * anime_norm
        for feature in features:
            component = profile.weight(feature) * profile.feature_idf(feature)
            if component:
                per_feature[feature] = component / divisor
    content = sum(per_feature.values())

    quality_term = quality_weight * (quality or 0.0)
    collaborative_term = collaborative_weight * (collaborative_score or 0.0)
    final = content_weight * content + quality_term + collaborative_term
    match = calibrate(final)

    # Re-express every part as percentage points of the match the user sees.
    #
    # The scale must stay positive. Dividing the match by a negative total
    # would invert every sign and present a genre that dragged a title down as
    # though it had helped. A poorly matched title keeps its true signs and
    # carries the leftover in an explicit baseline term instead.
    scale = (match / final) if final > 0 else NEGATIVE_MATCH_SCALE
    contributions = tuple(
        sorted(
            (
                (feature, content_weight * value * scale)
                for feature, value in per_feature.items()
            ),
            key=lambda item: (-item[1], item[0]),
        )
    )
    return ScoredCandidate(
        index=index,
        features=features,
        content_score=content,
        quality_score=quality,
        collaborative_score=collaborative_score,
        final_score=final,
        match_score=match,
        contributions=contributions,
        quality_contribution=quality_term * scale,
        collaborative_contribution=collaborative_term * scale,
    )


def score_candidates(
    rows: Sequence[Mapping[str, object]],
    profile: TasteProfile,
    *,
    collaborative_scores: Mapping[object, float] | None = None,
    indexes: Sequence[object] | None = None,
) -> list[ScoredCandidate]:
    collaborative_scores = collaborative_scores or {}
    keys = list(indexes) if indexes is not None else list(range(len(rows)))
    return [
        score_candidate(
            row,
            profile,
            index=key,
            collaborative_score=collaborative_scores.get(key),
        )
        for key, row in zip(keys, rows)
    ]
