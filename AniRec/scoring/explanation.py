"""Answer "why was this recommended to me?" from the ranking that produced it.

Explanations are built after selection, for the rows actually served, from
values the ranking engine recorded. Nothing here re-scores a title or borrows
another engine's reasoning:

* ``exact-additive`` (heuristic): the parts of the ranking score. They sum to
  ``total`` exactly. Taste parts carry evidence from the reader's own rated
  titles; community rating and similar viewers are kept separate because they
  are not about the reader's taste.
* ``counterfactual-removal`` (sequence model): the model is rerun without
  parts of the reader's history and the pick is scored and ranked again among
  the same eligible candidates. One segment per genre *of the reader's
  titles* (remove every history title in that genre), and one effect per
  single history title. The model itself never sees genres, so a segment
  means "your titles in this genre", never "because this pick is in this
  genre". Removal effects overlap and interact, so segments do NOT sum to the
  score: they are relative impacts, and ``total``/``baseline`` are null.
  Deterministic: no sampling.
* ``unavailable``: the engine cannot explain itself, and says so.

The output is plain JSON-ready data. Wording is the client's job; the data says
what each number is.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence

try:
    from .features import extract_features, feature_label, feature_namespace
except ImportError:  # Compatibility with the sibling import path used by tests.
    from scoring.features import extract_features, feature_label, feature_namespace


EXPLANATION_SCHEMA_VERSION = 1

# Row columns engines add for this stage.
MODEL_RANK_COLUMN = "Model Rank"
RANKED_COUNT_COLUMN = "Ranked Candidate Count"
SCORE_PARTS_COLUMN = "Score Parts"
EXPLANATION_COLUMN = "Explanation"

METHOD_EXACT_ADDITIVE = "exact-additive"
METHOD_COUNTERFACTUAL_REMOVAL = "counterfactual-removal"
METHOD_UNAVAILABLE = "unavailable"

KIND_TASTE = "taste"
KIND_COMMUNITY = "community"
KIND_SIMILAR_VIEWERS = "similar-viewers"
KIND_HISTORY_GROUP = "history-group"
KIND_HISTORY_OTHER = "history-other"

# History titles named as the strongest single influences.
INFLUENCE_LIMIT = 5

# Rated titles named per taste part.
EVIDENCE_LIMIT = 3

_FACETS = {"genre": "genre", "studio": "studio", "source": "source", "type": "media-type", "era": "era"}


def unavailable_explanation(reason: str) -> dict:
    """An engine that cannot explain its ranking says so instead of borrowing."""
    return {
        "schema_version": EXPLANATION_SCHEMA_VERSION,
        "method": METHOD_UNAVAILABLE,
        "unit": None,
        "total": None,
        "baseline": None,
        "full_score": None,
        "full_rank": None,
        "ranked_candidate_count": None,
        "history_window": None,
        "segments": [],
        "influences": [],
        "unavailable_reason": reason,
    }


def explain_counterfactual_removal(
    history: Sequence[Mapping[str, object]],
    effect: Mapping[str, object],
    *,
    pool_size: int,
) -> dict:
    """Describe one row's removal effects as a bar of history-genre segments.

    ``history[i]`` describes model-input title ``i`` (``mal_id``, ``title``,
    ``genres``, ``user_score``, ``list_status``). ``effect`` holds the row's
    ``full_score`` and ``full_rank``; ``groups`` as ``(kind, label, members,
    score_drop, rank_without)``; and ``titles[i]`` as ``(score_drop,
    rank_without)``. A score drop is the full-history score minus the score
    without those titles: positive means they raised this pick.
    """
    titles = effect["titles"]
    segments = []
    for kind, label, members, drop, rank_without in effect["groups"]:
        ordered = sorted(
            members,
            key=lambda index: (
                -titles[index][0] if drop >= 0 else titles[index][0],
                str(history[index].get("title") or "").casefold(),
            ),
        )
        segments.append(
            {
                "kind": kind,
                "facet": "genre" if kind == KIND_HISTORY_GROUP else None,
                "label": label,
                "value": float(drop),
                "rank_without": int(rank_without),
                "member_count": len(members),
                "taste": None,
                "feedback_adjustment": None,
                "signal_available": True,
                "community": None,
                "evidence": [
                    _history_evidence(history[index], *titles[index])
                    for index in ordered[:EVIDENCE_LIMIT]
                ],
            }
        )
    segments.sort(key=lambda segment: (-abs(segment["value"]), segment["label"].casefold()))
    strongest = sorted(
        range(len(history)),
        key=lambda index: (
            -abs(titles[index][0]),
            str(history[index].get("title") or "").casefold(),
        ),
    )
    return {
        "schema_version": EXPLANATION_SCHEMA_VERSION,
        "method": METHOD_COUNTERFACTUAL_REMOVAL,
        "unit": "model-score",
        "total": None,
        "baseline": None,
        "full_score": float(effect["full_score"]),
        "full_rank": int(effect["full_rank"]),
        "ranked_candidate_count": int(pool_size),
        # The model reads only the most recent titles; removal is measured
        # over exactly these, never the reader's whole list.
        "history_window": len(history),
        "segments": segments,
        "influences": [
            _history_evidence(history[index], *titles[index])
            for index in strongest[:INFLUENCE_LIMIT]
        ],
        "unavailable_reason": None,
    }


def _history_evidence(title: Mapping[str, object], drop: float, rank_without: int) -> dict:
    return {
        "mal_id": title.get("mal_id"),
        "title": str(title.get("title") or ""),
        "user_score": title.get("user_score"),
        "list_status": title.get("list_status"),
        "value": float(drop),
        "rank_without": int(rank_without),
    }


def explain_additive(
    rows: Sequence[Mapping[str, object]],
    *,
    rated_history: Iterable[Mapping[str, object]] | None = None,
    taste_adjustments: Mapping[str, float] | None = None,
) -> list[dict]:
    """Explain heuristic rows from their recorded score parts.

    ``rated_history`` is the reader's real list with their own scores. Imputed
    scores must not be passed: evidence says "you rated this", so only genuine
    ratings may appear. ``None`` means the rated list is unavailable: taste
    parts then report their counts and averages as unknown, not as zero.
    """
    rated = _rated_titles(rated_history) if rated_history is not None else None
    overall_mean = (
        sum(item["user_score"] for item in rated) / len(rated) if rated else None
    )
    adjustments = {
        str(label).strip().casefold(): float(value)
        for label, value in (taste_adjustments or {}).items()
        if str(label).strip() and value
    }
    return [
        _explain_row(row, rated, overall_mean, adjustments) for row in rows
    ]


def _explain_row(row, rated, overall_mean, adjustments) -> dict:
    parts = row.get(SCORE_PARTS_COLUMN)
    if not isinstance(parts, Mapping):
        return unavailable_explanation("score-parts-missing")

    segments = []
    for feature, value, affinity, idf in parts.get("features") or ():
        namespace = feature_namespace(feature)
        label = feature_label(feature)
        carriers = (
            [item for item in rated if feature in item["features"]]
            if rated is not None
            else []
        )
        scores = [item["user_score"] for item in carriers]
        # Evidence follows the direction the part moved the score: a part that
        # helped names the reader's highest-rated carriers, one that hurt
        # names their lowest-rated ones.
        ordered = sorted(
            carriers,
            key=lambda item: (
                -item["user_score"] if value >= 0 else item["user_score"],
                item["title"].casefold(),
                item["mal_id"] if item["mal_id"] is not None else 0,
            ),
        )
        segments.append(
            {
                "kind": KIND_TASTE,
                "facet": _FACETS.get(namespace),
                "label": label,
                "value": float(value),
                "rank_without": None,
                "member_count": None,
                "taste": {
                    "affinity": float(affinity),
                    "rarity": float(idf),
                    "rated_count": len(carriers) if rated is not None else None,
                    "mean_user_score": (
                        sum(scores) / len(scores) if scores else None
                    ),
                    "overall_mean_user_score": overall_mean,
                },
                "feedback_adjustment": (
                    adjustments.get(label.casefold()) if namespace == "genre" else None
                ),
                "signal_available": True,
                "community": None,
                "evidence": [
                    {
                        "mal_id": item["mal_id"],
                        "title": item["title"],
                        "user_score": item["user_score"],
                        "list_status": None,
                        "value": None,
                        "rank_without": None,
                    }
                    for item in ordered[:EVIDENCE_LIMIT]
                ],
            }
        )

    segments.append(
        {
            "kind": KIND_COMMUNITY,
            "facet": None,
            "label": "Community rating",
            "value": float(parts.get("community") or 0.0),
            "rank_without": None,
            "member_count": None,
            "taste": None,
            "feedback_adjustment": None,
            # False means no usable MAL score: the neutral catalogue prior
            # stood in, and the value is that prior's share.
            "signal_available": bool(parts.get("community_available")),
            "community": {
                "mean_score": _finite(row.get("Mean Score")),
                "scoring_users": _finite(row.get("Scoring Users")),
            },
            "evidence": [],
        }
    )
    # Present whenever the batch blended the signal in, including for a title
    # the graph never reached, so the client can say "no data" for it.
    if parts.get("similar_viewers_in_blend"):
        segments.append(
            {
                "kind": KIND_SIMILAR_VIEWERS,
                "facet": None,
                "label": "Similar viewers",
                "value": float(parts.get("similar_viewers") or 0.0),
                "rank_without": None,
                "member_count": None,
                "taste": None,
                "feedback_adjustment": None,
                "signal_available": bool(parts.get("similar_viewers_available")),
                "community": None,
                "evidence": [],
            }
        )

    return {
        "schema_version": EXPLANATION_SCHEMA_VERSION,
        "method": METHOD_EXACT_ADDITIVE,
        "unit": "ranking-score",
        "total": float(parts.get("total") or 0.0),
        "baseline": 0.0,
        "full_score": float(parts.get("total") or 0.0),
        "full_rank": _positive_int(row.get(MODEL_RANK_COLUMN)),
        "ranked_candidate_count": _positive_int(row.get(RANKED_COUNT_COLUMN)),
        "history_window": None,
        "segments": segments,
        "influences": [],
        "unavailable_reason": None,
    }


def _rated_titles(history: Iterable[Mapping[str, object]]) -> list[dict]:
    rated = []
    for row in history or ():
        score = _finite(row.get("User Score"))
        if score is None or score <= 0:
            continue
        title = str(row.get("Title") or "").strip()
        if not title:
            continue
        mal_id = _finite(row.get("Anime ID"))
        rated.append(
            {
                "mal_id": int(mal_id) if mal_id is not None and mal_id > 0 else None,
                "title": title,
                "user_score": score,
                "features": extract_features(row),
            }
        )
    return rated


def _positive_int(value: object) -> int | None:
    number = _finite(value)
    if number is None or number <= 0 or number != int(number):
        return None
    return int(number)


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
