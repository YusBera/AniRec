"""What the Profile surface renders, and the boundary it renders it from.

The frontend does not work out what kind of viewer somebody is. It cannot:
"how closely do your scores track the community", "which of your ratings are
contrarian", "which popular titles did you reject" and "which genre do you
score most inconsistently" are all questions about a whole library measured
against MyAnimeList's own aggregates. Answering them here would put a second,
quieter statistics engine inside the interface, one that would disagree with
the real one the first time either changed.

So this file holds the same three things ``compatibility.py`` holds, for the
same reasons:

* the shapes the surface draws - an identity, a reading, a verdict, a bucket;
* a ``TasteProfileProvider`` protocol, which is the whole of what the surface
  asks of whatever answers it;
* the providers available today. The local provider adapts statistics derived
  from synchronized MAL snapshots, the unavailable provider reports why that
  data cannot be read, and the sample provider replays a recorded response so
  the surface can be seen and tested without claiming those figures are real.

The one exception to "no arithmetic" is deliberate and narrow. Mean, median,
mode and scale usage are read straight off the rating histogram that arrives
in the payload: they are not modelling questions, they are four ways of
looking at ten numbers the reader can already see on the page, and computing
them at the point of display is what keeps them from ever contradicting the
bars above them. They are cached on the dataclass rather than recomputed per
paint - the same reason a React surface would reach for ``useMemo``.

Everything else - sync, bias, contrarian index, mainstream index, genre and
studio verdicts, era and season averages, the rating timeline - is carried
verbatim from the provider and only formatted here.

The local provider now supplies the score histogram, community comparisons,
per-genre and per-studio summaries, and air-year and season analysis. A later
sync schema still needs full list-status counts, popularity rank, profile
metadata, rewatch counts, and rating timestamps before watching habits,
hidden gems, and taste-through-time can be measured honestly. See
docs/design/BACKEND_HANDOFF.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path
from typing import Protocol

from ..infrastructure.paths import resource_path
from ..services.taste_profile_service import (
    ProfileStatisticsService,
    ProfileStatisticsUnavailable,
    ProfileStatisticsUnavailableReason,
)
from .compatibility import UnavailableReason


class TasteProfileUnavailable(Exception):
    """A taste profile the backend could not produce, with the reason kept.

    Shares ``UnavailableReason`` with Compare rather than defining a second
    vocabulary: "your list is private" and "MyAnimeList is unreachable" mean
    the same thing on both surfaces, and the interface decides whether to
    offer a retry from the same table either way.
    """

    def __init__(self, reason: UnavailableReason, message: str = "") -> None:
        super().__init__(message or reason.value)
        self.reason = reason
        self.message = message


# ---------------------------------------------------------------------------
# Shapes
#
# Written from what the surface needs to draw, not from what happens to be
# convenient to compute. Every optional figure formats to N/A rather than to
# zero, because "we did not measure this" and "this measured zero" are
# different facts and a readout that confuses them is worse than blank.
# ---------------------------------------------------------------------------


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


def _text(value) -> str:
    return str(value or "").strip()


def _fraction(value) -> float | None:
    """A 0-1 position on a rail, bounded so a bad figure cannot overdraw."""
    number = _number(value)
    if number is None:
        return None
    return max(0.0, min(1.0, number))


DASH = "N/A"


def count_text(value: int | None) -> str:
    return DASH if value is None else f"{int(value):,}"


def score_text(value: float | None, places: int = 1) -> str:
    return DASH if value is None else f"{float(value):.{places}f}"


@dataclass(frozen=True)
class ProfileIdentity:
    """Who this profile belongs to, and the four counts behind it."""

    username: str = ""
    avatar_url: str | None = None
    member_since: str = ""
    profile_url: str | None = None
    completed: int | None = None
    episodes: int | None = None
    days_watched: float | None = None
    mean_score: float | None = None

    @property
    def initials(self) -> str:
        """Fallback avatar text: at most two letters from the username.

        A MAL username is one token, so there is rarely a second word to take
        a letter from; first and last character of the alphanumeric run keeps
        it stable and avoids rendering an underscore as an initial.
        """
        letters = [character for character in self.username if character.isalnum()]
        if not letters:
            return "??"
        if len(letters) == 1:
            return letters[0].upper()
        return (letters[0] + letters[-1]).upper()

    @property
    def days_text(self) -> str:
        return DASH if self.days_watched is None else f"{float(self.days_watched):.1f}"

    @property
    def mean_text(self) -> str:
        return score_text(self.mean_score, 2)


@dataclass(frozen=True)
class FingerprintReading:
    """One statistic in the taste fingerprint.

    ``readout`` names which instrument draws it - a bank of cells for a
    proportion, a two-ended rail for a position between two named extremes -
    because the choice belongs with the figure, not with the layout code.
    """

    reading_id: str
    caption: str
    value_text: str = DASH
    label: str = ""
    detail: str = ""
    position: float | None = None
    scale_low: str = ""
    scale_high: str = ""
    readout: str = "cells"
    tone: str = ""

    @property
    def accessible_text(self) -> str:
        """One sentence carrying everything the three visual rows carry.

        A screen reader that reads "COMMUNITY SYNC", "72%" and "MOSTLY
        ALIGNED" as three unrelated labels has lost the reading; this joins
        them, and it is also what stops the meaning resting on colour alone.
        """
        parts = [self.caption.title(), self.value_text]
        if self.label:
            parts.append(self.label.lower())
        sentence = ", ".join(part for part in parts if part)
        return f"{sentence}. {self.detail}" if self.detail else sentence


@dataclass(frozen=True)
class RatingBucket:
    score: int
    count: int = 0


@dataclass(frozen=True)
class RatingDistribution:
    """The 1-10 histogram, and the four figures read off it.

    The buckets arrive from the provider. Mean, median, mode and scale usage
    are derived here - see the module docstring for why these four and no
    others - and cached, so a resize does not recompute them.
    """

    buckets: tuple[RatingBucket, ...] = ()

    def __bool__(self) -> bool:
        return any(bucket.count for bucket in self.buckets)

    @cached_property
    def ordered(self) -> tuple[RatingBucket, ...]:
        """Highest score first, which is the way the chart reads down."""
        return tuple(sorted(self.buckets, key=lambda bucket: -bucket.score))

    @cached_property
    def total(self) -> int:
        return sum(bucket.count for bucket in self.buckets)

    @cached_property
    def peak(self) -> int:
        """The tallest bar, which every other bar is drawn as a share of."""
        return max((bucket.count for bucket in self.buckets), default=0)

    @cached_property
    def mean(self) -> float | None:
        if not self.total:
            return None
        weighted = sum(bucket.score * bucket.count for bucket in self.buckets)
        return weighted / self.total

    @cached_property
    def median(self) -> float | None:
        if not self.total:
            return None
        target = (self.total + 1) / 2
        seen = 0
        for bucket in sorted(self.buckets, key=lambda bucket: bucket.score):
            seen += bucket.count
            if seen >= target:
                return float(bucket.score)
        return None

    @cached_property
    def mode(self) -> int | None:
        if not self.total:
            return None
        return max(self.buckets, key=lambda bucket: (bucket.count, bucket.score)).score

    @cached_property
    def scale_usage(self) -> tuple[int, int]:
        """How many of the ten scores this reader has ever actually used."""
        return (
            sum(1 for bucket in self.buckets if bucket.count),
            len(self.buckets) or 10,
        )

    @property
    def mean_text(self) -> str:
        return score_text(self.mean, 2)

    @property
    def median_text(self) -> str:
        median = self.median
        return DASH if median is None else f"{median:.0f}"

    @property
    def mode_text(self) -> str:
        return DASH if self.mode is None else f"{self.mode:d}"

    @property
    def scale_usage_text(self) -> str:
        used, available = self.scale_usage
        return f"{used} / {available}"


@dataclass(frozen=True)
class TitleVerdict:
    """One anime and the two opinions on it.

    ``delta`` is carried rather than subtracted here for the same reason
    ``ComparisonScores.difference`` is: a backend that later weights a
    disagreement by how many people rated it can send that instead, and this
    keeps working.
    """

    title: str
    mal_id: int | None = None
    cover_url: str | None = None
    your_score: float | None = None
    community_score: float | None = None
    delta: float | None = None
    popularity_rank: int | None = None
    ranked_position: int | None = None
    year: int | None = None

    @property
    def your_score_text(self) -> str:
        return DASH if self.your_score is None else f"{float(self.your_score):.0f}"

    @property
    def community_score_text(self) -> str:
        return score_text(self.community_score, 2)

    @property
    def delta_text(self) -> str:
        if self.delta is None:
            return DASH
        return f"{float(self.delta):+.1f}"

    @property
    def rank_text(self) -> str:
        return DASH if self.ranked_position is None else f"#{self.ranked_position:d}"

    @property
    def popularity_text(self) -> str:
        return DASH if self.popularity_rank is None else f"#{self.popularity_rank:,}"

    @property
    def direction(self) -> str:
        """Which way the disagreement runs, as a word the stylesheet reads.

        A word rather than a sign test at the point of use, so the colour and
        the caption cannot end up disagreeing about the same verdict.
        """
        if self.delta is None:
            return "level"
        if self.delta > 0:
            return "above"
        if self.delta < 0:
            return "below"
        return "level"


@dataclass(frozen=True)
class HotTakes:
    """The two ends of the same list: rated high, rated low."""

    higher: tuple[TitleVerdict, ...] = ()
    lower: tuple[TitleVerdict, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.higher or self.lower)


@dataclass(frozen=True)
class HypeKillers:
    """Highly ranked anime this reader rated unusually low."""

    count: int | None = None
    entries: tuple[TitleVerdict, ...] = ()
    biggest: TitleVerdict | None = None

    def __bool__(self) -> bool:
        return bool(self.entries or self.biggest)

    @property
    def count_text(self) -> str:
        return count_text(self.count)


@dataclass(frozen=True)
class HiddenGems:
    """Obscure anime this reader rated unusually high."""

    rate_text: str = DASH
    entries: tuple[TitleVerdict, ...] = ()
    deepest: TitleVerdict | None = None

    def __bool__(self) -> bool:
        return bool(self.entries or self.deepest)


@dataclass(frozen=True)
class TasteTitle:
    """A title in a genre's drill-down list: a name and one score."""

    title: str
    your_score: float | None = None

    @property
    def your_score_text(self) -> str:
        return DASH if self.your_score is None else f"{float(self.your_score):.0f}"


