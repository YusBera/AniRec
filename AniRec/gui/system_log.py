"""A read-only console reporting what the application is actually doing.

This is the one surface that tells you the machine is working rather than
merely styled to look like it does. Every line corresponds to a real event
the window already knows about - a worker starting, a theme applying, a
profile loading, a request failing - so the panel stays honest under a
direction that would otherwise invite decorative fake telemetry.

It takes no input. It is scrollable, it follows the tail unless the reader
has scrolled away from it, and it drops the oldest lines once the buffer is
full so a long session cannot grow it without bound.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime

from PySide6.QtCore import QRegularExpression, QTimer, Qt
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat
from PySide6.QtWidgets import (
    QFrame,
    QSizePolicy,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


# Lines retained. Past this the oldest are discarded, which bounds both memory
# and the cost of re-rendering the document.
MAX_LINES = 200

# A record occupies a stamp/tag row and an indented message row.
ROWS_PER_RECORD = 2

# Delay between startup lines. Long enough to read as a sequence, short
# enough that the panel is fully populated before anyone reaches for it.
BOOT_LINE_MS = 130

# Visible height of the console, in pixels.
LOG_HEIGHT = 132

# Width of the drawn progress meter, in cells.
METER_CELLS = 10


def render_meter(percent: float, cells: int = METER_CELLS, glyph: str = "|") -> str:
    """Draw a text progress meter, e.g. ``[||||||    ] 60%``.

    Bounded and integer-quantised so a value outside 0-100, or a NaN arriving
    from a worker, cannot produce a ragged or oversized bar.
    """
    try:
        value = float(percent)
    except (TypeError, ValueError):
        value = 0.0
    if value != value:  # NaN
        value = 0.0
    value = max(0.0, min(100.0, value))
    filled = int(round(cells * value / 100.0))
    filled = max(0, min(cells, filled))
    return f"[{glyph * filled}{' ' * (cells - filled)}] {value:3.0f}%"


def _theme_colour(role: str, fallback: str) -> QColor:
    """A colour the active theme published, with a safe default."""
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    value = application.property(role) if application is not None else None
    colour = QColor(str(value or fallback))
    return colour if colour.isValid() else QColor(fallback)


# Which channels read as which kind of event. Anything unlisted falls back to
# the muted body colour, so an unknown tag is quiet rather than loud.
CHANNEL_ROLES = {
    "BOOT": ("resolvedSignal", "#6FC6C0"),
    "ENGINE": ("resolvedAccent", "#C6A15B"),
    "SOURCE": ("resolvedAccent", "#C6A15B"),
    "RENDER": ("resolvedTextSubtle", "#7C8C80"),
    "RETRIEV": ("resolvedSignal", "#6FC6C0"),
    "STATUS": ("resolvedText", "#E9E5D6"),
    "ERROR": (None, "#F0989A"),
}


class LogHighlighter(QSyntaxHighlighter):
    """Colour the console by field, not by decoration.

    Three things carry meaning on a line: when it happened, which part of the
    application said it, and any measured value. Each gets its own weight, so
    the column of tags can be scanned without reading the messages, and a
    meter stands out from the prose beside it.
    """

    TIMESTAMP = QRegularExpression(r"^\d{2}:\d{2}:\d{2}")
    TAG = QRegularExpression(r"^\d{2}:\d{2}:\d{2}\s+([A-Z_]+)")
    METER = QRegularExpression(r"\[[|\s]*\]\s*\d+%")

    def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt API
        stamp = QTextCharFormat()
        stamp.setForeground(_theme_colour("resolvedTextSubtle", "#7C8C80"))
        match = self.TIMESTAMP.match(text)
        if match.hasMatch():
            self.setFormat(match.capturedStart(), match.capturedLength(), stamp)

        match = self.TAG.match(text)
        if match.hasMatch():
            name = match.captured(1)
            role, fallback = CHANNEL_ROLES.get(
                name, ("resolvedTextSubtle", "#7C8C80")
            )
            tag_format = QTextCharFormat()
            tag_format.setForeground(
                QColor(fallback) if role is None else _theme_colour(role, fallback)
            )
            tag_format.setFontWeight(700)
            self.setFormat(
                match.capturedStart(1), match.capturedLength(1), tag_format
            )

        meter = QTextCharFormat()
        meter.setForeground(_theme_colour("resolvedAccent", "#C6A15B"))
        iterator = self.METER.globalMatch(text)
        while iterator.hasNext():
            found = iterator.next()
            self.setFormat(found.capturedStart(), found.capturedLength(), meter)


class SystemLog(QFrame):
    """A bounded, read-only activity console."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("systemLog")
        self.setAccessibleName("System activity log")
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 10, 10)
        layout.setSpacing(4)

        # CHANGE [RAIL-BUDGET]: the console is collapsed by default. Expanded,
        # its 132px plus the SYSTEM readout above it spent close to a third of
        # the rail's height on lines like "system palette bound - x1.00" -
        # true, but nothing anybody acts on, and it was crowding the only
        # navigation in the application. Collapsed it keeps the one thing the
        # panel is actually read for, the newest event, on a single line, and
        # opens on click for the rest.
        self.caption = QPushButton("ACTIVITY  +")
        self.caption.setObjectName("railCaptionToggle")
        self.caption.setProperty("buttonRole", "link")
        self.caption.setCheckable(True)
        self.caption.setCursor(Qt.CursorShape.PointingHandCursor)
        self.caption.setAccessibleName("Show or hide the system activity log")
        self.caption.toggled.connect(self.set_expanded)
        layout.addWidget(self.caption)

        self.summary = QLabel("")
        self.summary.setObjectName("systemLogSummary")
        self.summary.setWordWrap(True)
        # CHANGE [RAIL-JUMP]: neither of the two panels may have an opinion
        # about how wide the rail is.
        #
        # The rail is deliberately elastic - 214 to 238 - so that nav labels
        # can claim the slack when the GUI scale makes them wider. The
        # console was claiming it instead: a QPlainTextEdit asks for about
        # 280px by default, so opening the console pushed the rail from 214
        # straight to its 238 maximum, took 24px off the content beside it,
        # and reflowed the entire card grid sideways. Measured: stack width
        # 1017 collapsed, 993 expanded, on one click of a control that is
        # supposed to reveal a log.
        #
        # Ignored plus a zero minimum is the same treatment the card action
        # buttons get, and for the same reason: the container decides the
        # width, not the text inside it.
        self.summary.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.summary.setMinimumWidth(0)
        self.summary.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.summary)

        self.view = QPlainTextEdit()
        self.view.setObjectName("systemLogView")
        self.view.setReadOnly(True)
        self.view.setUndoRedoEnabled(False)
        self.view.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        # Two blocks per record since a record is laid out over two rows,
        # so the view holds the same MAX_LINES records the deque does.
        self.view.setMaximumBlockCount(MAX_LINES * ROWS_PER_RECORD)
        self.view.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Deliberately short. It is a status panel on a rail, not a log
        # viewer: enough lines to see what just happened, scrollable for the
        # rest, and never so tall that it competes with the navigation above.
        self.view.setFixedHeight(LOG_HEIGHT)
        self.view.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed
        )
        self.view.setMinimumWidth(0)
        self.view.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.view.setVisible(False)
        layout.addWidget(self.view)
        self._highlighter = LogHighlighter(self.view.document())

        self._lines: deque[str] = deque(maxlen=MAX_LINES)
        # While a startup sequence is being revealed, anything else the
        # application reports queues behind it. Without this the paced boot
        # lines interleave with events that fire immediately, and the console
        # shows the machine finishing before it started.
        self._boot_queue: list[tuple[str, str]] = []
        self._booting = False
        # Which channel owns the newest line, when that line is a live meter.
        # Tracked as a tag rather than an index: the deque evicts from the
        # front once it is full, which would silently shift every stored
        # index by one and make a meter rewrite the wrong row.
        self._live_tag: str | None = None

    # ---- expansion -----------------------------------------------------

    def set_expanded(self, expanded: bool) -> None:
        """Open or close the console, leaving the newest line always visible."""
        expanded = bool(expanded)
        if self.caption.isChecked() != expanded:
            self.caption.setChecked(expanded)
        self.caption.setText("ACTIVITY  −" if expanded else "ACTIVITY  +")
        self.view.setVisible(expanded)
        self.summary.setVisible(not expanded)
        if expanded:
            self._render(follow=True)

    @property
    def is_expanded(self) -> bool:
        # isVisible() is False for every child of a window that has not been
        # shown yet, which is not what is being asked here.
        return self.view.isVisibleTo(self)

    def _update_summary(self) -> None:
        """Show the newest record's message on the collapsed single line."""
        if not self._lines:
            self.summary.setText("")
            return
        # A record is laid out over two rows, "stamp TAG" then the indented
        # message. The message is what is worth the one line; the stamp and
        # the channel are not.
        newest = self._lines[-1].splitlines()[-1].strip()
        self.summary.setText(newest)
        self.summary.setToolTip(newest)

    # ---- writing -------------------------------------------------------

    @staticmethod
    def _compose(stamp: str, tag: str, body: str) -> str:
        """Lay one record out over two rows.

        CHANGE [WRAP]: every record used to be written as a single
        ``HH:MM:SS TAG message`` line into a 200px column. Measured against
        IBM Plex Mono at 7.4pt, not one real line fitted - they ran 204px to
        354px - so every record wrapped, and the continuation row started
        flush left in the timestamp's column. That destroyed the one thing
        the tag column is for: being scannable without reading the messages.

        The prefix alone is 14 characters, about 42% of the column, so no
        amount of shortening it makes the single-line form fit. Splitting the
        record instead keeps the stamp and tag on an uncluttered row that
        always fits, and indents the message under it. The same vertical
        space the ragged wrap was already using, spent deliberately.
        """
        return f"{stamp} {str(tag)[:7].upper()}\n  {body}"

    def append(self, tag: str, message: str) -> None:
        """Record one event. ``tag`` is a short uppercase channel name."""
        if self._booting:
            self._boot_queue.append((str(tag), str(message)))
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        self._lines.append(self._compose(stamp, tag, message))
        self._live_tag = None
        self._render(follow=self._at_tail())

    def progress(self, tag: str, percent: float, message: str = "") -> None:
        """Record or update a progress meter for one channel."""
        key = str(tag).upper()
        stamp = datetime.now().strftime("%H:%M:%S")
        meter = render_meter(percent)
        suffix = f" {message}" if message else ""
        line = self._compose(stamp, key, f"{meter}{suffix}")

        if self._live_tag == key and self._lines:
            self._lines[-1] = line
        else:
            self._lines.append(line)
            self._live_tag = key
        self._render(follow=self._at_tail())

    def boot(self, entries) -> None:
        """Reveal a startup sequence one line at a time.

        The lines are the same real events the console would print anyway;
        only their arrival is paced. A machine of this kind does not finish
        starting in a single frame, and watching the sequence land is what
        tells you the panel is live rather than a printed label.
        """
        pending = [(str(tag), str(message)) for tag, message in entries]
        if not pending:
            return
        self._booting = True

        def emit_next() -> None:
            if pending:
                tag, message = pending.pop(0)
                self._booting = False
                self.append(tag, message)
                self._booting = True
                QTimer.singleShot(BOOT_LINE_MS, emit_next)
                return
            # Sequence finished: release anything that arrived meanwhile, in
            # the order it actually happened.
            self._booting = False
            queued, self._boot_queue = self._boot_queue, []
            for tag, message in queued:
                self.append(tag, message)

        QTimer.singleShot(0, emit_next)

    def retint(self) -> None:
        """Re-run the highlighter after a palette change.

        Formats are resolved at highlight time from the colours the theme
        published, so existing lines keep the previous theme's colours until
        the document is highlighted again.
        """
        self._highlighter.rehighlight()

    def clear(self) -> None:
        self._lines.clear()
        self._live_tag = None
        self.view.clear()
        self._update_summary()

    # ---- rendering -----------------------------------------------------

    def _at_tail(self) -> bool:
        """True when the reader has not scrolled away from the newest line."""
        bar = self.view.verticalScrollBar()
        return bar.value() >= bar.maximum() - 2

    def _render(self, *, follow: bool) -> None:
        self._update_summary()
        bar = self.view.verticalScrollBar()
        previous = bar.value()
        self.view.setPlainText("\n".join(self._lines))
        if follow:
            bar.setValue(bar.maximum())
        else:
            # Someone is reading history; leave their position alone.
            bar.setValue(min(previous, bar.maximum()))
