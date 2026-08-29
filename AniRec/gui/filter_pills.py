"""The row of active filters, between the feed's controls and the feed.

A pill here is not the rounded capsule the word usually implies. This
interface is a front panel: everything on it is square, hairlined, and
labelled in the stencil face. So a filter reads as a *tag strip* - a caption in
the machine face, the value beside it, and a hard dismiss box on the end -
which is the same object the library tabs and the state readouts already are.

Each kind carries a colour, but the colour is a border and a caption tint, not
a filled swatch: eight filled chips in six colours is a bag of sweets, and the
values are what should be read, not the categories. Every colour comes from a
role the palette already defines, so the row follows light, dark, OLED and any
gradient the user builds without a second palette to keep in step.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import SPACE
from .discover_filters import ActiveFilter, FilterKind, ProfileStatus
from .instrument_widgets import StatusLight
from .scaling import scaled
from .texts import FILTER_TEXT


# How wide a value may be before it is elided. Long enough for almost every
# real genre, studio and username; short enough that one pathological value
# cannot push the rest of the row off screen. A username may run to 64
# characters, and MAL studio names are not much kinder.
MAXIMUM_VALUE_WIDTH = 168


# Which palette role paints each kind's border and caption. The row has to be
# scannable by category at a glance without turning into a rainbow, so the
# assignments follow the two-accent rule the rest of the application keeps:
# amber is the user's own taste, cyan is the system and other people.
KIND_TONES = {
    FilterKind.GENRE: "genre",
    FilterKind.STUDIO: "studio",
    FilterKind.YEAR: "year",
    FilterKind.SCORE: "score",
    FilterKind.STATUS: "status",
    FilterKind.EPISODES: "episodes",
    FilterKind.PROFILE: "profile",
}


class FilterPill(QFrame):
    """One active filter, with its own dismiss control.

    Built from real controls rather than a painted rectangle with a click
    handler: the dismiss is a QPushButton so it is in the tab order, has a
    focus ring, and is announced as a button, and the whole pill is focusable
    so the keyboard can reach a filter without walking through every dismiss
    box first.
    """

    dismissed = Signal(object)
    retry_requested = Signal(object)

    def __init__(self, filter_: ActiveFilter, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.filter = filter_
        self.setObjectName("filterPill")
        self.setProperty("filterKind", KIND_TONES[filter_.kind])
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["sm"]), scaled(SPACE["hair"]),
            scaled(SPACE["hair"]), scaled(SPACE["hair"]),
        )
        layout.setSpacing(scaled(SPACE["xs"]))

        # A profile is the one filter that has to be fetched, so it is the one
        # that carries a lamp. The same lamp the navigation rail uses, so
        # "working" and "faulted" look the same wherever they are reported.
        self.lamp: StatusLight | None = None
        if filter_.kind is FilterKind.PROFILE:
            self.lamp = StatusLight(self._lamp_state(filter_))
            layout.addWidget(self.lamp, 0, Qt.AlignmentFlag.AlignVCenter)

        self.caption_label = QLabel(f"{filter_.label}:")
        self.caption_label.setObjectName("filterPillCaption")
        layout.addWidget(self.caption_label)

        self.value_label = QLabel(filter_.display_value)
        self.value_label.setObjectName("filterPillValue")
        self.value_label.setMaximumWidth(scaled(MAXIMUM_VALUE_WIDTH))
        layout.addWidget(self.value_label)

        # Only ever built for a profile that failed, so a healthy row carries
        # no dead controls.
        self.retry_button: QPushButton | None = None
        if filter_.is_failed:
            self.retry_button = QPushButton(FILTER_TEXT.pill_retry)
            self.retry_button.setObjectName("filterPillRetry")
            self.retry_button.setProperty("buttonRole", "link")
            self.retry_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.retry_button.setAccessibleName(
                FILTER_TEXT.pill_retry_accessible.format(value=filter_.display_value)
            )
            self.retry_button.clicked.connect(
                lambda: self.retry_requested.emit(self.filter)
            )
            layout.addWidget(self.retry_button)

        self.dismiss_button = QPushButton("×")
        self.dismiss_button.setObjectName("filterPillDismiss")
        self.dismiss_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dismiss_button.setFixedWidth(scaled(20))
        self.dismiss_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        # The glyph is decoration; what a screen reader is told is the whole
        # sentence, because "×" on its own names neither the action nor which
        # of eight filters it would remove.
        self.dismiss_button.setAccessibleName(
            FILTER_TEXT.pill_dismiss_accessible.format(
                label=filter_.label, value=filter_.display_value
            )
        )
        self.dismiss_button.setToolTip(self.dismiss_button.accessibleName())
        self.dismiss_button.clicked.connect(lambda: self.dismissed.emit(self.filter))
        layout.addWidget(self.dismiss_button)

        self._apply_state(filter_)

    @staticmethod
    def _lamp_state(filter_: ActiveFilter) -> str:
        if filter_.status is ProfileStatus.PENDING:
            return "busy"
        if filter_.status is ProfileStatus.ERROR:
            return "error"
        return "ok"

    def _apply_state(self, filter_: ActiveFilter) -> None:
        """Say what the pill is doing, in text as well as in colour.

        The lamp is the fast read, but a lamp alone is a colour-only signal
        and this row has to be usable without it: the accessible name and the
        tooltip carry the same fact in words, and a failure puts its reason
        where it can actually be read rather than only tinting the border.
        """
        loading = filter_.is_loading
        failed = filter_.is_failed
        self.setProperty("pillState", "loading" if loading else "error" if failed else "")
        if loading:
            state_text = FILTER_TEXT.pill_loading.format(value=filter_.display_value)
        elif failed:
            state_text = filter_.message or FILTER_TEXT.pill_failed.format(
                value=filter_.display_value
            )
        else:
            state_text = f"{filter_.label}: {filter_.display_value}"
        self.setAccessibleName(state_text)
        self.setToolTip(state_text)
        # The label may be wider than the pill allows, and a truncated value is
        # only honest if the whole one is still reachable.
        elided = self._elided(filter_.display_value)
        self.value_label.setText(elided)
        if elided != filter_.display_value:
            self.value_label.setToolTip(filter_.display_value)
        self.value_label.setAccessibleName(filter_.display_value)
        if self.lamp is not None:
            self.lamp.set_state(self._lamp_state(filter_))
        self.style().unpolish(self)
        self.style().polish(self)

    def _elided(self, text: str) -> str:
        metrics = self.value_label.fontMetrics()
        return metrics.elidedText(
            text, Qt.TextElideMode.ElideRight, scaled(MAXIMUM_VALUE_WIDTH)
        )

    def update_filter(self, filter_: ActiveFilter) -> None:
        """Re-state an existing pill rather than rebuilding the row.

        A profile resolving is the common case here, and rebuilding the row
        for it would take focus away from whatever the reader was on.
        """
        self.filter = filter_
        self.caption_label.setText(f"{filter_.label}:")
        self._apply_state(filter_)

    def keyPressEvent(self, event) -> None:
        """Delete and Backspace remove the focused filter.

        A pill is reachable by Tab, so it should be dismissable without
        having to Tab once more into the box beside it.
        """
        if event.key() in {Qt.Key.Key_Delete, Qt.Key.Key_Backspace}:
            self.dismissed.emit(self.filter)
            return
        super().keyPressEvent(event)


class FilterPillBar(QWidget):
    """Every active filter, wrapping rather than scrolling.

    Wrapping is the point: a row that scrolls sideways hides filters, and a
    hidden filter is exactly the thing that makes a feed look broken. The rows
    are built by hand because Qt has no flow layout, and the widget hides
    itself outright when there is nothing to show, so an empty state costs no
    height at all rather than leaving a band of padding above the feed.
    """

    filter_dismissed = Signal(object)
    retry_requested = Signal(object)
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("filterPillBar")
        self._pills: dict[tuple[str, str], FilterPill] = {}
        self._filters: tuple[ActiveFilter, ...] = ()
        self._row_width = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["xs"]))

        self._rows_container = QWidget(self)
        self._rows_layout = QVBoxLayout(self._rows_container)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        self._rows_layout.setSpacing(scaled(SPACE["xs"]))
        layout.addWidget(self._rows_container)

        self.clear_button = QPushButton(FILTER_TEXT.clear_all)
        self.clear_button.setObjectName("filterPillClear")
        self.clear_button.setProperty("buttonRole", "link")
        self.clear_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.clear_button.setAccessibleName(FILTER_TEXT.clear_all_accessible)
        self.clear_button.clicked.connect(self.clear_requested.emit)

        self.setVisible(False)

    @property
    def pills(self) -> tuple[FilterPill, ...]:
        return tuple(self._pills.values())

    def set_filters(self, filters) -> None:
        """Bring the row in line with the state, reusing what is already there.

        Rebuilding wholesale would be simpler and would also destroy the pill
        under the pointer every time another profile finished loading, so a
        pill that is still wanted is updated in place and only genuine
        arrivals and departures are built and torn down.
        """
        filters = tuple(filters or ())
        self._filters = filters
        wanted = {item.key: item for item in filters}

        for key in [key for key in self._pills if key not in wanted]:
            pill = self._pills.pop(key)
            pill.hide()
            pill.setParent(None)
            pill.deleteLater()

        for key, item in wanted.items():
            pill = self._pills.get(key)
            if pill is None:
                pill = FilterPill(item, self)
                pill.dismissed.connect(self.filter_dismissed.emit)
                pill.retry_requested.connect(self.retry_requested.emit)
                self._pills[key] = pill
            else:
                pill.update_filter(item)

        # A pill that gains or loses its retry control has to be rebuilt: the
        # control is only created for a failed filter, so an in-place update
        # cannot conjure it.
        for key, item in list(wanted.items()):
            pill = self._pills[key]
            if bool(pill.retry_button) != bool(item.is_failed):
                pill.hide()
                pill.setParent(None)
                pill.deleteLater()
                replacement = FilterPill(item, self)
                replacement.dismissed.connect(self.filter_dismissed.emit)
                replacement.retry_requested.connect(self.retry_requested.emit)
                self._pills[key] = replacement

        self.setVisible(bool(filters))
        self.clear_button.setVisible(len(filters) > 1)
        self._reflow()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.width() != self._row_width:
            self._reflow()

    def _reflow(self) -> None:
        """Lay the pills into as many rows as the width needs.

        Measured against the widget's own width rather than a fixed count, so
        the row behaves the same at every window size and GUI scale, and never
        makes the page scroll sideways.
        """
        self._row_width = self.width()
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout() is not None:
                item.layout().setParent(None)

        ordered = [
            self._pills[item.key] for item in self._filters if item.key in self._pills
        ]
        if not ordered:
            return

        gap = scaled(SPACE["xs"])
        available = max(self.width(), scaled(240))
        rows: list[list[QWidget]] = [[]]
        used = 0
        trailing = [self.clear_button] if self.clear_button.isVisible() else []
        for widget in [*ordered, *trailing]:
            width = widget.sizeHint().width()
            if rows[-1] and used + gap + width > available:
                rows.append([])
                used = 0
            rows[-1].append(widget)
            used += width + (gap if len(rows[-1]) > 1 else 0)

        for row in rows:
            container = QWidget(self._rows_container)
            container.setObjectName("filterPillRow")
            row_layout = QHBoxLayout(container)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(gap)
            for widget in row:
                widget.setParent(container)
                widget.show()
                row_layout.addWidget(widget)
            row_layout.addStretch(1)
            self._rows_layout.addWidget(container)
