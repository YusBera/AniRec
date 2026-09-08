"""What the feed needs in order to fold a franchise into one card.

Two facts, both already on disk after a normal run, and neither of them worth
a window reading a CSV to get:

* the relation graph the collaborative signal built, which is what says that
  three recommendations are three parts of one story; and
* every anime the reader has finished, which is what says whether the story
  is new to them.

Both are best effort. A reader with no graph cached simply gets the feed
they have always had - single cards, in order - which is why every failure
here answers with an empty result rather than raising. Folding franchises is
an improvement to the feed, not a precondition for having one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

try:
    from ..infrastructure.csv_storage import CsvStorage
except ImportError:  # Compatibility with the legacy top-level import path.
    from infrastructure.csv_storage import CsvStorage

from .anime_graph_service import AnimeGraphService

COMPLETED_ANIME_FILENAME = "completed_anime.csv"


@dataclass(frozen=True)
class BundleContext:
    """The graph and the watched set, ready for ``build_bundles``."""

    graph: dict = field(default_factory=dict)
    watched_mal_ids: frozenset[int] = frozenset()

    def __bool__(self) -> bool:
        return bool(self.graph)


class BundleContextService:
    """Read the franchise graph and the completed list for one profile."""

    def __init__(
        self,
        *,
        graph_service: AnimeGraphService | None = None,
        storage: CsvStorage | None = None,
    ) -> None:
        self._graph = graph_service or AnimeGraphService()
        self._storage = storage or CsvStorage()

    def load(self, directory: str | Path | None) -> BundleContext:
        if directory is None:
            return BundleContext()
        path = Path(directory)
        return BundleContext(
            graph=self._load_graph(path),
            watched_mal_ids=self._load_watched(path),
        )

    def _load_graph(self, directory: Path) -> dict:
        try:
            return self._graph.load_cache(directory) or {}
        except (OSError, TypeError, ValueError):
            return {}

    def _load_watched(self, directory: Path) -> frozenset[int]:
        """Every id the reader has finished.

        Deliberately the *whole* completed list rather than the exclusion set
        the scorer builds. That set only covers titles rated above the
        reader's own mean and is capped, so trusting it would offer somebody
        "a series you have not started" for a series they watched and
        disliked - which is the one mistake a bundle must not make.
        """
        try:
            completed = self._storage.read(
                directory / COMPLETED_ANIME_FILENAME,
                required_columns=("Anime ID",),
            )
        except (FileNotFoundError, OSError, TypeError, ValueError, pd.errors.ParserError):
            return frozenset()
        if completed is None or completed.empty:
            return frozenset()
        ids = pd.to_numeric(completed.get("Anime ID"), errors="coerce").dropna()
        return frozenset(int(value) for value in ids)
