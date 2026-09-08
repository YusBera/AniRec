"""Shared presentation semantics for recommendation contribution rails.

This module only classifies labels already supplied to the frontend.  It does
not calculate scores.  Keeping the classification and tonal variants here
means the compact cover rail and the expanded score track cannot assign two
different colours to the same contributor.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

from PySide6.QtGui import QColor


class ContributionKind(str, Enum):
    GENRE = "genre"
    STUDIO = "studio"
    COMMUNITY = "community"
    OTHER = "other"


@dataclass(frozen=True)
class SemanticContribution:
    name: str
    value: float
    kind: ContributionKind
    ordinal: int


_TONE_FACTORS = (100, 112, 92, 120, 96)

# How far each successive term in one category is rotated around the colour
# wheel. Lightness alone was not enough: three genres on one card came out at
# an identical hue and saturation, separated only by lightness, so the rail
# read as a single aqua region with faint steps in it rather than as three
# contributors. The span stays narrow enough that a genre never drifts into
# the studio family - genres land within 40 degrees of the signal hue, studios
# within 40 of the accent, and those two sit far enough apart to keep a clear
# gap between the groups.
_HUE_OFFSETS = (0, 24, -22, 40, -38)
_HUE_SPAN = 40

# Kinds that describe everyone else rather than this viewer, and how far
# they are pushed back behind the taste terms.
_RECEDING_KINDS = frozenset(
    {ContributionKind.COMMUNITY, ContributionKind.OTHER}
)
_RECEDE = 145


def _normalise(value: object) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def _unprefixed(value: str) -> str:
    head, separator, tail = value.partition(":")
    if separator and head.strip() in {
        "genre",
        "studio",
        "community",
        "viewer",
        "source",
    }:
        return tail.strip()
    return value


def classify_contribution(
    name: object,
    *,
    genres=(),
    studios=(),
) -> ContributionKind:
    """Classify a display label against metadata already on its view model."""
    label = _normalise(name)
    bare = _unprefixed(label)
    genre_names = {_normalise(item) for item in genres if _normalise(item)}
    studio_names = {_normalise(item) for item in studios if _normalise(item)}

    if label.startswith("studio:") or bare in studio_names:
        return ContributionKind.STUDIO
    if label.startswith("genre:") or bare in genre_names:
        return ContributionKind.GENRE
    if any(word in label for word in ("community", "viewer", "mal score")):
        return ContributionKind.COMMUNITY
    return ContributionKind.OTHER


def semantic_contributions(
    contributions,
    *,
    genres=(),
    studios=(),
) -> tuple[SemanticContribution, ...]:
    """Clean contribution values and number tones independently per kind."""
    ordinals = {kind: 0 for kind in ContributionKind}
    cleaned: list[SemanticContribution] = []
    for name, value in contributions or ():
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not math.isfinite(number):
            continue
        kind = classify_contribution(name, genres=genres, studios=studios)
        cleaned.append(
            SemanticContribution(str(name), number, kind, ordinals[kind])
        )
        ordinals[kind] += 1
    return tuple(cleaned)


def tonal_variant(base: QColor, ordinal: int) -> QColor:
    """Separate successive terms in one category, without leaving it.

    Both hue and lightness move. Hue does most of the work because it is what
    the eye actually uses to tell two adjacent blocks apart; lightness is kept
    as a smaller secondary cue so the distinction survives for a viewer who
    cannot separate those hues.
    """
    index = max(0, int(ordinal))
    colour = QColor(base)

    offset = _HUE_OFFSETS[index % len(_HUE_OFFSETS)]
    if offset and colour.saturation() > 0:
        hue, saturation, lightness, alpha = colour.getHsl()
        colour = QColor.fromHsl(
            (hue + max(-_HUE_SPAN, min(_HUE_SPAN, offset))) % 360,
            saturation,
            lightness,
            alpha,
        )

    factor = _TONE_FACTORS[index % len(_TONE_FACTORS)]
    if factor > 100:
        return colour.lighter(factor)
    if factor < 100:
        return colour.darker(round(10_000 / factor))
    return colour


def contribution_colour(
    contribution: SemanticContribution,
    *,
    genre: QColor,
    studio: QColor,
    community: QColor,
    other: QColor,
) -> QColor:
    bases = {
        ContributionKind.GENRE: genre,
        ContributionKind.STUDIO: studio,
        ContributionKind.COMMUNITY: community,
        ContributionKind.OTHER: other,
    }
    colour = tonal_variant(bases[contribution.kind], contribution.ordinal)
    if contribution.kind in _RECEDING_KINDS:
        # The community average and the pooled minor tags are not the user's
        # taste, and on a real card the community block is the second largest
        # thing on the rail. Rendered as a bright peer it competed with the
        # terms that actually describe this person; receded, the lit part of
        # the bar is the part that is about them.
        colour = colour.darker(_RECEDE)
    return colour


def contribution_summary(contributions: tuple[SemanticContribution, ...]) -> str:
    """Provide a non-colour explanation for tooltips and assistive tech."""
    if not contributions:
        return "No contribution breakdown available"
    labels = {
        ContributionKind.GENRE: "Genre",
        ContributionKind.STUDIO: "Studio",
        ContributionKind.COMMUNITY: "Community",
        ContributionKind.OTHER: "Other",
    }
    return "; ".join(
        f"{labels[item.kind]}: {item.name} {item.value:g}"
        for item in contributions
    )


def proportional_segment_widths(
    contributions: tuple[SemanticContribution, ...], total_width: float
) -> tuple[float, ...]:
    """Divide a score's visible fill by each positive contributor's share.

    Contribution values can be raw points that do not themselves add up to
    the calibrated match percentage.  A compact score rail still needs to end
    at that percentage; the exact raw values remain available in its tooltip
    and in the detail rows.
    """
    values = tuple(max(0.0, item.value) for item in contributions)
    total = sum(values)
    if total <= 0.0 or total_width <= 0.0:
        return tuple(0.0 for _item in contributions)
    return tuple(float(total_width) * value / total for value in values)


def snap_pixel(value: float) -> int:
    """Round a positive logical coordinate without Python's half-to-even rule."""
    return int(math.floor(max(0.0, float(value)) + 0.5))


def snapped_segment_edges(widths, *, start: float = 0.0) -> tuple[int, ...]:
    """Return shared integer edges so adjacent fills never create fat gaps."""
    running = float(start)
    edges = [snap_pixel(running)]
    for width in widths:
        running += max(0.0, float(width))
        edges.append(snap_pixel(running))
    return tuple(edges)
