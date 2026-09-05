"""What the Compare surface renders, and the boundary it renders it from.

The frontend does not decide who is compatible with whom. It cannot: a match
score is a modelling question, a "most different ratings" list is a ranking
question, and both belong with the scoring code that already answers questions
of that shape for the feed. Computing either here would put a second, quieter
recommendation engine inside the interface, and the two would disagree the
first time one of them changed.

So this file holds three things and no arithmetic worth the name:

* the shapes the surface draws - a summary, a section, an entry;
* a ``CompatibilityProvider`` protocol, which is the whole of what the
  interface asks of whatever answers it;
* two providers that exist today. One reports that the capability is not
  built yet, in a form the surface can render honestly. The other replays a
  recorded response so the surface can be seen, reviewed and tested - the same
  bargain ``SampleDataService`` already makes for the feed, and stamped SAMPLE
  in the same way.

The response shape is the shape below, written from what the surface needs
rather than from what happens to be convenient to compute.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from ..infrastructure.paths import resource_path
from ..models import Anime, Recommendation
from .recommendation_view_model import (
    RecommendationViewModel,
    recommendation_view_models,
)


class UnavailableReason(str, Enum):
    """Why a comparison could not be produced.

    These are separate values rather than one failure because the surface says
    something different for each, and a reader can act on some and not others.
    "This person's list is private" is not a fault a retry fixes; "MyAnimeList
    is unreachable" is.
    """

    BACKEND_MISSING = "backend-missing"
    USER_NOT_FOUND = "user-not-found"
    PRIVATE_LIST = "private-list"
    FRIENDS_PRIVATE = "friends-private"
    NOT_CONNECTED = "not-connected"
    API_UNAVAILABLE = "api-unavailable"
    NETWORK = "network"


class CompatibilityUnavailable(Exception):
    """A comparison the backend could not answer, with the reason kept."""

    def __init__(self, reason: UnavailableReason, message: str = "") -> None:
        super().__init__(message or reason.value)
        self.reason = reason
        self.message = message


@dataclass(frozen=True)
class ComparisonScores:
    """The two opinions on one anime, and the gap between them.

    ``difference`` is carried rather than subtracted here on purpose. It is
    the backend's figure, so a service that later weights a disagreement by
    how confident each rating is can send that instead, and this keeps
    working. The frontend only formats it.
    """

    your_score: float | None = None
    friend_score: float | None = None
    difference: float | None = None
    mal_score: float | None = None

    @staticmethod
    def _format(value: float | None) -> str:
        return "N/A" if value is None else f"{float(value):.0f}"

    @property
    def your_score_text(self) -> str:
        return self._format(self.your_score)

    @property
    def friend_score_text(self) -> str:
        return self._format(self.friend_score)

    @property
    def mal_score_text(self) -> str:
        return "N/A" if self.mal_score is None else f"{float(self.mal_score):.2f}"

    @property
    def difference_text(self) -> str:
        if self.difference is None:
            return "N/A"
        return f"{abs(float(self.difference)):.0f}"

    @property
    def agreement(self) -> str:
        """How far apart the two are, as a word the stylesheet can read.

        Three bands, not a colour ramp. The point of this row is which anime
        to talk about, not to rank disagreements to one decimal place, and a
        continuous red-to-green gradient over a pair of numbers is a trading
        terminal.
        """
        if self.difference is None:
            return "unknown"
        gap = abs(float(self.difference))
        if gap <= 1:
            return "close"
        if gap <= 3:
            return "apart"
        return "opposed"


@dataclass(frozen=True)
class ComparisonEntry:
    """One anime in one comparison section."""

    model: RecommendationViewModel
    scores: ComparisonScores = field(default_factory=ComparisonScores)


@dataclass(frozen=True)
class ComparisonSection:
    """A prepared, already-ordered run of anime with a heading.

    The frontend does not sort or filter these. Membership and order are the
    backend's answer to a question the backend asked; re-ranking them here
    would mean the heading no longer describes the contents.
    """

    section_id: str
    title: str
    description: str = ""
    entries: tuple[ComparisonEntry, ...] = ()
    empty_message: str = ""

    def __bool__(self) -> bool:
        return bool(self.entries)


@dataclass(frozen=True)
class FriendSummary:
    """Who was compared, and the headline figures for the comparison."""

    username: str
    match_score: float | None = None
    match_label: str = ""
    total_anime: int | None = None
    shared_anime: int | None = None
    both_rated: int | None = None
    profile_url: str | None = None

    @property
    def match_score_text(self) -> str:
        return "N/A" if self.match_score is None else f"{float(self.match_score):.0f}%"

    @staticmethod
    def count_text(value: int | None) -> str:
        return "N/A" if value is None else f"{int(value):,}"


@dataclass(frozen=True)
class CompatibilityReport:
    """Everything one comparison puts on screen."""

    friend: FriendSummary
    sections: tuple[ComparisonSection, ...] = ()
    # Set when the figures came from a recorded response rather than from a
    # live account, so the surface can say so instead of implying otherwise.
    is_sample: bool = False


@dataclass(frozen=True)
class FriendEntry:
    """One name in the logged-in user's public friends list."""

    username: str
    profile_url: str | None = None


