"""The Discover taste vector: what a reader's ratings say they enjoy and avoid.

The desktop Discover header (``gui/discover_page.py``) reads the same ranking:
the four most positive importance terms and the two most negative. That
ranking mixes genres and studios, which is right for scoring and wrong for a
sentence, so every term is typed here against the feed's own studio
catalogue. A studio is not a genre (``docs/DOMAIN_RULES.md``); the client
words the two kinds differently instead of guessing which is which.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..models.domain import NOT_AVAILABLE, GenreStat

LIKED_LIMIT = 4
AVOIDED_LIMIT = 2


@dataclass(frozen=True)
class TasteTerm:
    term: str
    kind: str  # "genre" or "studio"
    rated_count: int


@dataclass(frozen=True)
class TasteVector:
    liked: tuple[TasteTerm, ...]
    avoided: tuple[TasteTerm, ...]


def taste_vector(stats: Iterable[GenreStat], studio_names: Iterable[str]) -> TasteVector:
    """Select and type the terms exactly as the desktop header does.

    Ordering matches the desktop: a stable sort by descending importance, the
    first positive terms as liked, and the last negative terms (most negative
    first) as avoided. A term the data could not name is skipped rather than
    shown as a taste. An empty vector is a real state - no ranked terms yet -
    and the client says so instead of inventing a sentence.
    """
    studios = {name.strip().casefold() for name in studio_names if name}
    ranked = sorted(
        (stat for stat in stats if stat.genre and stat.genre != NOT_AVAILABLE),
        key=lambda stat: -float(stat.importance_score or 0.0),
    )

    def typed(stat: GenreStat) -> TasteTerm:
        kind = "studio" if stat.genre.strip().casefold() in studios else "genre"
        return TasteTerm(term=stat.genre, kind=kind, rated_count=int(stat.completed_count or 0))

    liked = tuple(
        typed(stat) for stat in ranked if float(stat.importance_score or 0.0) > 0
    )[:LIKED_LIMIT]
    avoided = tuple(
        typed(stat) for stat in reversed(ranked) if float(stat.importance_score or 0.0) < 0
    )[:AVOIDED_LIMIT]
    return TasteVector(liked=liked, avoided=avoided)