@dataclass(frozen=True)
class GenreReading:
    """One genre: how much of the list it is, and how it was scored."""

    name: str
    watched: int | None = None
    share: float | None = None
    average: float | None = None
    spread: float | None = None
    titles: tuple[TasteTitle, ...] = ()

    @property
    def watched_text(self) -> str:
        return count_text(self.watched)

    @property
    def average_text(self) -> str:
        return score_text(self.average, 2)


@dataclass(frozen=True)
class GenreVerdict:
    """A named genre singled out for one reason, with the figure behind it.

    CHANGE [EVIDENCE]: and with the titles behind the figure. "Military is
    your most divisive genre" is a claim a reader cannot check and often does
    not believe - the usual reaction is "I have watched something tagged
    Military?" - so the verdict carries the two ends that made it divisive.
    """

    name: str
    watched: int | None = None
    average: float | None = None
    spread: float | None = None
    detail: str = ""
    titles: tuple[TasteTitle, ...] = ()
    lowest: tuple[TasteTitle, ...] = ()

    @property
    def watched_text(self) -> str:
        return count_text(self.watched)

    @property
    def average_text(self) -> str:
        return score_text(self.average, 2)


@dataclass(frozen=True)
class GenreDNA:
    readings: tuple[GenreReading, ...] = ()
    best_match: GenreVerdict | None = None
    weakness: GenreVerdict | None = None
    divisive: GenreVerdict | None = None

    def __bool__(self) -> bool:
        return bool(self.readings)

    @cached_property
    def peak_share(self) -> float:
        """The widest genre, which the rest are drawn as a share of."""
        return max((reading.share or 0.0 for reading in self.readings), default=0.0)