class CompatibilityProvider(Protocol):
    """The whole of what the Compare surface asks for.

    Two calls. Both may raise ``CompatibilityUnavailable``; neither may
    return partial nonsense, because a surface cannot tell the difference
    between "no shared anime" and "we did not manage to look".
    """

    def friends(self) -> tuple[FriendEntry, ...]:
        """The logged-in user's public friends, or a stated reason there are none."""

    def compare(self, username: str) -> CompatibilityReport:
        """A prepared comparison against one MyAnimeList username."""


class UnavailableCompatibilityProvider:
    """The provider in force until a real one exists.

    It refuses rather than inventing, and it refuses with a reason, so the
    surface renders a truthful state instead of an empty one that looks like a
    bug. This is what ships wired up: nothing about the Compare surface
    pretends to have data it does not have.
    """

    def __init__(
        self, reason: UnavailableReason = UnavailableReason.BACKEND_MISSING
    ) -> None:
        self._reason = reason

    def friends(self) -> tuple[FriendEntry, ...]:
        raise CompatibilityUnavailable(self._reason)

    def compare(self, username: str) -> CompatibilityReport:
        raise CompatibilityUnavailable(self._reason)


SAMPLE_COMPATIBILITY_RESOURCE = "gui/resources/sample/sample_compatibility.json"


class SampleCompatibilityProvider:
    """Replay a recorded comparison, so the surface can be judged before it exists.

    The file it reads is a captured response in the documented shape, not a
    calculation: nothing here decides who matches whom, it only parses. That
    distinction matters, because a "sample" that computed its own answers
    would be a second implementation of the thing this deliberately does not
    implement.

    Everything it returns is flagged ``is_sample``, and the surface stamps it,
    for the same reason the feed's sample library carries a banner.
    """

    def __init__(self, *, base_override: str | Path | None = None) -> None:
        self._base_override = base_override
        self._payload: dict | None = None

    def _load(self) -> dict:
        if self._payload is None:
            try:
                path = resource_path(
                    SAMPLE_COMPATIBILITY_RESOURCE, base_override=self._base_override
                )
                self._payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError) as error:
                raise CompatibilityUnavailable(
                    UnavailableReason.BACKEND_MISSING,
                    "The bundled sample comparison could not be read.",
                ) from error
        return self._payload

    def friends(self) -> tuple[FriendEntry, ...]:
        payload = self._load()
        return tuple(
            FriendEntry(
                username=str(item.get("username") or "").strip(),
                profile_url=item.get("profile_url"),
            )
            for item in payload.get("friends") or ()
            if str(item.get("username") or "").strip()
        )

    def compare(self, username: str) -> CompatibilityReport:
        payload = self._load()
        wanted = str(username or "").strip().casefold()
        for record in payload.get("comparisons") or ():
            friend = record.get("friend") or {}
            if str(friend.get("username") or "").casefold() == wanted:
                return report_from_payload(record, is_sample=True)
        # A sample set holds a handful of names. Anything else is genuinely
        # not there, and saying so is more useful than substituting one of the
        # names that is.
        raise CompatibilityUnavailable(
            UnavailableReason.USER_NOT_FOUND,
            f"{username} is not part of the bundled sample data.",
        )


