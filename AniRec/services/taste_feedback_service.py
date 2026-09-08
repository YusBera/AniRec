"""Adaptive, explainable reranking from explicit like and dislike feedback."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

try:
    from ..models import Recommendation
    from .recommendation_state_service import RecommendationLocalState
except ImportError:  # Compatibility with legacy top-level imports.
    from models import Recommendation
    from services.recommendation_state_service import RecommendationLocalState


# Feedback is expressed in match-percentage points, the same unit as the score
# it adjusts. Feedback is applied here and nowhere else: the generation pipeline
# deliberately produces a feedback-neutral baseline so that a vote is never
# counted twice.
LIKE_GENRE_BOOST = 6.0
DISLIKE_GENRE_PENALTY = 8.0
MAX_ABSOLUTE_GENRE_ADJUSTMENT = 24.0


def _clamp_adjustment(value: float) -> float:
    return max(
        -MAX_ABSOLUTE_GENRE_ADJUSTMENT,
        min(MAX_ABSOLUTE_GENRE_ADJUSTMENT, value),
    )


def _joined_reason(reason: str | None, clause: str, learned) -> str:
    """Fold what feedback taught us into the engine's sentence, not beside it.

    The engine writes "Matches your interests in A, B and C." Feedback adds a
    second list of the same kind, so it belongs inside that sentence as
    another clause. When the engine said nothing, or said something this
    cannot be grafted onto, the clause becomes a sentence of its own rather
    than being dropped.
    """
    base = (reason or "").strip()
    # A term the engine already named does not get named twice. This is what
    # made the doubled sentence so obviously redundant: both halves listed
    # Action and Historical, in a space that only had room for one of them.
    folded = base.casefold()
    learned = [term for term in learned if term.casefold() not in folded]
    terms = " and ".join(learned)
    if not terms:
        return base
    if base.endswith("."):
        base = base[:-1]
    if base:
        return f"{base}, and {clause} {terms}."
    return f"{clause[0].upper()}{clause[1:]} {terms}.".replace("Your", "Based on your", 1)


class TasteFeedbackService:
    """Turn explicit feedback into bounded genre affinities and visible reranking."""

    def genre_adjustments(
        self, state: RecommendationLocalState
    ) -> dict[str, float]:
        values: dict[str, float] = defaultdict(float)
        labels: dict[str, str] = {}
        for record in state.feedback:
            delta = LIKE_GENRE_BOOST if record.sentiment == "liked" else -DISLIKE_GENRE_PENALTY
            for genre in record.genres:
                key = genre.casefold()
                labels.setdefault(key, genre)
                values[key] += delta
        # Clamping the accumulated total rather than each step keeps the result
        # independent of the order feedback happens to be replayed in.
        return {
            labels[key]: round(_clamp_adjustment(score), 2)
            for key, score in values.items()
        }

    def personalize(
        self,
        recommendations: tuple[Recommendation, ...] | list[Recommendation],
        state: RecommendationLocalState,
    ) -> tuple[Recommendation, ...]:
        adjustments = {
            genre.casefold(): value
            for genre, value in self.genre_adjustments(state).items()
        }
        personalized = []
        for recommendation in recommendations:
            matches = [
                (genre, adjustments[genre.casefold()])
                for genre in recommendation.anime.genres
                if genre.casefold() in adjustments
            ]
            delta = _clamp_adjustment(sum(value for _genre, value in matches))
            match_score = max(0.0, min(100.0, recommendation.match_score + delta))
            reason = recommendation.reason
            positive = [genre for genre, value in matches if value > 0]
            negative = [genre for genre, value in matches if value < 0]
            # CHANGE [ONE-SENTENCE]: this used to prepend a second sentence to
            # the reason the engine had already written, so a card read
            # "Boosted by your likes in Action, Historical. Matches your
            # interests in Bandai Namco Picture…" - two sentences making the
            # same argument, in a two-line reservation that then cut the
            # second one mid-word. The clauses are joined into one sentence
            # instead, which says strictly more than either did and fits.
            if positive:
                reason = _joined_reason(reason, "your likes in", positive[:2])
            elif negative:
                reason = _joined_reason(reason, "your feedback in", negative[:2])
            personalized.append(
                replace(recommendation, match_score=round(match_score, 2), reason=reason)
            )
        personalized.sort(
            key=lambda item: (
                -item.match_score,
                -(item.anime.mean_score or 0.0),
                item.anime.display_title.casefold(),
            )
        )
        return tuple(
            replace(item, rank=index)
            for index, item in enumerate(personalized, start=1)
        )
