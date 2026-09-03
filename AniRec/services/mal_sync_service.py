"""Read-only reconciliation between AniRec's local lists and MyAnimeList.

The loop this closes is the one the interface could never see. AniRec knows
what it recommended and what the reader saved for later; MyAnimeList knows
what they went on to watch and what they thought of it. Nothing joined the
two, so a saved title sat in Watch Later forever even after it had been
finished and rated somewhere else.

Three deliberate limits, each of which is a decision rather than an omission.

*Read only.* Nothing here writes to anybody's MyAnimeList account. Writing a
score needs the ``write:users`` scope, which is an escalation from the public
Client ID flow the rest of the application runs on, and it is an outward
change to a third party's data. Detecting a completion needs neither. The
write path is a separate, opt-in piece of work; this one delivers most of the
value without asking for anything new.

*Attribution is the save, not the sight.* A completion is credited to AniRec
only when the reader saved that title from an AniRec card - that is what
``watch_later_mal_ids`` already means, since the only thing that writes to it
is the Later control. Seeing a recommendation and then finding the show
somewhere else is not evidence AniRec caused anything, and claiming it would
be the application flattering itself.

*State is a snapshot, not an event log.* What is stored is the set of
completions currently worth telling somebody about, recomputed on every sync,
plus which ones they have already acknowledged. An append-only log of sync
events would grow forever and would re-announce everything the first time a
cache was cleared.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

try:
    from ..errors import StorageError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.paths import profile_dir
    from ..user_data import fetch_recent_list_entries
except ImportError:  # Compatibility with legacy top-level imports.
    from errors import StorageError
    from infrastructure.json_storage import JsonStore
    from infrastructure.paths import profile_dir
    from user_data import fetch_recent_list_entries


MAL_SYNC_STATE_SCHEMA_VERSION = 1

# MyAnimeList uses 0 for "on the list, no score given". It is not a rating of
# zero, and the difference is the whole point of the unscored prompt.
UNSCORED = 0

COMPLETED_STATUS = "completed"


@dataclass(frozen=True)
class MalListEntry:
    """One entry of somebody's MyAnimeList list, as the sync walk saw it."""

    mal_id: int
    title: str
    status: str
    score: int
    updated_at: str
    episodes_watched: int = 0

    def __post_init__(self) -> None:
        mal_id = int(self.mal_id)
        if mal_id <= 0:
            raise ValueError("MAL ID must be a positive integer.")
        object.__setattr__(self, "mal_id", mal_id)
        object.__setattr__(self, "title", str(self.title).strip())
        object.__setattr__(self, "status", str(self.status).strip().casefold())
        object.__setattr__(self, "score", max(0, int(self.score or 0)))
        object.__setattr__(self, "episodes_watched", max(0, int(self.episodes_watched or 0)))
        object.__setattr__(self, "updated_at", str(self.updated_at).strip())

    @property
    def is_completed(self) -> bool:
        return self.status == COMPLETED_STATUS

    @property
    def is_unscored(self) -> bool:
        return self.score == UNSCORED

    @classmethod
    def from_payload(cls, payload: object) -> "MalListEntry":
        if not isinstance(payload, dict):
            raise ValueError("A list entry must be an object.")
        return cls(
            mal_id=payload.get("mal_id"),
            title=payload.get("title") or "",
            status=payload.get("status") or "",
            score=payload.get("score") or 0,
            updated_at=payload.get("updated_at") or "",
            episodes_watched=payload.get("episodes_watched") or 0,
        )


@dataclass(frozen=True)
class SyncedCompletion:
    """A finished anime the reader has not been told about yet.

    ``from_watch_later`` is the attribution: true when this title was saved
    from an AniRec card before it was finished. Only those may be described as
    something AniRec recommended.
    """

    mal_id: int
    title: str
    score: int
    completed_at: str
    from_watch_later: bool = False

    def __post_init__(self) -> None:
        mal_id = int(self.mal_id)
        if mal_id <= 0:
            raise ValueError("MAL ID must be a positive integer.")
        object.__setattr__(self, "mal_id", mal_id)
        object.__setattr__(self, "title", str(self.title).strip())
        object.__setattr__(self, "score", max(0, int(self.score or 0)))
        object.__setattr__(self, "completed_at", str(self.completed_at).strip())
        object.__setattr__(self, "from_watch_later", bool(self.from_watch_later))

    @property
    def needs_score(self) -> bool:
        return self.score == UNSCORED

    def to_storage_dict(self) -> dict[str, object]:
        return {
            "mal_id": self.mal_id,
            "title": self.title,
            "score": self.score,
            "completed_at": self.completed_at,
            "from_watch_later": self.from_watch_later,
        }

    @classmethod
    def from_storage_dict(cls, payload: object) -> "SyncedCompletion":
        if not isinstance(payload, dict):
            raise ValueError("A completion record must be an object.")
        return cls(
            mal_id=payload.get("mal_id"),
            title=payload.get("title") or "",
            score=payload.get("score") or 0,
            completed_at=payload.get("completed_at") or "",
            from_watch_later=payload.get("from_watch_later", False),
        )


