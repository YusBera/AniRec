"""The Discover surface: one action, your taste, and the feed to review.

Addresses: BUG5 (the header left too little room to browse).

Everything a first time user needs sits on one page. What used to be a
dashboard, a separate genre analysis page and a seven step pipeline view is
now a single primary action, a taste summary folded away until asked for, and
the recommendations themselves.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
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
from .instrument_widgets import InstrumentPanel
from .resources import themed_ui_icon
from .texts import DISCOVER_TEXT


# How far the feed must scroll before the introductory header folds away.
COLLAPSE_THRESHOLD_PX = 24


def _vertical_rule() -> QFrame:
    """A hard 1px separator, used between fields on a header strip."""
    rule = QFrame()
    rule.setObjectName("stripDivider")
    rule.setFixedWidth(1)
    rule.setFixedHeight(14)
    return rule


class TastePanel(QFrame):
    """A collapsible summary of the genres driving the current feed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardPanel")
        # Which ranked terms are studios rather than genres, and the last
        # stats seen, so the sentence can be rewritten when the catalogue
        # arrives after the stats do.
        self._studio_names: set[str] = set()
        self._last_stats: tuple | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["sm"], SPACE["lg"], SPACE["sm"])
        layout.setSpacing(SPACE["xs"])

        header = QHBoxLayout()
        header.setSpacing(SPACE["sm"])
        self.caption_label = QLabel(DISCOVER_TEXT.taste_caption)
        self.caption_label.setObjectName("discoverChannel")
        header.addWidget(self.caption_label)
        header.addWidget(_vertical_rule())
        self.toggle_button = QPushButton(DISCOVER_TEXT.taste_show)
        self.toggle_button.setObjectName("tastePanelToggle")
        self.toggle_button.setProperty("buttonRole", "link")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setAccessibleName("Show or hide your taste summary")
        self.summary_label = QLabel(DISCOVER_TEXT.taste_empty)
        self.summary_label.setObjectName("dashboardGenreName")
        self.summary_label.setWordWrap(True)
        header.addWidget(self.summary_label, 1)
        header.addWidget(self.toggle_button)
        layout.addLayout(header)

        self.detail_label = QLabel("")
        self.detail_label.setObjectName("dashboardMetricLabel")
        self.detail_label.setWordWrap(True)
        self.detail_label.setVisible(False)
        layout.addWidget(self.detail_label)

        self.toggle_button.toggled.connect(self._on_toggled)

    def _on_toggled(self, expanded: bool) -> None:
        self.detail_label.setVisible(bool(expanded))
        self.toggle_button.setText(
            DISCOVER_TEXT.taste_hide if expanded else DISCOVER_TEXT.taste_show
        )

    def set_studio_names(self, studios) -> None:
        """Tell the panel which of its ranked terms are studios, not genres."""
        self._studio_names = {
            str(name).strip().casefold() for name in studios or () if str(name).strip()
        }
        if self._last_stats is not None:
            self.set_genre_stats(self._last_stats)

    def set_genre_stats(self, stats) -> None:
        self._last_stats = tuple(stats or ())
        ranked = sorted(
            stats, key=lambda stat: -float(stat.importance_score or 0.0)
        )
        liked = [stat for stat in ranked if float(stat.importance_score or 0.0) > 0][:4]
        disliked = [
            stat for stat in reversed(ranked) if float(stat.importance_score or 0.0) < 0
        ][:2]

        if not liked and not disliked:
            self.summary_label.setText(DISCOVER_TEXT.taste_empty)
            self.detail_label.setText("")
            self.toggle_button.setEnabled(False)
            return

        self.toggle_button.setEnabled(True)
        self.summary_label.setText(self._summary_sentence(liked))

        lines = []
        for stat in liked:
            rated = stat.completed_count or 0
            lines.append(
                DISCOVER_TEXT.taste_line.format(genre=stat.genre, count=rated)
            )
        for stat in disliked:
            lines.append(DISCOVER_TEXT.taste_avoid.format(genre=stat.genre))
        self.detail_label.setText("\n".join(lines))

    def _summary_sentence(self, liked) -> str:
        """Say what you like, and separately who tends to have made it.

        Both kinds of term come out of the same ranking and both belong in
        the sentence; they just do not belong in the same list. Until the
        catalogue has been ingested there are no studio names to match
        against, in which case this degrades to exactly the old sentence.
        """
        studio_names = getattr(self, "_studio_names", set())
        genres = [
            stat.genre for stat in liked if stat.genre.strip().casefold() not in studio_names
        ]
        studios = [
            stat.genre for stat in liked if stat.genre.strip().casefold() in studio_names
        ]
        if genres and studios:
            return DISCOVER_TEXT.taste_summary_studios.format(
                genres=", ".join(genres), studios=" and ".join(studios[:2])
            )
        if studios:
            return DISCOVER_TEXT.taste_summary_studios_only.format(
                studios=" and ".join(studios[:2])
            )
        return DISCOVER_TEXT.taste_summary.format(
            genres=", ".join(genres) or DISCOVER_TEXT.taste_none_yet
        )


