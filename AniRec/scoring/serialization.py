"""Persist a taste profile as the tabular file the pipeline already carries.

``genre_importance.csv`` keeps its ``Genre`` and ``Importance_Score`` columns so
existing files, the command line workflow, and the genre panel continue to
work. The learned parts are stored beside them, and a file written before those
columns existed still loads, with its importance scores rescaled into affinities
so old profiles degrade rather than break.
"""

from __future__ import annotations

import pandas as pd

try:
    from .features import GENRE, feature_label, feature_namespace, token
    from .taste import TasteProfile
except ImportError:  # Compatibility with the sibling import path used by tests.
    from features import GENRE, feature_label, feature_namespace, token
    from taste import TasteProfile


LEGACY_AFFINITY_CEILING = 0.6

PROFILE_COLUMNS = [
    "Feature",
    "Genre",
    "Importance_Score",
    "Affinity",
    "Idf",
    "Observations",
]


def profile_to_frame(profile: TasteProfile) -> pd.DataFrame:
    """Serialise a profile, strongest feature first."""
    rows = []
    for feature, affinity in profile.affinities.items():
        idf = profile.feature_idf(feature)
        rows.append(
            {
                "Feature": feature,
                "Genre": feature_label(feature),
                # How much the user likes this, on a familiar 0 to 100 style
                # scale. Deliberately excludes the rarity weight, which the
                # ranker reads from the Idf column instead.
                "Importance_Score": round(affinity * 100.0, 2),
                "Affinity": round(affinity, 6),
                "Idf": round(idf, 6),
                "Observations": int(profile.observations.get(feature, 0)),
            }
        )
    frame = pd.DataFrame(rows, columns=PROFILE_COLUMNS)
    if frame.empty:
        return frame
    return frame.sort_values(
        ["Importance_Score", "Genre"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)


def profile_from_frame(frame: pd.DataFrame) -> TasteProfile:
    """Rebuild a profile from its stored form."""
    if frame is None or frame.empty:
        return TasteProfile()

    has_learned = {"Affinity", "Idf"}.issubset(frame.columns)
    affinities: dict[str, float] = {}
    idf: dict[str, float] = {}
    observations: dict[str, int] = {}

    # Legacy files hold only frequency-share importance. Rescaling by the
    # largest value maps them into the affinity range so they still rank
    # sensibly, without pretending they carry information they never had.
    # The ceiling keeps them below full confidence, because a frequency share
    # says nothing about whether the user actually enjoyed the genre, and
    # leaves room for explicit feedback to override an inherited profile.
    legacy_peak = 0.0
    if not has_learned and "Importance_Score" in frame.columns:
        numeric = pd.to_numeric(frame["Importance_Score"], errors="coerce").abs()
        legacy_peak = float(numeric.max()) if not numeric.empty else 0.0

    for _index, row in frame.iterrows():
        feature = str(row.get("Feature") or "").strip()
        if not feature:
            label = str(row.get("Genre") or "").strip()
            if not label:
                continue
            feature = token(GENRE, label)
        elif not feature_namespace(feature):
            feature = token(GENRE, feature)

        if has_learned:
            affinity = pd.to_numeric(row.get("Affinity"), errors="coerce")
            value = pd.to_numeric(row.get("Idf"), errors="coerce")
            affinities[feature] = 0.0 if pd.isna(affinity) else float(affinity)
            idf[feature] = 1.0 if pd.isna(value) or value <= 0 else float(value)
        else:
            importance = pd.to_numeric(row.get("Importance_Score"), errors="coerce")
            importance = 0.0 if pd.isna(importance) else float(importance)
            affinities[feature] = (
                importance / legacy_peak * LEGACY_AFFINITY_CEILING
                if legacy_peak > 0
                else 0.0
            )
            idf[feature] = 1.0

        count = pd.to_numeric(row.get("Observations"), errors="coerce")
        observations[feature] = 0 if pd.isna(count) else int(count)

    return TasteProfile(
        affinities=affinities,
        idf=idf,
        observations=observations,
        rated_count=sum(observations.values()),
    )