@dataclass(frozen=True)
class StudioReading:
    """One studio, and what of theirs this reader actually saw.

    A studio name on its own is the weakest fact on the board: most people
    cannot name a thing Tezuka Productions made, so "your nemesis studio"
    reads as trivia about somebody else. The titles make it about the reader.
    """

    name: str
    watched: int | None = None
    average: float | None = None
    titles: tuple[TasteTitle, ...] = ()
    lowest: tuple[TasteTitle, ...] = ()

    @property
    def watched_text(self) -> str:
        return count_text(self.watched)

    @property
    def average_text(self) -> str:
        return score_text(self.average, 2)


@dataclass(frozen=True)
class StudioDNA:
    most_watched: StudioReading | None = None
    most_trusted: StudioReading | None = None
    nemesis: StudioReading | None = None
    readings: tuple[StudioReading, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.most_watched or self.most_trusted or self.nemesis)


@dataclass(frozen=True)
class EraBucket:
    label: str
    watched: int | None = None
    average: float | None = None

    @property
    def watched_text(self) -> str:
        return count_text(self.watched)

    @property
    def average_text(self) -> str:
        return score_text(self.average, 2)


@dataclass(frozen=True)
class SeasonReading:
    name: str
    average: float | None = None
    watched: int | None = None

    @property
    def average_text(self) -> str:
        return score_text(self.average, 1)


