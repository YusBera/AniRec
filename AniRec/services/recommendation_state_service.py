"""Profile-local recommendation lists and adaptive taste feedback."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from ..errors import StorageError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.paths import profile_dir
except ImportError:  # Compatibility with legacy top-level imports.
    from errors import StorageError
    from infrastructure.json_storage import JsonStore
    from infrastructure.paths import profile_dir


RECOMMENDATION_STATE_SCHEMA_VERSION = 3


@dataclass(frozen=True)
class RecommendationFeedback:
    """One explicit user preference tied to a stable MyAnimeList anime ID.

    Dormant since schema 3. No control writes one of these any more - the
    like and dislike buttons that did are gone, and Not interested writes to
    ``hidden_mal_ids`` instead. The record, ``set_feedback`` and the two id
    properties below are kept because the ranking engine still accepts a
    taste-adjustment map at its boundary and a future model may want to fill
    it from something better earned than a click on a poster. Loading a
    schema 1 or 2 profile migrates the old records out, so in practice the
    collection is always empty and the adjustments it produces are always
    ``{}``.
    """

    mal_id: int
    sentiment: str
    genres: tuple[str, ...] = ()
    title: str = ""

    def __post_init__(self) -> None:
        mal_id = int(self.mal_id)
        if mal_id <= 0:
            raise ValueError("MAL ID must be a positive integer.")
        sentiment = str(self.sentiment).strip().casefold()
        if sentiment not in {"liked", "disliked"}:
            raise ValueError("Recommendation feedback must be liked or disliked.")
        genres = tuple(
            dict.fromkeys(
                text
                for value in self.genres
                if (text := str(value).strip())
            )
        )
        object.__setattr__(self, "mal_id", mal_id)
        object.__setattr__(self, "sentiment", sentiment)
        object.__setattr__(self, "genres", genres)
        object.__setattr__(self, "title", str(self.title).strip())

    def to_storage_dict(self) -> dict[str, object]:
        return {
            "mal_id": self.mal_id,
            "sentiment": self.sentiment,
            "genres": list(self.genres),
            "title": self.title,
        }

    @classmethod
    def from_storage_dict(cls, payload: object) -> "RecommendationFeedback":
        if not isinstance(payload, dict):
            raise ValueError("Recommendation feedback must be an object.")
        return cls(
            mal_id=payload.get("mal_id"),
            sentiment=payload.get("sentiment"),
            genres=tuple(payload.get("genres") or ()),
            title=payload.get("title") or "",
        )


@dataclass(frozen=True)
class RecommendationLocalState:
    hidden_mal_ids: frozenset[int] = frozenset()
    watch_later_mal_ids: frozenset[int] = frozenset()
    show_hidden: bool = False
    feedback: tuple[RecommendationFeedback, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "hidden_mal_ids", _mal_id_set(self.hidden_mal_ids))
        object.__setattr__(self, "watch_later_mal_ids", _mal_id_set(self.watch_later_mal_ids))
        object.__setattr__(self, "show_hidden", bool(self.show_hidden))
        normalized_feedback = []
        for item in self.feedback:
            record = (
                item
                if isinstance(item, RecommendationFeedback)
                else RecommendationFeedback.from_storage_dict(item)
            )
            normalized_feedback.append(record)
        normalized_feedback.sort(key=lambda item: item.mal_id)
        if len({item.mal_id for item in normalized_feedback}) != len(normalized_feedback):
            raise ValueError("Only one feedback record is allowed per MAL ID.")
        object.__setattr__(self, "feedback", tuple(normalized_feedback))

    @property
    def liked_mal_ids(self) -> frozenset[int]:
        return frozenset(item.mal_id for item in self.feedback if item.sentiment == "liked")

    @property
    def disliked_mal_ids(self) -> frozenset[int]:
        return frozenset(
            item.mal_id for item in self.feedback if item.sentiment == "disliked"
        )

    def to_storage_dict(self) -> dict[str, object]:
        return {
            "schema_version": RECOMMENDATION_STATE_SCHEMA_VERSION,
            "hidden_mal_ids": sorted(self.hidden_mal_ids),
            "watch_later_mal_ids": sorted(self.watch_later_mal_ids),
            "show_hidden": self.show_hidden,
            "feedback": [item.to_storage_dict() for item in self.feedback],
        }

    @classmethod
    def from_storage_dict(cls, payload: object) -> "RecommendationLocalState":
        if not isinstance(payload, dict):
            raise ValueError("Recommendation state root must be an object.")
        schema_version = payload.get("schema_version")
        if schema_version not in {1, 2, RECOMMENDATION_STATE_SCHEMA_VERSION}:
            raise ValueError("Unsupported recommendation state schema version.")
        stored_feedback = tuple(
            RecommendationFeedback.from_storage_dict(item)
            for item in (payload.get("feedback") or ())
        )
        hidden = set(payload.get("hidden_mal_ids") or ())
        # Schema 3 retires explicit like and dislike. A dislike was already an
        # exclusion in everything but name - it was unioned with the hidden set
        # everywhere it was read - so it migrates into that set and keeps the
        # user's intent. A like cannot migrate anywhere honest: it recorded an
        # opinion about a poster, formed before the anime was watched, and
        # there is no longer a control that could take it back. Dropping it is
        # the only reading that does not leave a permanent unremovable vote in
        # the taste model.
        if schema_version in {1, 2}:
            hidden.update(
                record.mal_id
                for record in stored_feedback
                if record.sentiment == "disliked"
            )
            stored_feedback = ()
        return cls(
            hidden_mal_ids=frozenset(hidden),
            watch_later_mal_ids=frozenset(payload.get("watch_later_mal_ids") or ()),
            show_hidden=bool(payload.get("show_hidden", False)),
            feedback=stored_feedback,
        )


class RecommendationStateService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        store: JsonStore | None = None,
    ) -> None:
        self._root_override = root_override
        self._store = store or JsonStore()
        self.last_error: StorageError | None = None

    def path(self, profile_id: str) -> Path:
        return profile_dir(profile_id, self._root_override) / "recommendation_state.json"

    def load(self, profile_id: str) -> RecommendationLocalState:
        self.last_error = None
        path = self.path(profile_id)
        if not path.exists():
            return RecommendationLocalState()
        try:
            return RecommendationLocalState.from_storage_dict(self._store.read(path))
        except (OSError, TypeError, ValueError) as error:
            self.last_error = StorageError(
                "Profile recommendation state could not be loaded safely."
            )
            self.last_error.__cause__ = error
            return RecommendationLocalState()

    def save(
        self, profile_id: str, state: RecommendationLocalState
    ) -> RecommendationLocalState:
        self._store.write(state.to_storage_dict(), self.path(profile_id))
        return state

    def set_hidden(
        self, profile_id: str, mal_id: int, hidden: bool
    ) -> RecommendationLocalState:
        state = self.load(profile_id)
        values = set(state.hidden_mal_ids)
        _update_id(values, mal_id, hidden)
        return self.save(
            profile_id,
            RecommendationLocalState(
                hidden_mal_ids=frozenset(values),
                watch_later_mal_ids=state.watch_later_mal_ids,
                show_hidden=state.show_hidden,
                feedback=state.feedback,
            ),
        )

    def set_watch_later(
        self, profile_id: str, mal_id: int, watch_later: bool
    ) -> RecommendationLocalState:
        state = self.load(profile_id)
        values = set(state.watch_later_mal_ids)
        _update_id(values, mal_id, watch_later)
        return self.save(
            profile_id,
            RecommendationLocalState(
                hidden_mal_ids=state.hidden_mal_ids,
                watch_later_mal_ids=frozenset(values),
                show_hidden=state.show_hidden,
                feedback=state.feedback,
            ),
        )

    def set_show_hidden(
        self, profile_id: str, show_hidden: bool
    ) -> RecommendationLocalState:
        state = self.load(profile_id)
        return self.save(
            profile_id,
            RecommendationLocalState(
                hidden_mal_ids=state.hidden_mal_ids,
                watch_later_mal_ids=state.watch_later_mal_ids,
                show_hidden=show_hidden,
                feedback=state.feedback,
            ),
        )

    def set_feedback(
        self,
        profile_id: str,
        mal_id: int,
        sentiment: str | None,
        *,
        genres: tuple[str, ...] | list[str] = (),
        title: str = "",
    ) -> RecommendationLocalState:
        """Set mutually exclusive feedback, or clear it when sentiment is ``None``."""

        normalized_id = int(mal_id)
        if normalized_id <= 0:
            raise ValueError("MAL ID must be a positive integer.")
        state = self.load(profile_id)
        records = {item.mal_id: item for item in state.feedback}
        if sentiment is None:
            records.pop(normalized_id, None)
        else:
            records[normalized_id] = RecommendationFeedback(
                mal_id=normalized_id,
                sentiment=sentiment,
                genres=tuple(genres),
                title=title,
            )
        return self.save(
            profile_id,
            RecommendationLocalState(
                hidden_mal_ids=state.hidden_mal_ids,
                watch_later_mal_ids=state.watch_later_mal_ids,
                show_hidden=state.show_hidden,
                feedback=tuple(records.values()),
            ),
        )


def _mal_id_set(values) -> frozenset[int]:
    result = set()
    for value in values:
        mal_id = int(value)
        if mal_id <= 0:
            raise ValueError("MAL IDs must be positive integers.")
        result.add(mal_id)
    return frozenset(result)


def _update_id(values: set[int], mal_id: int, enabled: bool) -> None:
    normalized = int(mal_id)
    if normalized <= 0:
        raise ValueError("MAL ID must be a positive integer.")
    if enabled:
        values.add(normalized)
    else:
        values.discard(normalized)
