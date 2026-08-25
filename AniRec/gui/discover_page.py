"""The Discover surface: one action, your taste, and the feed to review.

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
from .texts import DISCOVER_TEXT


class TastePanel(QFrame):
    """A collapsible summary of the genres driving the current feed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboardPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["lg"], SPACE["sm"], SPACE["lg"], SPACE["sm"])
        layout.setSpacing(SPACE["xs"])

        header = QHBoxLayout()
        header.setSpacing(SPACE["sm"])
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

    def set_genre_stats(self, stats) -> None:
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
        names = ", ".join(stat.genre for stat in liked) or DISCOVER_TEXT.taste_none_yet
        self.summary_label.setText(DISCOVER_TEXT.taste_summary.format(genres=names))

        lines = []
        for stat in liked:
            rated = stat.completed_count or 0
            lines.append(
                DISCOVER_TEXT.taste_line.format(genre=stat.genre, count=rated)
            )
        for stat in disliked:
            lines.append(DISCOVER_TEXT.taste_avoid.format(genre=stat.genre))
        self.detail_label.setText("\n".join(lines))


class DiscoverPage(QWidget):
    """Action strip, taste summary, and the recommendation feed."""

    refresh_requested = Signal()

    def __init__(
        self,
        explorer: QWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-discover")
        self.setAccessibleName("Discover page")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["sm"])

        strip = QFrame()
        strip.setObjectName("discoverActionStrip")
        strip_layout = QHBoxLayout(strip)
        strip_layout.setContentsMargins(0, 0, 0, 0)
        strip_layout.setSpacing(SPACE["md"])

        self.status_label = QLabel(DISCOVER_TEXT.status_ready)
        self.status_label.setObjectName("dashboardMetricLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        # One button replaces the seven step pipeline page. The steps still
        # exist, behind the developer tools switch in Settings, for anyone who
        # wants to run them individually.
        self.refresh_button = QPushButton(DISCOVER_TEXT.refresh)
        self.refresh_button.setObjectName("discoverRefreshButton")
        self.refresh_button.setProperty("buttonRole", "primary")
        self.refresh_button.setAccessibleName(DISCOVER_TEXT.refresh_accessible)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)

        strip_layout.addWidget(self.status_label, 1)
        strip_layout.addWidget(self.refresh_button)
        layout.addWidget(strip)

        self.taste_panel = TastePanel()
        layout.addWidget(self.taste_panel)

        self.explorer = explorer
        layout.addWidget(explorer, 1)

    def set_genre_stats(self, stats) -> None:
        self.taste_panel.set_genre_stats(tuple(stats or ()))

    def set_status(self, message: str) -> None:
        self.status_label.setText(message or DISCOVER_TEXT.status_ready)

    def set_refreshing(self, running: bool) -> None:
        self.refresh_button.setEnabled(not running)
        self.refresh_button.setText(
            DISCOVER_TEXT.refreshing if running else DISCOVER_TEXT.refresh
        )