@dataclass(frozen=True)
class EraPreferences:
    buckets: tuple[EraBucket, ...] = ()
    golden: EraBucket | None = None
    seasons: tuple[SeasonReading, ...] = ()
    season_of_choice: str = ""

    def __bool__(self) -> bool:
        return bool(self.buckets or self.seasons)

    @cached_property
    def peak_watched(self) -> int:
        return max((bucket.watched or 0 for bucket in self.buckets), default=0)

    @cached_property
    def season_peak(self) -> float:
        return max((season.average or 0.0 for season in self.seasons), default=0.0)


@dataclass(frozen=True)
class HabitReading:
    """One behavioural percentage, and where it sits on its own rail."""

    reading_id: str
    caption: str
    value_text: str = DASH
    position: float | None = None


@dataclass(frozen=True)
class RewatchNote:
    title: str
    mal_id: int | None = None
    watches: int | None = None

    @property
    def watches_text(self) -> str:
        return DASH if self.watches is None else f"{int(self.watches)}×"


@dataclass(frozen=True)
class WatchingHabits:
    readings: tuple[HabitReading, ...] = ()
    most_rewatched: RewatchNote | None = None

    def __bool__(self) -> bool:
        return bool(self.readings)


@dataclass(frozen=True)
class TimelinePoint:
    year: int
    average: float | None = None
    rated: int | None = None

    @property
    def average_text(self) -> str:
        return score_text(self.average, 1)


@dataclass(frozen=True)
class RatingTimeline:
    """Mean score per year, and the backend's one-word reading of the shape."""

    points: tuple[TimelinePoint, ...] = ()
    trend: str = ""
    trend_detail: str = ""

    def __bool__(self) -> bool:
        return len(self.points) > 1

    @cached_property
    def bounds(self) -> tuple[float, float]:
        """The score range the plot is drawn against.

        Padded to at least two whole points and clamped to the 1-10 scale, so
        a reader whose averages all sit between 6.9 and 7.9 does not get a
        plot where a tenth of a point looks like a collapse.
        """
        values = [point.average for point in self.points if point.average is not None]
        if not values:
            return (1.0, 10.0)
        low, high = min(values), max(values)
        if high - low < 2.0:
            middle = (high + low) / 2
            low, high = middle - 1.0, middle + 1.0
        return (max(1.0, low - 0.2), min(10.0, high + 0.2))


@dataclass(frozen=True)
class TasteProfile:
    """Everything the Profile surface puts on screen, in one answer."""

    identity: ProfileIdentity = field(default_factory=ProfileIdentity)
    fingerprint: tuple[FingerprintReading, ...] = ()
    rating_distribution: RatingDistribution = field(default_factory=RatingDistribution)
    hot_takes: HotTakes = field(default_factory=HotTakes)
    hype_killers: HypeKillers = field(default_factory=HypeKillers)
    hidden_gems: HiddenGems = field(default_factory=HiddenGems)
    genres: GenreDNA = field(default_factory=GenreDNA)
    studios: StudioDNA = field(default_factory=StudioDNA)
    eras: EraPreferences = field(default_factory=EraPreferences)
    habits: WatchingHabits = field(default_factory=WatchingHabits)
    timeline: RatingTimeline = field(default_factory=RatingTimeline)
    # Set when the figures came from a recorded response rather than from a
    # real account, so the surface can say so instead of implying otherwise.
    is_sample: bool = False


# ---------------------------------------------------------------------------
# Providers
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# The verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Archetype:
    """A name for the way this reader differs, and the figures behind it.

    The Profile surface used to open with five equal readings and leave the
    reader to work out which one was about them. This picks the one that
    actually is, so the page can lead with a sentence somebody would repeat
    rather than a dashboard nobody asked for.
    """

    archetype_id: str
    name: str
    sentence: str
    evidence: tuple[str, ...] = ()

    def __bool__(self) -> bool:
        return bool(self.name)