# ---------------------------------------------------------------------------
# Parsing
#
# One function, used by every provider, so a live backend and a recorded
# response cannot drift into two readings of the same document.
# ---------------------------------------------------------------------------


def report_from_payload(payload, *, is_sample: bool = False) -> CompatibilityReport:
    """Build a report from the documented JSON shape.

    Tolerant in the way a boundary has to be: a missing count becomes "N/A"
    rather than a crash, and an entry with no anime attached is dropped rather
    than rendered as a card about nothing. It is not tolerant about identity -
    a comparison with no username is not a comparison.
    """
    record = payload if isinstance(payload, dict) else {}
    friend_data = record.get("friend") or {}
    friend = FriendSummary(
        username=str(friend_data.get("username") or "").strip(),
        match_score=_number(friend_data.get("match_score")),
        match_label=str(friend_data.get("match_label") or "").strip(),
        total_anime=_count(friend_data.get("total_anime")),
        shared_anime=_count(friend_data.get("shared_anime")),
        both_rated=_count(friend_data.get("both_rated")),
        profile_url=friend_data.get("profile_url"),
    )

    sections = []
    for item in record.get("sections") or ():
        if not isinstance(item, dict):
            continue
        entries = tuple(
            entry
            for raw in item.get("entries") or ()
            if (entry := _entry_from_payload(raw)) is not None
        )
        sections.append(
            ComparisonSection(
                section_id=str(item.get("id") or "").strip() or "section",
                title=str(item.get("title") or "").strip(),
                description=str(item.get("description") or "").strip(),
                entries=entries,
                empty_message=str(item.get("empty_message") or "").strip(),
            )
        )
    return CompatibilityReport(
        friend=friend, sections=tuple(sections), is_sample=is_sample
    )


def _entry_from_payload(raw) -> ComparisonEntry | None:
    if not isinstance(raw, dict):
        return None
    anime_data = raw.get("anime")
    if not isinstance(anime_data, dict):
        return None
    title = str(anime_data.get("title") or "").strip()
    if not title:
        return None
    anime = Anime(
        title=title,
        mal_id=_count(anime_data.get("mal_id")),
        english_title=anime_data.get("english_title"),
        genres=tuple(anime_data.get("genres") or ()),
        studios=tuple(anime_data.get("studios") or ()),
        mean_score=_number(anime_data.get("mean_score")),
        cover_url=anime_data.get("cover_url"),
        large_cover_url=anime_data.get("large_cover_url"),
        episodes=_count(anime_data.get("episodes")),
        status=anime_data.get("status"),
        year=_count(anime_data.get("year")),
        synopsis=anime_data.get("synopsis"),
        mal_url=anime_data.get("mal_url"),
        media_type=anime_data.get("media_type"),
    )
    # The card is driven by the same view model the feed uses, so a comparison
    # card and a Discover card cannot describe the same anime differently.
    model = recommendation_view_models(
        (Recommendation(anime=anime, match_score=_number(raw.get("match_score")) or 0.0),)
    )[0]
    scores = raw.get("scores") if isinstance(raw.get("scores"), dict) else {}
    return ComparisonEntry(
        model=model,
        scores=ComparisonScores(
            your_score=_number(scores.get("your_score")),
            friend_score=_number(scores.get("friend_score")),
            difference=_number(scores.get("difference")),
            mal_score=_number(scores.get("mal_score"))
            if scores.get("mal_score") is not None
            else _number(anime_data.get("mean_score")),
        ),
    )


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None


def _count(value) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def sections_from(report: CompatibilityReport) -> Sequence[ComparisonSection]:
    return report.sections
