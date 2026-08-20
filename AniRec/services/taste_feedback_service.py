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
            if positive:
                learned = ", ".join(positive[:2])
                reason = f"Boosted by your likes in {learned}. {reason or ''}".strip()
            elif negative:
                learned = ", ".join(negative[:2])
                reason = f"Ranked lower from your feedback in {learned}. {reason or ''}".strip()
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