# What each reading looks like for an ordinary reader, and how far from that
# counts as a lot. Deviation is measured against these rather than against the
# midpoint of the rail, because the rails are not centred on typical: almost
# everyone finishes most of what they start, so 0.87 completion is unremarkable
# while 0.31 contrarian is not. Comparing raw distance from 0.5 would call
# every reader a finisher.
_TYPICAL = {
    "community-sync": (0.60, 0.20),
    "rating-bias": (0.50, 0.20),
    "contrarian": (0.20, 0.15),
    "completion": (0.75, 0.18),
    "mainstream": (0.65, 0.20),
}

# One name per direction of travel. Deliberately none of them insulting: this
# is shown to a person about themselves, and "you have bad taste" is not an
# insight however well the arithmetic supports it. The high/low pairs are
# both flattering because both are genuinely interesting - agreeing with
# everyone is a real trait, not a failure to have opinions.
_ARCHETYPES = {
    ("contrarian", "high"): (
        "the outlier",
        "When everyone agrees on something, you are the one checking.",
    ),
    ("contrarian", "low"): (
        "the level head",
        "You recognize quality without chasing disagreement for its own sake. When you break from consensus, it means something.",
    ),
    ("rating-bias", "low"): (
        "the hard marker",
        "You spend your high scores carefully. A 9 from you is worth more than a 9 from most people.",
    ),
    ("rating-bias", "high"): (
        "the enthusiast",
        "You are generous with the things that earn your attention. Your list remembers what worked, not just what missed.",
    ),
    ("mainstream", "low"): (
        "the deep diver",
        "Most of your list is material the average watcher has never heard of.",
    ),
    ("mainstream", "high"): (
        "the scene reader",
        "You know the titles shaping the conversation, and you form your own view while everyone is still talking.",
    ),
    ("completion", "high"): (
        "the finisher",
        "You see things through. Once you start a series it is going on the completed pile.",
    ),
    ("completion", "low"): (
        "the curious sampler",
        "You explore widely and protect your time. A series has to earn its place before you stay with it.",
    ),
    ("community-sync", "high"): (
        "the barometer",
        "If a show lands with you, it lands with everyone. Your taste is the forecast.",
    ),
    ("community-sync", "low"): (
        "the wildcard",
        "Your scores go their own way. Knowing the community average tells you little about yours.",
    ),
}

# Ties broken in this order, so the same profile always reads the same way.
_PRIORITY = ("contrarian", "mainstream", "rating-bias", "community-sync", "completion")


def archetype_for(profile: "TasteProfile") -> Archetype | None:
    """Name the reader's strongest trait, or their balance across traits.

    Returns ``None`` only when there are no usable readings. Profiles near
    the typical value on every axis receive a balanced identity instead of
    being described as unremarkable.
    """
    scored: list[tuple[float, int, FingerprintReading]] = []
    for reading in profile.fingerprint:
        baseline = _TYPICAL.get(reading.reading_id)
        if baseline is None or reading.position is None:
            continue
        typical, spread = baseline
        if spread <= 0:
            continue
        deviation = (float(reading.position) - typical) / spread
        try:
            rank = _PRIORITY.index(reading.reading_id)
        except ValueError:
            rank = len(_PRIORITY)
        scored.append((abs(deviation), -rank, reading))

    if not scored:
        return None
    strength, _rank, reading = max(scored, key=lambda item: (item[0], item[1]))
    # A reader near the middle of every axis is not devoid of personality.
    # The truthful conclusion is balance: no single habit dominates the way
    # they choose, rate, or finish anime.
    if strength < 0.45:
        evidence = tuple(
            f"{item.value_text} {item.caption.lower()}"
            for item in profile.fingerprint
            if item.value_text and item.value_text != DASH
        )
        return Archetype(
            archetype_id="balanced-curator",
            name="the balanced curator",
            sentence=(
                "You know when to trust the crowd and when to keep your own "
                "counsel. Your taste has range without losing its center."
            ),
            evidence=evidence,
        )

    typical, spread = _TYPICAL[reading.reading_id]
    direction = "high" if float(reading.position) >= typical else "low"
    named = _ARCHETYPES.get((reading.reading_id, direction))
    if named is None:
        return None
    name, sentence = named

    evidence = tuple(
        f"{item.value_text} {item.caption.lower()}"
        for item in profile.fingerprint
        if item.value_text and item.value_text != DASH
    )
    return Archetype(
        archetype_id=f"{reading.reading_id}-{direction}",
        name=name,
        sentence=sentence,
        evidence=evidence,
    )