@dataclass(frozen=True)
class MalSyncState:
    """What the last sync learned, and what the reader has already seen.

    ``watermark`` is the newest ``updated_at`` any sync has observed. It is
    stored exactly as MyAnimeList wrote it and never reformatted, because it
    is compared as a string against values from the same source.
    """

    watermark: str | None = None
    last_synced_at: str | None = None
    completions: tuple[SyncedCompletion, ...] = ()
    acknowledged_mal_ids: frozenset[int] = frozenset()

    def __post_init__(self) -> None:
        records = []
        for item in self.completions:
            record = (
                item
                if isinstance(item, SyncedCompletion)
                else SyncedCompletion.from_storage_dict(item)
            )
            records.append(record)
        records.sort(key=lambda item: (item.completed_at, item.mal_id), reverse=True)
        if len({item.mal_id for item in records}) != len(records):
            raise ValueError("Only one completion record is allowed per MAL ID.")
        object.__setattr__(self, "completions", tuple(records))
        acknowledged = set()
        for value in self.acknowledged_mal_ids:
            mal_id = int(value)
            if mal_id <= 0:
                raise ValueError("MAL IDs must be positive integers.")
            acknowledged.add(mal_id)
        object.__setattr__(self, "acknowledged_mal_ids", frozenset(acknowledged))

    @property
    def unacknowledged(self) -> tuple[SyncedCompletion, ...]:
        """What there is to tell the reader, newest first."""
        return tuple(
            item
            for item in self.completions
            if item.mal_id not in self.acknowledged_mal_ids
        )

    @property
    def unscored(self) -> tuple[SyncedCompletion, ...]:
        """Finished, credited to AniRec, and never rated.

        Restricted to titles saved from AniRec on purpose. Prompting somebody
        about every unrated thing on their MyAnimeList list would be AniRec
        appointing itself editor of an account it only reads.
        """
        return tuple(
            item
            for item in self.unacknowledged
            if item.needs_score and item.from_watch_later
        )

    def to_storage_dict(self) -> dict[str, object]:
        return {
            "schema_version": MAL_SYNC_STATE_SCHEMA_VERSION,
            "watermark": self.watermark,
            "last_synced_at": self.last_synced_at,
            "completions": [item.to_storage_dict() for item in self.completions],
            "acknowledged_mal_ids": sorted(self.acknowledged_mal_ids),
        }

    @classmethod
    def from_storage_dict(cls, payload: object) -> "MalSyncState":
        if not isinstance(payload, dict):
            raise ValueError("Sync state root must be an object.")
        if payload.get("schema_version") != MAL_SYNC_STATE_SCHEMA_VERSION:
            raise ValueError("Unsupported MAL sync state schema version.")
        watermark = payload.get("watermark")
        last_synced_at = payload.get("last_synced_at")
        return cls(
            watermark=str(watermark) if isinstance(watermark, str) else None,
            last_synced_at=(
                str(last_synced_at) if isinstance(last_synced_at, str) else None
            ),
            completions=tuple(
                SyncedCompletion.from_storage_dict(item)
                for item in (payload.get("completions") or ())
            ),
            acknowledged_mal_ids=frozenset(payload.get("acknowledged_mal_ids") or ()),
        )


