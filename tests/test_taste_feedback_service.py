from __future__ import annotations

from AniRec.models import Anime, Recommendation
from AniRec.services import (
    RecommendationFeedback,
    RecommendationLocalState,
    TasteFeedbackService,
)


def test_feedback_builds_bounded_genre_affinities_and_reranks_explainably():
    state = RecommendationLocalState(
        feedback=(
            RecommendationFeedback(1, "liked", ("Fantasy", "Adventure"), "Liked"),
            RecommendationFeedback(2, "disliked", ("Romance",), "Disliked"),
        )
    )
    service = TasteFeedbackService()
    adjustments = service.genre_adjustments(state)
    assert adjustments == {"Fantasy": 6.0, "Adventure": 6.0, "Romance": -8.0}

    personalized = service.personalize(
        (
            Recommendation(Anime("Romance", genres=("Romance",)), match_score=80),
            Recommendation(Anime("Fantasy", genres=("Fantasy",)), match_score=78),
        ),
        state,
    )
    assert [item.anime.title for item in personalized] == ["Fantasy", "Romance"]
    assert personalized[0].match_score == 84.0
    assert "Boosted by your likes" in personalized[0].reason
    assert personalized[1].match_score == 72.0