class TasteProfileProvider(Protocol):
    """The whole of what the Profile surface asks for.

    One call. It may raise ``TasteProfileUnavailable``; it may not return a
    half-filled profile, because a surface cannot tell the difference between
    "this reader has rated nothing" and "we did not manage to look".
    """

    def taste_profile(self) -> TasteProfile:
        """A prepared taste profile for the signed-in reader."""


class UnavailableTasteProfileProvider:
    """Explicit fallback when no local or remote profile source is configured.

    It refuses rather than inventing, and it refuses with a reason, so the
    surface renders a truthful state instead of an empty one that looks like
    a bug.
    """

    def __init__(
        self, reason: UnavailableReason = UnavailableReason.BACKEND_MISSING
    ) -> None:
        self._reason = reason

    def taste_profile(self) -> TasteProfile:
        raise TasteProfileUnavailable(self._reason)


class LocalTasteProfileProvider:
    """Adapt synchronized local statistics to the Profile surface contract."""

    _REASONS = {
        ProfileStatisticsUnavailableReason.NOT_CONNECTED: (
            UnavailableReason.NOT_CONNECTED
        ),
        ProfileStatisticsUnavailableReason.NO_DATA: UnavailableReason.USER_NOT_FOUND,
        ProfileStatisticsUnavailableReason.INVALID_DATA: (
            UnavailableReason.API_UNAVAILABLE
        ),
    }

    def __init__(self, statistics: ProfileStatisticsService) -> None:
        self._statistics = statistics

    def taste_profile(self) -> TasteProfile:
        try:
            payload = self._statistics.profile_payload()
        except ProfileStatisticsUnavailable as error:
            raise TasteProfileUnavailable(
                self._REASONS[error.reason], error.message
            ) from error
        return profile_from_payload(payload)


SAMPLE_TASTE_PROFILE_RESOURCE = "gui/resources/sample/sample_taste_profile.json"


class SampleTasteProfileProvider:
    """Replay a recorded profile, so the surface can be judged before it exists.

    The file it reads is a captured response in the documented shape, not a
    calculation: nothing here decides who is contrarian, it only parses. That
    distinction matters, because a "sample" that worked out its own answers
    would be a second implementation of the thing this deliberately does not
    implement.
    """

    def __init__(self, *, base_override: str | Path | None = None) -> None:
        self._base_override = base_override
        self._payload: dict | None = None

    def taste_profile(self) -> TasteProfile:
        if self._payload is None:
            try:
                path = resource_path(
                    SAMPLE_TASTE_PROFILE_RESOURCE, base_override=self._base_override
                )
                self._payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, TypeError) as error:
                raise TasteProfileUnavailable(
                    UnavailableReason.BACKEND_MISSING,
                    "The bundled sample profile could not be read.",
                ) from error
        return profile_from_payload(self._payload, is_sample=True)


# ---------------------------------------------------------------------------
# Parsing
#
# One function, used by every provider, so a live backend and a recorded
# response cannot drift into two readings of the same document.
# ---------------------------------------------------------------------------


def profile_from_payload(payload, *, is_sample: bool = False) -> TasteProfile:
    """Build a profile from the documented JSON shape.

    Tolerant in the way a boundary has to be: a missing figure becomes N/A
    rather than a crash, and a section that is absent entirely comes back
    empty so the surface can say "not measured" for that section alone instead
    of failing the page.
    """
    record = payload if isinstance(payload, dict) else {}
    return TasteProfile(
        identity=_identity_from(record.get("identity")),
        fingerprint=tuple(
            reading
            for raw in record.get("fingerprint") or ()
            if (reading := _fingerprint_from(raw)) is not None
        ),
        rating_distribution=_distribution_from(record.get("rating_distribution")),
        hot_takes=_hot_takes_from(record.get("hot_takes")),
        hype_killers=_hype_killers_from(record.get("hype_killers")),
        hidden_gems=_hidden_gems_from(record.get("hidden_gems")),
        genres=_genres_from(record.get("genres")),
        studios=_studios_from(record.get("studios")),
        eras=_eras_from(record.get("eras")),
        habits=_habits_from(record.get("habits")),
        timeline=_timeline_from(record.get("timeline")),
        is_sample=is_sample,
    )


