"""Genre importance, kept as the original entry point over the new engine.

The scoring model lives in :mod:`scoring`. This module remains so that the
command line workflow and anything importing ``calculate_genre_importance``
keep working, and now reports learned affinities rather than the frequency
share the original implementation produced.
"""

import math

try:
    from .genre_utils import parse_genres
    from .scoring.features import GENRE, feature_label, feature_namespace
    from .scoring.taste import build_taste_profile
except ImportError:  # Backward compatibility for direct script-style imports.
    from genre_utils import parse_genres
    from scoring.features import GENRE, feature_label, feature_namespace
    from scoring.taste import build_taste_profile


# Learned affinities sit roughly within plus or minus one. Reporting them on a
# wider scale keeps the numbers readable in the same places the old frequency
# shares were shown.
#
# Importance reports affinity alone, deliberately without the rarity weight
# the ranker applies. Rarity governs how informative a match is, not how much
# the user likes something, and folding it in here would rank a genre seen
# once above a long-standing favourite.
IMPORTANCE_SCALE = 100.0


def calculate_genre_importance(df, genre_medians=None):
    """Return each genre's learned importance to the user.

    ``genre_medians`` is accepted for compatibility and no longer used. The
    original formula multiplied a frequency share by the genre's mean rating
    divided by its own median, a ratio computed from the same sample and so
    equal to one for any consistently rated genre. That made the result a
    frequency histogram in which a genre watched often but rated poorly
    outranked one watched rarely and loved. Importance is now driven by how far
    above or below the user's own average a genre sits, tempered by how much
    evidence supports it.
    """
    profile = build_taste_profile(df)
    importance = {}
    for feature, affinity in profile.affinities.items():
        if feature_namespace(feature) != GENRE:
            continue
        value = affinity * IMPORTANCE_SCALE
        if not math.isnan(value):
            importance[feature_label(feature)] = round(value, 2)
    return importance


def _to_score(value):
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(score) else score