class DiscoverPage(QWidget):
    """The Discover surface: one instrument header, then the feed.

    CHANGE [HEADER-REHAUL]: this surface used to open with a stack of
    full-width strips - an action row, a taste row, and the explorer's own
    hero band underneath - each with its own frame, its own margins and a gap
    between them. Three boxes to carry a state word, a sentence and a button.

    They are one panel now, two lines tall: identity and state and the run
    control on the first line, the taste vector on the second, divided by a
    single hairline. The taste half stays a child widget so it can still fold
    away on scroll, but folding it now collapses a line inside a panel rather
    than removing a whole box from the page.
    """

    refresh_requested = Signal()

    def __init__(
        self,
        explorer: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-discover")
        self.setAccessibleName("Discover page")

        # What STATE reports: whether a run is in flight, and whether the last
        # one failed. Declared before the strip is built, because the strip
        # paints its opening state as it is assembled.
        self._running = False
        self._faulted = False

        # CHANGE [PAGE]: the same inset and rhythm every other surface uses.
        # The explorer inside supplies its own page margin when it *is* the
        # page, so it is told not to here - otherwise the two would stack and
        # Discover's feed would sit further in than My Library's.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACE["sm"], SPACE["sm"], SPACE["sm"], SPACE["sm"]
        )
        layout.setSpacing(SPACE["md"])

        header = InstrumentPanel()
        header.setObjectName("discoverHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(0)

        # --- line one: who, what state, and the one action ---
        strip = QWidget()
        strip.setObjectName("discoverActionStrip")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(
            SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"]
        )
        strip_layout.setSpacing(SPACE["md"])

        self.channel_label = QLabel(DISCOVER_TEXT.channel)
        self.channel_label.setObjectName("discoverChannel")
        self.state_caption = QLabel(DISCOVER_TEXT.state_caption)
        self.state_caption.setObjectName("discoverStateCaption")
        # The STATE value: a vocabulary, fixed and short, in the numeric face.
        # It used to hold whatever _report_activity last passed, so after a
        # sync a field captioned STATE read "MAL data updated - 412 completed
        # titles synced." - a wrapped past-tense sentence in a state field,
        # which never returned to READY.
        self.status_label = QLabel(DISCOVER_TEXT.status_ready)
        self.status_label.setObjectName("discoverStateValue")
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred
        )
        # The sentence, in the reading face, beside the state rather than
        # inside it.
        self.message_label = QLabel("")
        self.message_label.setObjectName("discoverStatusMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self.refresh_button = QPushButton(DISCOVER_TEXT.refresh)
        self.refresh_button.setObjectName("discoverRefreshButton")
        self.refresh_button.setProperty("buttonRole", "primary")
        self.refresh_button.setAccessibleName(DISCOVER_TEXT.refresh_accessible)
        self.refresh_button.setIcon(
            themed_ui_icon("refresh", role="resolvedAccentContrast")
        )
        self.refresh_button.setMinimumWidth(146)
        self.refresh_button.setMaximumWidth(168)
        self.refresh_button.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        # Paint the opening state through the same path every later one
        # takes, so READY carries its tone from the first frame.
        self._render_state()

        strip_layout.addWidget(self.channel_label)
        strip_layout.addWidget(_vertical_rule())
        strip_layout.addWidget(self.state_caption)
        strip_layout.addWidget(self.status_label)
        strip_layout.addWidget(self.message_label)
        strip_layout.addStretch(1)
        strip_layout.addWidget(self.refresh_button)
        header_layout.addWidget(strip)

        self._header_rule = QFrame()
        self._header_rule.setObjectName("railRule")
        self._header_rule.setFixedHeight(1)
        header_layout.addWidget(self._header_rule)

        # --- line two: the taste vector behind this feed ---
        self.taste_panel = TastePanel()
        header_layout.addWidget(self.taste_panel)

        layout.addWidget(header)
        self._header = header
        self._strip = strip

        self.explorer = explorer
        explorer.set_embedded(True)
        layout.addWidget(explorer, 1)

        # CHANGE [BUG5]: the header took 41% of a 1280x720 window, leaving about
        # a third of the height to actually browse in. The parts that are only
        # needed before you start reading now fold away as soon as the feed is
        # scrolled, and come back when you return to the top.
        self._collapsed = False
        if hasattr(explorer, "feed_scrolled"):
            explorer.feed_scrolled.connect(self._on_feed_scrolled)

    def retint_icons(self) -> None:
        """Re-render this surface's glyphs for the active theme."""
        self.refresh_button.setIcon(
            themed_ui_icon("refresh", role="resolvedAccentContrast")
        )

    @staticmethod
    def _divider() -> QFrame:
        return _vertical_rule()

    def _on_feed_scrolled(self, position: int) -> None:
        self.set_header_collapsed(position > COLLAPSE_THRESHOLD_PX)

    def set_header_collapsed(self, collapsed: bool) -> None:
        """Fold the introductory header away while browsing."""
        collapsed = bool(collapsed)
        if collapsed == self._collapsed:
            return
        self._collapsed = collapsed
        # The taste summary is orientation, not a control, so it is what goes
        # while browsing. The action and the state stay: they are why you are
        # on this surface and what the machine is doing about it.
        self.taste_panel.setVisible(not collapsed)
        self._header_rule.setVisible(not collapsed)

    @property
    def header_collapsed(self) -> bool:
        return self._collapsed

    def set_genre_stats(self, stats) -> None:
        self.taste_panel.set_genre_stats(tuple(stats or ()))

    def set_studio_names(self, studios) -> None:
        self.taste_panel.set_studio_names(studios)

    def set_status(self, message: str, *, tone: str = "success") -> None:
        """Report what happened. The sentence goes beside STATE, not into it."""
        self.message_label.setText(message or "")
        self._faulted = tone == "error"
        self._render_state()

    def set_refreshing(self, running: bool) -> None:
        self.refresh_button.setEnabled(not running)
        self.refresh_button.setText(
            DISCOVER_TEXT.refreshing if running else DISCOVER_TEXT.refresh
        )
        self._running = running
        if running:
            # A new run supersedes the previous one's verdict and its message;
            # leaving the old sentence up beside BUSY reports the wrong run.
            self._faulted = False
            self.message_label.setText("")
        self._render_state()

    def _render_state(self) -> None:
        """Drive STATE from what the machine is doing, and nothing else."""
        if self._running:
            text, tone = DISCOVER_TEXT.status_busy, "busy"
        elif self._faulted:
            text, tone = DISCOVER_TEXT.status_fault, "error"
        else:
            text, tone = DISCOVER_TEXT.status_ready, "ok"
        self.status_label.setText(text)
        self.status_label.setProperty("tone", tone)
        self.status_label.style().unpolish(self.status_label)
        self.status_label.style().polish(self.status_label)
