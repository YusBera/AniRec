"""The genre and studio tags on a card, as controls rather than as a sentence.

A card used to print its genres as one string - "Psychological · Mystery ·
Drama" - which is the right density and the wrong object. The single most
common thing a person wants after reading that line is *more like this one*,
and a sentence cannot offer it.

Three constraints shaped what replaced it, and they pull against each other:

* it has to stay metadata. A genre is not a call to action, and eleven filled
  buttons on a 208px card is a toolbar with a poster attached.
* it has to be reachable without a mouse. Which rules out a painted strip with
  a click handler, and rules in real buttons: focusable, in the tab order,
  activated by Space and Enter for free, and announced as buttons.
* it must not change the card's height. The grid is a grid because every
  wrapped block on the card reserves a fixed number of lines; a flow of tags
  that grew with the tag count would undo that for the whole feed.

So: real flat buttons, laid out into a reservation of exactly the height the
label they replaced occupied, and anything past the last row collapses into a
single "+n" that carries the rest in its tooltip. A card with eleven genres is
the same height as a card with two, and neither of them hides a genre without
saying so.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget

from .design_tokens import SPACE
from ..presentation.filters import FilterKind
from .scaling import scaled


# The gap between tags, and between rows of tags.
TAG_SPACING = SPACE["xs"]


class MetadataTag(QPushButton):
    """One clickable genre or studio."""

    def __init__(
        self, kind: FilterKind, value: str, parent: QWidget | None = None
    ) -> None:
        super().__init__(value, parent)
        self.kind = kind
        self.value = value
        self.setObjectName("metadataTag")
        # Read by the stylesheet, so a studio and a genre are told apart by
        # the same colour vocabulary the filter pills use.
        self.setProperty("tagKind", kind.value)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFlat(True)
        label = "genre" if kind is FilterKind.GENRE else "studio"
        self.setAccessibleName(f"Filter by {label} {value}")
        self.setToolTip(f"Show more {value}")


class OverflowTag(QPushButton):
    """The "+n" that stands for the tags that did not fit.

    It is a button rather than a label so the hidden values are reachable:
    pressing it asks the card to say what they are, and its tooltip lists them
    for anyone who only hovers.
    """

    def __init__(self, hidden: tuple[str, ...], parent: QWidget | None = None) -> None:
        super().__init__(f"+{len(hidden)}", parent)
        self.hidden = hidden
        self.setObjectName("metadataTagOverflow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFlat(True)
        joined = ", ".join(hidden)
        self.setAccessibleName(f"{len(hidden)} more: {joined}")
        self.setToolTip(joined)


class MetadataTagStrip(QWidget):
    """Genres and studios for one anime, wrapped into a fixed reservation.

    Laid out by hand, in ``resizeEvent``, because Qt ships no flow layout and
    the alternatives - a QTextEdit of links, a painted strip - each give up
    one of the three constraints above.
    """

    tag_activated = Signal(object, str)
    overflow_activated = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("metadataTagStrip")
        self._tags: list[QPushButton] = []
        self._values: tuple[tuple[FilterKind, str], ...] = ()
        self._overflow: OverflowTag | None = None
        self._laid_out_width = -1
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    @property
    def tags(self) -> tuple[QPushButton, ...]:
        return tuple(self._tags)

    @property
    def overflow(self) -> OverflowTag | None:
        return self._overflow

    def set_values(self, values) -> None:
        """Replace the strip's contents.

        Studios lead. They are the single most useful handle a viewer has -
        "another one by Kyoto Animation" is a stronger signal than "another
        drama" - and putting them first means they survive a narrow card,
        where the tail of a long genre list is what collapses.
        """
        values = tuple(
            (kind, str(value).strip())
            for kind, value in values or ()
            if str(value or "").strip()
        )
        if values == self._values:
            return
        self._values = values
        self._rebuild()

    def _rebuild(self) -> None:
        for widget in self._tags:
            widget.hide()
            widget.setParent(None)
            widget.deleteLater()
        self._tags = []
        if self._overflow is not None:
            self._overflow.hide()
            self._overflow.setParent(None)
            self._overflow.deleteLater()
            self._overflow = None

        for kind, value in self._values:
            tag = MetadataTag(kind, value, self)
            tag.clicked.connect(
                lambda _checked=False, k=kind, v=value: self.tag_activated.emit(k, v)
            )
            self._tags.append(tag)
        self._laid_out_width = -1
        self._reflow()

    def highlight(self, value: str) -> None:
        """Light the tag a rail segment belongs to.

        Matching is by displayed value because that is what the two surfaces
        genuinely share: the rail's contributor names come from the same
        genre and studio strings these tags are built from. Comparison is
        case-folded so a difference in casing between the two sources cannot
        silently break the link.

        When the hovered contributor has no tag - the community term, or the
        pooled "other tags" - every tag dims instead. Saying nothing would be
        ambiguous with "hovering nothing at all"; dimming says the block under
        the pointer came from somewhere other than the tags on this card.
        """
        wanted = str(value or "").strip().casefold()
        values = {str(getattr(t, "value", "")).casefold() for t in self._tags}
        unmatched = bool(wanted) and wanted not in values
        for tag in self._tags:
            linked = (
                bool(wanted)
                and not unmatched
                and str(getattr(tag, "value", "")).casefold() == wanted
            )
            dimmed = unmatched
            if tag.property("linked") == linked and tag.property("dimmed") == dimmed:
                continue
            tag.setProperty("linked", linked)
            tag.setProperty("dimmed", dimmed)
            tag.style().unpolish(tag)
            tag.style().polish(tag)

    def reserve_height(self, height: int) -> None:
        """Pin the strip to the height the label it replaced occupied."""
        self.setFixedHeight(max(0, int(height)))
        self._laid_out_width = -1
        self._reflow()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.width() != self._laid_out_width:
            self._reflow()

    def _reflow(self) -> None:
        """Place as many tags as the reservation holds, then collapse the rest."""
        self._laid_out_width = self.width()
        available = self.width()
        if available <= 0 or not self._tags:
            if self._overflow is not None:
                self._overflow.hide()
            for tag in self._tags:
                tag.setVisible(available > 0)
            return

        gap = scaled(TAG_SPACING)
        row_height = max(tag.sizeHint().height() for tag in self._tags)
        rows = max(1, (self.height() + gap) // (row_height + gap))

        placed: list[QPushButton] = []
        placed_rows: list[int] = []
        hidden: list[str] = []
        x = 0
        row = 0
        for index, tag in enumerate(self._tags):
            width = min(tag.sizeHint().width(), available)
            if x and x + width > available:
                # Preserve the occupied width of the final permitted row.
                # Resetting x before discovering that the next row does not
                # exist placed the +n counter at x=0, directly over the first
                # tag in that row.
                if row + 1 >= rows:
                    hidden = [widget.value for widget in self._tags[index:]]
                    break
                row += 1
                x = 0
            if row >= rows:
                hidden = [widget.value for widget in self._tags[index:]]
                break
            tag.move(x, row * (row_height + gap))
            tag.resize(width, row_height)
            tag.show()
            placed.append(tag)
            placed_rows.append(row)
            x += width + gap

        for tag in self._tags[len(placed) :]:
            tag.hide()

        if self._overflow is not None:
            self._overflow.hide()
            self._overflow.setParent(None)
            self._overflow.deleteLater()
            self._overflow = None

        if not hidden:
            return

        # The counter has to fit too, so the last placed tag makes room for it
        # rather than the counter spilling past the card edge.
        overflow = OverflowTag(tuple(hidden), self)
        overflow.clicked.connect(
            lambda _checked=False, values=tuple(hidden): self.overflow_activated.emit(values)
        )
        last_row = max(0, rows - 1)
        while True:
            overflow.hidden = tuple(hidden)
            overflow.setText(f"+{len(hidden)}")
            joined = ", ".join(hidden)
            overflow.setAccessibleName(f"{len(hidden)} more: {joined}")
            overflow.setToolTip(joined)
            width = overflow.sizeHint().width()
            if x + width <= available:
                break
            if not placed or placed_rows[-1] != last_row:
                # The counter is deliberately tiny, but keep its geometry
                # bounded if an extreme font scale makes even it wider than
                # the entire strip.
                width = min(width, available)
                break
            dropped = placed.pop()
            placed_rows.pop()
            dropped.hide()
            hidden.insert(0, dropped.value)
            x = dropped.x()
        overflow.move(x, last_row * (row_height + gap))
        overflow.resize(width, row_height)
        overflow.show()
        self._overflow = overflow
