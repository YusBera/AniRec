"""The vocabulary of everything the Discover feed can be narrowed by.

Split out of ``gui/discover_filters.py``, which said of itself that it was
"deliberately Qt-light: a QObject for the one signal, and otherwise plain
data". This module is the plain data half. The QObject that broadcasts a
change stays in the GUI, because a signal is a toolkit's way of saying a
thing happened and every client has its own.

Nothing here knows what a filter *means*. ``FilterKind`` doubles as the
parameter name a query is sent under, so a filter arrives at whatever answers
it already normalised rather than translated at the boundary - which is what
lets the same value travel to a Qt widget, an HTTP query string and a React
control without three spellings of "studio".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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
