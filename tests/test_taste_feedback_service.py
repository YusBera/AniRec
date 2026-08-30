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
    # CHANGE [ONE-SENTENCE]: what feedback taught us is folded into the
    # engine's own sentence rather than prepended as a second one, and a term
    # the engine already named is not named twice. The card reserves two
    # lines; two sentences making the same argument did not fit in them.
    assert personalized[0].reason == "Based on your likes in Fantasy."
    assert personalized[0].reason.count(".") == 1
    assert personalized[1].match_score == 72.0

    # With a reason already written, the clause joins it instead of stacking.
    joined = service.personalize(
        (
            Recommendation(
                Anime("Fantasy", genres=("Fantasy",)),
                match_score=78,
                reason="Matches your interests in Mystery and Drama.",
            ),
        ),
        state,
    )
    assert joined[0].reason == (
        "Matches your interests in Mystery and Drama, and your likes in Fantasy."
    )
    assert joined[0].reason.count(".") == 1
