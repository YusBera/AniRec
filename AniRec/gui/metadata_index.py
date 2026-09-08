"""What the feed can be filtered by, in words a person recognises.

Nobody types a MyAnimeList studio id. So the search box has to be able to turn
"shaft" into the studio Shaft and "psych" into the genre Psychological, which
means something has to hold the names.

That something is deliberately *not* a table of studios shipped in the
frontend. A bundled list would be wrong the day it shipped, would disagree
with whatever the catalogue actually holds, and would put a data source in the
interface layer. The index is built from the records already loaded - every
genre and studio the feed itself carries - so it can only ever offer values
that exist in the data being filtered, and it costs no request.

The limit of that approach is honest and worth stating: it can only see what
has been loaded, so a studio with no title in the current feed is not
findable. The frontend keeps that limitation honest rather than inventing a
second catalogue that can disagree with the loaded data.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .discover_filters import FilterKind


# Suggestions past this point are noise: nobody scrolls a typeahead.
MAXIMUM_SUGGESTIONS = 8

# Below this many characters a prefix match is mostly the whole catalogue.
MINIMUM_QUERY_LENGTH = 1


@dataclass(frozen=True)
class MetadataSuggestion:
    """One thing the search box can offer.

    ``kind`` is carried rather than inferred from the name, because "Mecha" is
    a genre and "Bones" is a studio and nothing about either string says so.
    The reader is told which is which for the same reason.
    """

    kind: FilterKind
    value: str
    occurrences: int = 0

    @property
    def type_label(self) -> str:
        return "Genre" if self.kind is FilterKind.GENRE else "Studio"


class MetadataCatalog:
    """The genres and studios present in whatever has been loaded.

    Counts are kept so the ranking can put a term that describes forty titles
    above one that describes a single title, which is almost always the more
    useful suggestion.
    """

    def __init__(self) -> None:
        self._genres: dict[str, str] = {}
        self._studios: dict[str, str] = {}
        self._genre_counts: dict[str, int] = {}
        self._studio_counts: dict[str, int] = {}

    @property
    def genres(self) -> tuple[str, ...]:
        return tuple(sorted(self._genres.values(), key=str.casefold))

    @property
    def studios(self) -> tuple[str, ...]:
        return tuple(sorted(self._studios.values(), key=str.casefold))

    def __len__(self) -> int:
        return len(self._genres) + len(self._studios)

    def ingest(self, models: Iterable) -> None:
        """Fold whatever a batch of records knows into the index.

        Additive on purpose. The feed is topped up rather than replaced as a
        reader scrolls, and a term that was findable before a top-up should
        not stop being findable after one.
        """
        for model in models or ():
            for raw in getattr(model, "genres", ()) or ():
                self._record(self._genres, self._genre_counts, raw)
            for raw in getattr(model, "studios", ()) or ():
                self._record(self._studios, self._studio_counts, raw)

    @staticmethod
    def _record(names: dict[str, str], counts: dict[str, int], raw: object) -> None:
        text = str(raw or "").strip()
        if not text:
            return
        key = text.casefold()
        # First spelling seen wins, so the suggestion list does not flicker
        # between "Sci-Fi" and "sci-fi" as different pages land.
        names.setdefault(key, text)
        counts[key] = counts.get(key, 0) + 1

    def clear(self) -> None:
        self._genres.clear()
        self._studios.clear()
        self._genre_counts.clear()
        self._studio_counts.clear()

    def search(
        self, query: str, *, limit: int = MAXIMUM_SUGGESTIONS, exclude=()
    ) -> tuple[MetadataSuggestion, ...]:
        """Rank the catalogue against what has been typed so far.

        A prefix match beats a match in the middle of the name, because typing
        "sci" while looking for Sci-Fi should not be answered with Science
        SARU first. Within a tier, the term that covers more of the feed wins,
        and ties fall back to alphabetical so the list is stable between
        keystrokes.
        """
        text = str(query or "").strip().casefold()
        if len(text) < MINIMUM_QUERY_LENGTH:
            return ()
        blocked = {
            (kind.value, str(value).strip().casefold()) for kind, value in exclude or ()
        }

        scored: list[tuple[int, int, str, MetadataSuggestion]] = []
        for kind, names, counts in (
            (FilterKind.GENRE, self._genres, self._genre_counts),
            (FilterKind.STUDIO, self._studios, self._studio_counts),
        ):
            for key, display in names.items():
                if (kind.value, key) in blocked:
                    continue
                if key.startswith(text):
                    tier = 0
                elif text in key:
                    tier = 1
                elif _matches_word_start(key, text):
                    tier = 2
                else:
                    continue
                count = counts.get(key, 0)
                scored.append(
                    (
                        tier,
                        -count,
                        key,
                        MetadataSuggestion(kind=kind, value=display, occurrences=count),
                    )
                )

        scored.sort(key=lambda item: (item[0], item[1], item[2]))
        return tuple(item[3] for item in scored[: max(1, limit)])


def _matches_word_start(name: str, text: str) -> bool:
    """Whether the query starts any word of a multi-word name.

    "saru" should find Science SARU and "animation" should find Kyoto
    Animation, neither of which a prefix or substring tier reaches first.
    """
    return any(part.startswith(text) for part in name.replace("-", " ").split())
