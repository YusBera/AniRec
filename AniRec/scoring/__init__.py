"""Explainable hybrid scoring for AniRec.

The engine is built from parts that each answer one question:

``features``  what describes an anime
``taste``     how much the user likes each of those descriptors
``ranking``   how well a given anime matches, and why

Every score a user sees is a weighted sum whose terms are kept, so an
explanation is a decomposition of the real number rather than a story
reconstructed alongside it.
"""

from __future__ import annotations

try:
    from .features import extract_features, feature_label
    from .ranking import ScoredCandidate, score_candidates
    from .taste import TasteProfile, build_taste_profile
except ImportError:  # Compatibility with the sibling import path used by tests.
    from features import extract_features, feature_label
    from ranking import ScoredCandidate, score_candidates
    from taste import TasteProfile, build_taste_profile


__all__ = [
    "ScoredCandidate",
    "TasteProfile",
    "build_taste_profile",
    "extract_features",
    "feature_label",
    "score_candidates",
]
