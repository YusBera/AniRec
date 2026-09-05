"""The Qt store that broadcasts what the Discover feed is filtered by.

Every entry point writes here and every reader reads from here, so
"Psychological" selected from the control and "Psychological" clicked on a
card are not two code paths that agree by inspection, they are one value.

CHANGE [PRESENTATION-BOUNDARY]: the filter vocabulary itself - the kinds, the
labels, ``ActiveFilter`` and the two constructors that spell a range the way
a pill shows it - moved to ``AniRec.presentation.filters``. It was already
Qt-free, and a second client now needs it without importing a widget toolkit.
What is left here is the one thing that genuinely belongs to Qt: an object
that emits ``changed``. The names are re-exported so existing importers keep
working and so this module still reads as the one place the feed's filter
state lives.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from ..presentation.filters import (
    KIND_LABELS,
    MAXIMUM_GROUP_PROFILES,
    ActiveFilter,
    FilterKind,
    ProfileStatus,
    episode_filter,
    score_filter,
)


class DiscoverFilterState(QObject):
    """The active filters, and the one signal that says they moved.

    Order is insertion order, so the pill row reads in the order the reader
    built it rather than in an order the application chose for them.
    """

    changed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._filters: list[ActiveFilter] = []
        # Set while several changes are applied together, so a control that
        # writes three values does not fire three queries.
        self._muted = 0
        self._dirty = False

    # ---- reading ---------------------------------------------------------

    @property
    def filters(self) -> tuple[ActiveFilter, ...]:
        return tuple(self._filters)

    def __len__(self) -> int:
        return len(self._filters)

    def __bool__(self) -> bool:
        return bool(self._filters)

    def of_kind(self, kind: FilterKind) -> tuple[ActiveFilter, ...]:
        return tuple(item for item in self._filters if item.kind is kind)

    def first_value(self, kind: FilterKind) -> str | None:
        """The single value for a kind the feed only supports one of."""
        for item in self._filters:
            if item.kind is kind:
                return item.value
        return None

    def contains(self, kind: FilterKind, value: str) -> bool:
        wanted = (kind.value, str(value).strip().casefold())
        return any(item.key == wanted for item in self._filters)

    @property
    def profiles(self) -> tuple[ActiveFilter, ...]:
        return self.of_kind(FilterKind.PROFILE)

    @property
    def ready_profiles(self) -> tuple[ActiveFilter, ...]:
        return tuple(
            item for item in self.profiles if item.status is ProfileStatus.READY
        )

    @property
    def group_mode(self) -> bool:
        """Whether the feed is being asked for more than one person.

        A profile that is still loading counts: the request has been made and
        the surface should say so before the answer arrives, or adding a
        profile looks like it did nothing.
        """
        return any(
            item.status in (ProfileStatus.PENDING, ProfileStatus.READY)
            for item in self.profiles
        )

    @property
    def can_add_profile(self) -> bool:
        return len(self.profiles) < MAXIMUM_GROUP_PROFILES

    def query_parameters(self) -> dict[str, list[str]]:
        """The normalised form sent with a request.

        Names come from ``FilterKind``, values are the machine forms, and
        anything not yet resolved is left out. Nothing here decides what a
        parameter *does*; that is the query's business.
        """
        parameters: dict[str, list[str]] = {}
        for item in self._filters:
            if not item.counts_toward_query:
                continue
            parameters.setdefault(item.kind.value, []).append(item.value)
        return parameters

    # ---- writing ---------------------------------------------------------

    def add(self, filter_: ActiveFilter) -> bool:
        """Record a filter, unless it is already recorded.

        Returns whether anything changed, so a caller that wants to say
        "already active" can, without asking twice.
        """
        if not filter_.value:
            return False
        if self.contains(filter_.kind, filter_.value):
            return False
        self._filters.append(filter_)
        self._emit()
        return True

    def add_value(
        self,
        kind: FilterKind,
        value: str,
        *,
        display_value: str = "",
        status: ProfileStatus | None = None,
    ) -> bool:
        return self.add(
            ActiveFilter(
                kind=kind,
                value=value,
                display_value=display_value,
                status=status,
            )
        )

    def set_single(
        self, kind: FilterKind, value: str | None, *, display_value: str = ""
    ) -> bool:
        """Replace every filter of one kind with at most one value.

        For the kinds a feed can only mean one of - a minimum score, an airing
        status - where selecting a second value replaces the first rather than
        adding to it.
        """
        text = str(value or "").strip()
        existing = self.of_kind(kind)
        if text and len(existing) == 1 and existing[0].value == text:
            if existing[0].display_value == (display_value.strip() or text):
                return False
        changed = bool(existing)
        self._filters = [item for item in self._filters if item.kind is not kind]
        if text:
            self._filters.append(
                ActiveFilter(kind=kind, value=text, display_value=display_value)
            )
            changed = True
        if changed:
            self._emit()
        return changed

    def remove(self, kind: FilterKind, value: str) -> bool:
        wanted = (kind.value, str(value).strip().casefold())
        remaining = [item for item in self._filters if item.key != wanted]
        if len(remaining) == len(self._filters):
            return False
        self._filters = remaining
        self._emit()
        return True

    def remove_kind(self, kind: FilterKind) -> bool:
        remaining = [item for item in self._filters if item.kind is not kind]
        if len(remaining) == len(self._filters):
            return False
        self._filters = remaining
        self._emit()
        return True

    def clear(self) -> bool:
        if not self._filters:
            return False
        self._filters = []
        self._emit()
        return True

    def update_profile(
        self,
        value: str,
        *,
        status: ProfileStatus,
        message: str = "",
        display_value: str = "",
    ) -> bool:
        """Move one profile pill to its next state, leaving the others alone.

        This is the whole reason a profile's status lives on the filter: one
        username failing has to be able to say so without touching the pills
        beside it or the results already on screen.
        """
        wanted = (FilterKind.PROFILE.value, str(value).strip().casefold())
        changed = False
        for index, item in enumerate(self._filters):
            if item.key != wanted:
                continue
            updated = replace(
                item,
                status=status,
                message=message,
                display_value=display_value or item.display_value,
            )
            if updated != item:
                self._filters[index] = updated
                changed = True
            break
        if changed:
            self._emit()
        return changed

    # ---- batching --------------------------------------------------------

    def begin_batch(self) -> None:
        """Hold the change signal while several values are written."""
        self._muted += 1

    def end_batch(self) -> None:
        self._muted = max(0, self._muted - 1)
        if self._muted == 0 and self._dirty:
            self._dirty = False
            self.changed.emit()

    def _emit(self) -> None:
        if self._muted:
            self._dirty = True
            return
        self.changed.emit()



__all__ = [
    "KIND_LABELS",
    "MAXIMUM_GROUP_PROFILES",
    "ActiveFilter",
    "DiscoverFilterState",
    "FilterKind",
    "ProfileStatus",
    "episode_filter",
    "score_filter",
]