def _identity_from(raw) -> ProfileIdentity:
    record = raw if isinstance(raw, dict) else {}
    return ProfileIdentity(
        username=_text(record.get("username")),
        avatar_url=record.get("avatar_url") or None,
        member_since=_text(record.get("member_since")),
        profile_url=record.get("profile_url") or None,
        completed=_count(record.get("completed")),
        episodes=_count(record.get("episodes")),
        days_watched=_number(record.get("days_watched")),
        mean_score=_number(record.get("mean_score")),
    )


def _fingerprint_from(raw) -> FingerprintReading | None:
    if not isinstance(raw, dict):
        return None
    caption = _text(raw.get("caption"))
    if not caption:
        return None
    return FingerprintReading(
        reading_id=_text(raw.get("id")) or caption.casefold(),
        caption=caption,
        value_text=_text(raw.get("value_text")) or DASH,
        label=_text(raw.get("label")),
        detail=_text(raw.get("detail")),
        position=_fraction(raw.get("position")),
        scale_low=_text(raw.get("scale_low")),
        scale_high=_text(raw.get("scale_high")),
        readout=_text(raw.get("readout")) or "cells",
        tone=_text(raw.get("tone")),
    )


def _distribution_from(raw) -> RatingDistribution:
    record = raw if isinstance(raw, dict) else {}
    buckets = []
    for item in record.get("buckets") or ():
        if not isinstance(item, dict):
            continue
        score = _count(item.get("score"))
        if score is None:
            continue
        buckets.append(RatingBucket(score=score, count=_count(item.get("count")) or 0))
    return RatingDistribution(buckets=tuple(buckets))


def _verdict_from(raw) -> TitleVerdict | None:
    if not isinstance(raw, dict):
        return None
    title = _text(raw.get("title"))
    if not title:
        return None
    return TitleVerdict(
        title=title,
        mal_id=_count(raw.get("mal_id")),
        cover_url=raw.get("cover_url") or None,
        your_score=_number(raw.get("your_score")),
        community_score=_number(raw.get("community_score")),
        delta=_number(raw.get("delta")),
        popularity_rank=_count(raw.get("popularity_rank")),
        ranked_position=_count(raw.get("ranked_position")),
        year=_count(raw.get("year")),
    )


def _verdicts_from(raw) -> tuple[TitleVerdict, ...]:
    return tuple(
        verdict for item in raw or () if (verdict := _verdict_from(item)) is not None
    )


def _hot_takes_from(raw) -> HotTakes:
    record = raw if isinstance(raw, dict) else {}
    return HotTakes(
        higher=_verdicts_from(record.get("higher")),
        lower=_verdicts_from(record.get("lower")),
    )


def _hype_killers_from(raw) -> HypeKillers:
    record = raw if isinstance(raw, dict) else {}
    return HypeKillers(
        count=_count(record.get("count")),
        entries=_verdicts_from(record.get("entries")),
        biggest=_verdict_from(record.get("biggest")),
    )


def _hidden_gems_from(raw) -> HiddenGems:
    record = raw if isinstance(raw, dict) else {}
    return HiddenGems(
        rate_text=_text(record.get("rate_text")) or DASH,
        entries=_verdicts_from(record.get("entries")),
        deepest=_verdict_from(record.get("deepest")),
    )


def _genres_from(raw) -> GenreDNA:
    record = raw if isinstance(raw, dict) else {}
    readings = []
    for item in record.get("readings") or ():
        if not isinstance(item, dict):
            continue
        name = _text(item.get("name"))
        if not name:
            continue
        titles = tuple(
            TasteTitle(
                title=_text(entry.get("title")),
                your_score=_number(entry.get("your_score")),
            )
            for entry in item.get("titles") or ()
            if isinstance(entry, dict) and _text(entry.get("title"))
        )
        readings.append(
            GenreReading(
                name=name,
                watched=_count(item.get("watched")),
                share=_number(item.get("share")),
                average=_number(item.get("average")),
                spread=_number(item.get("spread")),
                titles=titles,
            )
        )
    return GenreDNA(
        readings=tuple(readings),
        best_match=_genre_verdict_from(record.get("best_match")),
        weakness=_genre_verdict_from(record.get("weakness")),
        divisive=_genre_verdict_from(record.get("divisive")),
    )