def reconcile(
    state: MalSyncState,
    entries,
    *,
    watch_later_mal_ids: frozenset[int],
    synced_at: str,
) -> tuple[MalSyncState, frozenset[int]]:
    """Fold a walk of list entries into the state, and say what to un-save.

    Pure: no network, no disk, no clock. Everything the decision depends on
    arrives as an argument, which is what lets the interesting cases be tested
    without a MyAnimeList account or a fixed date.

    Returns the new state and the set of MAL ids that should leave Watch
    Later, because they have now been watched. The caller owns that list, so
    this reports rather than reaches into it.

    Two rules are worth stating out loud:

    * Only completions are recorded. A title moved to watching, dropped or on
      hold has not produced anything to say, but it still advances the
      watermark, so the next walk does not re-read it.
    * A later observation replaces an earlier one for the same title. Somebody
      who finishes an anime and scores it the next day appears twice across
      two syncs, and the second is the true one.
    """
    known = {item.mal_id: item for item in state.completions}
    watermark = state.watermark
    finished = set()

    for entry in entries:
        record = entry if isinstance(entry, MalListEntry) else MalListEntry.from_payload(entry)
        if watermark is None or record.updated_at > watermark:
            watermark = record.updated_at
        if not record.is_completed:
            continue
        finished.add(record.mal_id)
        previous = known.get(record.mal_id)
        # Attribution is decided once, when the completion is first seen, and
        # then carried. Watch Later is emptied as titles are watched, so
        # re-deriving it on a later sync would quietly demote a completion
        # AniRec really did earn.
        from_watch_later = (
            previous.from_watch_later
            if previous is not None
            else record.mal_id in watch_later_mal_ids
        )
        known[record.mal_id] = SyncedCompletion(
            mal_id=record.mal_id,
            title=record.title or (previous.title if previous else ""),
            score=record.score,
            completed_at=record.updated_at,
            from_watch_later=from_watch_later,
        )

    updated = replace(
        state,
        watermark=watermark,
        last_synced_at=synced_at,
        completions=tuple(known.values()),
    )
    return updated, frozenset(finished & watch_later_mal_ids)


class MalSyncService:
    """Persist per-profile sync state and run a walk against MyAnimeList."""

    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        store: JsonStore | None = None,
        fetcher=fetch_recent_list_entries,
    ) -> None:
        self._root_override = root_override
        self._store = store or JsonStore()
        self._fetcher = fetcher
        self.last_error: StorageError | None = None

    def path(self, profile_id: str) -> Path:
        return profile_dir(profile_id, self._root_override) / "mal_sync_state.json"

    def load(self, profile_id: str) -> MalSyncState:
        self.last_error = None
        path = self.path(profile_id)
        if not path.exists():
            return MalSyncState()
        try:
            return MalSyncState.from_storage_dict(self._store.read(path))
        except (OSError, TypeError, ValueError) as error:
            # A sync state that cannot be read is not worth failing a launch
            # over. Starting from empty costs one full walk and nothing else.
            self.last_error = StorageError(
                "Profile MyAnimeList sync state could not be loaded safely."
            )
            self.last_error.__cause__ = error
            return MalSyncState()

    def save(self, profile_id: str, state: MalSyncState) -> MalSyncState:
        self._store.write(state.to_storage_dict(), self.path(profile_id))
        return state

    def acknowledge(self, profile_id: str, mal_ids) -> MalSyncState:
        """Mark completions as seen, so they stop being announced."""
        state = self.load(profile_id)
        acknowledged = set(state.acknowledged_mal_ids)
        acknowledged.update(int(value) for value in mal_ids)
        # Only ids that actually have a record are kept, so acknowledgements
        # for titles dropped from the snapshot do not accumulate forever.
        known = {item.mal_id for item in state.completions}
        return self.save(
            profile_id,
            replace(state, acknowledged_mal_ids=frozenset(acknowledged & known)),
        )

    def sync(
        self,
        profile_id: str,
        username: str,
        *,
        watch_later_mal_ids: frozenset[int] = frozenset(),
        synced_at: str,
        access_token: str | None = None,
        client_id: str | None = None,
        include_nsfw: bool = False,
        cancellation_token=None,
    ) -> tuple[MalSyncState, frozenset[int]]:
        """Walk the changed head of a list and fold it into the stored state.

        Network errors are not caught here. A sync that could not reach
        MyAnimeList must not advance the watermark or claim a sync time, and
        the caller is the only place that knows whether to report that to
        somebody or let a background attempt fail quietly.
        """
        state = self.load(profile_id)
        entries = self._fetcher(
            username,
            access_token,
            client_id=client_id,
            since=state.watermark,
            include_nsfw=include_nsfw,
            cancellation=cancellation_token,
        )
        updated, watched = reconcile(
            state,
            entries,
            watch_later_mal_ids=watch_later_mal_ids,
            synced_at=synced_at,
        )
        return self.save(profile_id, updated), watched
