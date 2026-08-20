"""Describe an anime as a set of namespaced feature tokens.

One vocabulary is shared by the taste profile, the ranker, and the
explanation, so a weight learned for a feature always refers to the same
thing wherever it is used.

MyAnimeList's v2 API returns genres, themes, and demographics together in a
single ``genres`` array, so they share the ``genre`` namespace. Axes the API
does keep separate get their own, and each is optional: a row that carries no
studio simply contributes no ``studio`` token, which lets the extractor run
unchanged before and after the catalogue gains those fields.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping

try:
    from ..genre_utils import parse_genres
except ImportError:  # Compatibility with the sibling import path used by tests.
    from genre_utils import parse_genres


GENRE = "genre"
STUDIO = "studio"
SOURCE = "source"
MEDIA_TYPE = "type"
ERA = "era"

NAMESPACES = (GENRE, STUDIO, SOURCE, MEDIA_TYPE, ERA)

_COLUMN_NAMESPACES = (
    ("Genres", GENRE),
    ("Studios", STUDIO),
    ("Source", SOURCE),
    ("Media Type", MEDIA_TYPE),
)


def token(namespace: str, value: str) -> str:
    return f"{namespace}:{value}"


def feature_label(feature: str) -> str:
    """The part of a token a person should read."""
    _namespace, _, value = feature.partition(":")
    return value or feature


def feature_namespace(feature: str) -> str:
    namespace, separator, _value = feature.partition(":")
    return namespace if separator else ""


def _era_token(value: object) -> str | None:
    """Bucket a release year into its decade."""
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    if not 1900 <= year <= 2200:
        return None
    return token(ERA, f"{year // 10 * 10}s")


def extract_features(row: Mapping[str, object]) -> frozenset[str]:
    """Return the feature tokens describing one anime row."""
    features: set[str] = set()
    for column, namespace in _COLUMN_NAMESPACES:
        if column not in row:
            continue
        for value in parse_genres(row.get(column)):
            features.add(token(namespace, value))

    era = _era_token(row.get("Year"))
    if era is not None:
        features.add(era)
    return frozenset(features)


def document_frequencies(rows: Iterable[Mapping[str, object]]) -> dict[str, int]:
    """Count how many catalogue entries carry each feature."""
    counts: dict[str, int] = {}
    for row in rows:
        for feature in extract_features(row):
            counts[feature] = counts.get(feature, 0) + 1
    return counts


def inverse_document_frequency(
    document_count: int,
    frequencies: Mapping[str, int],
) -> dict[str, float]:
    """Weight each feature by how much it distinguishes one anime from another.

    A tag on nearly everything says little about taste, while a rare one says a
    great deal. Values are floored just above zero so that a feature present on
    the entire catalogue still participates instead of silently vanishing.
    """
    total = max(int(document_count), 1)
    return {
        feature: max(math.log(total / (1 + count)), 0.01)
        for feature, count in frequencies.items()
    }