def _taste_titles_from(raw) -> tuple[TasteTitle, ...]:
    """Parse a list of title/score pairs, dropping anything unusable."""
    return tuple(
        TasteTitle(title=name, your_score=_number(entry.get("your_score")))
        for entry in raw or ()
        if isinstance(entry, dict) and (name := _text(entry.get("title")))
    )


def _genre_verdict_from(raw) -> GenreVerdict | None:
    if not isinstance(raw, dict):
        return None
    name = _text(raw.get("name"))
    if not name:
        return None
    return GenreVerdict(
        name=name,
        watched=_count(raw.get("watched")),
        average=_number(raw.get("average")),
        spread=_number(raw.get("spread")),
        detail=_text(raw.get("detail")),
        titles=_taste_titles_from(raw.get("titles")),
        lowest=_taste_titles_from(raw.get("lowest")),
    )


def _studio_from(raw) -> StudioReading | None:
    if not isinstance(raw, dict):
        return None
    name = _text(raw.get("name"))
    if not name:
        return None
    return StudioReading(
        name=name,
        watched=_count(raw.get("watched")),
        average=_number(raw.get("average")),
        titles=_taste_titles_from(raw.get("titles")),
        lowest=_taste_titles_from(raw.get("lowest")),
    )


def _studios_from(raw) -> StudioDNA:
    record = raw if isinstance(raw, dict) else {}
    return StudioDNA(
        most_watched=_studio_from(record.get("most_watched")),
        most_trusted=_studio_from(record.get("most_trusted")),
        nemesis=_studio_from(record.get("nemesis")),
        readings=tuple(
            studio
            for item in record.get("readings") or ()
            if (studio := _studio_from(item)) is not None
        ),
    )


def _era_bucket_from(raw) -> EraBucket | None:
    if not isinstance(raw, dict):
        return None
    label = _text(raw.get("label"))
    if not label:
        return None
    return EraBucket(
        label=label,
        watched=_count(raw.get("watched")),
        average=_number(raw.get("average")),
    )


def _eras_from(raw) -> EraPreferences:
    record = raw if isinstance(raw, dict) else {}
    seasons = tuple(
        SeasonReading(
            name=_text(item.get("name")),
            average=_number(item.get("average")),
            watched=_count(item.get("watched")),
        )
        for item in record.get("seasons") or ()
        if isinstance(item, dict) and _text(item.get("name"))
    )
    return EraPreferences(
        buckets=tuple(
            bucket
            for item in record.get("buckets") or ()
            if (bucket := _era_bucket_from(item)) is not None
        ),
        golden=_era_bucket_from(record.get("golden")),
        seasons=seasons,
        season_of_choice=_text(record.get("season_of_choice")),
    )


def _habits_from(raw) -> WatchingHabits:
    record = raw if isinstance(raw, dict) else {}
    readings = []
    for item in record.get("readings") or ():
        if not isinstance(item, dict):
            continue
        caption = _text(item.get("caption"))
        if not caption:
            continue
        readings.append(
            HabitReading(
                reading_id=_text(item.get("id")) or caption.casefold(),
                caption=caption,
                value_text=_text(item.get("value_text")) or DASH,
                position=_fraction(item.get("position")),
            )
        )
    rewatched = record.get("most_rewatched")
    note = None
    if isinstance(rewatched, dict) and _text(rewatched.get("title")):
        note = RewatchNote(
            title=_text(rewatched.get("title")),
            mal_id=_count(rewatched.get("mal_id")),
            watches=_count(rewatched.get("watches")),
        )
    return WatchingHabits(readings=tuple(readings), most_rewatched=note)


def _timeline_from(raw) -> RatingTimeline:
    record = raw if isinstance(raw, dict) else {}
    points = []
    for item in record.get("points") or ():
        if not isinstance(item, dict):
            continue
        year = _count(item.get("year"))
        if year is None:
            continue
        points.append(
            TimelinePoint(
                year=year,
                average=_number(item.get("average")),
                rated=_count(item.get("rated")),
            )
        )
    points.sort(key=lambda point: point.year)
    return RatingTimeline(
        points=tuple(points),
        trend=_text(record.get("trend")),
        trend_detail=_text(record.get("trend_detail")),
    )
