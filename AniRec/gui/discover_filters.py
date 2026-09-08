"""One state for everything the Discover feed is filtered by.

Before this, a filter was wherever its control happened to live: the genre was
whatever ``genre_filter.currentData()`` returned, the score was a spin box's
value, and nothing else could ask what was active without reaching into a
widget. Adding a second entry point for the same filter - a genre clicked on a
card, say - meant either duplicating that reach or keeping a second copy of the
answer, and a second copy is a copy that drifts.

Every entry point now writes here and every reader reads from here, so
"Psychological" selected from the control and "Psychological" clicked on a card
are not two code paths that agree by inspection, they are one value.

Deliberately Qt-light: a QObject for the one signal, and otherwise plain data
that can be built and asserted without a widget. The *meaning* of a filter -
what the backend does with a studio or a profile - is not decided here; this
only records what the user asked for, in a normalised form.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from PySide6.QtCore import QObject, Signal


class FilterKind(str, Enum):
    """What a filter is about.

    The value doubles as the parameter name sent to whatever answers a query,
    so a filter is normalised the moment it is created rather than translated
    at the boundary.
    """

    GENRE = "genre"
    STUDIO = "studio"
    YEAR = "year"
    SCORE = "score"
    STATUS = "status"
    EPISODES = "episodes"
    PROFILE = "profile"


# The caption a pill carries. Kept beside the kind rather than in the widget so
# a pill, a screen reader and an empty state cannot describe the same filter
# with three different words.
KIND_LABELS = {
    FilterKind.GENRE: "Genre",
    FilterKind.STUDIO: "Studio",
    FilterKind.YEAR: "Year",
    FilterKind.SCORE: "Score",
    FilterKind.STATUS: "Status",
    FilterKind.EPISODES: "Episodes",
    FilterKind.PROFILE: "Profile",
}


class ProfileStatus(str, Enum):
    """Where one added profile is in its own lifecycle.

    A profile filter is the only kind that has to be fetched before it means
    anything, so it is the only kind that can be pending or broken. Keeping
    that on the filter rather than in a parallel dictionary is what lets one
    profile fail without the others noticing.
    """

    PENDING = "pending"
    READY = "ready"
    ERROR = "error"


# The UI's own ceiling on group recommendations, stated once. Five is a limit
# on how many lists a person can meaningfully hold in their head at a time,
# not a backend constraint, so it is communicated inline rather than enforced
# by a failed request.
MAXIMUM_GROUP_PROFILES = 5


@dataclass(frozen=True)
class ActiveFilter:
    """One thing the feed is currently narrowed by.

    ``value`` is what goes to the query and is what identity is decided on;
    ``display_value`` is what a person reads. They differ for anything with a
    machine form - a score range is ``7-10`` and reads as ``7–10``.
    """

    kind: FilterKind
    value: str
    display_value: str = ""
    status: ProfileStatus | None = None
    message: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "value", str(self.value).strip())
        display = str(self.display_value).strip() or self.value
        object.__setattr__(self, "display_value", display)

    @property
    def key(self) -> tuple[str, str]:
        """What makes two filters the same filter.

        Case-folded, because a genre clicked off a card carries whatever case
        the catalogue used and a genre typed into the search box carries
        whatever the reader typed. Two pills reading "Shaft" and "shaft" are
        one filter, and the backend is not asked twice for it.
        """
        return (self.kind.value, self.value.casefold())

    @property
    def label(self) -> str:
        return KIND_LABELS[self.kind]

    @property
    def is_loading(self) -> bool:
        return self.status is ProfileStatus.PENDING

    @property
    def is_failed(self) -> bool:
        return self.status is ProfileStatus.ERROR

    @property
    def counts_toward_query(self) -> bool:
        """Whether this filter should be sent with a request.

        A profile that has not resolved, or that failed to, is a pill on
        screen and nothing more: sending it would either ask for a list that
        is still being fetched or re-ask for one already known to be
        unavailable.
        """
        return self.status in (None, ProfileStatus.READY)


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


def score_filter(minimum: float) -> ActiveFilter:
    """A minimum-MAL-score filter, spelled the way the pill row shows it.

    The machine form keeps the bound the query needs; the display form is the
    range a reader recognises, with an en dash because it is a range and not a
    subtraction.
    """
    bound = f"{float(minimum):g}"
    return ActiveFilter(
        kind=FilterKind.SCORE,
        value=f"{bound}-10",
        display_value=f"{bound}–10",
    )


def episode_filter(minimum: int | None, maximum: int | None) -> ActiveFilter | None:
    """An episode-count band, or nothing when neither end is set."""
    if not minimum and not maximum:
        return None
    if minimum and maximum:
        value = f"{int(minimum)}-{int(maximum)}"
        display = f"{int(minimum)}–{int(maximum)}"
    elif minimum:
        value = f"{int(minimum)}-"
        display = f"{int(minimum)}+"
    else:
        value = f"-{int(maximum)}"
        display = f"up to {int(maximum)}"
    return ActiveFilter(
        kind=FilterKind.EPISODES, value=value, display_value=display
    )
