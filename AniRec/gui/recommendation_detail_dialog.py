"""The recommendation score inspector.

The landing page sells AniRec by showing how a score is assembled.  This
dialog is the application-side version of that promise: the existing view
model is presented as an inspectable instrument rather than as a metadata
form followed by a newline-separated debug dump.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeyEvent, QPixmap, QShowEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .cover_art import rounded_cover
from .design_tokens import RADIUS, SPACE
from .instrument_widgets import (
    ChannelWipe,
    InstrumentPanel,
    ScoreTrack,
    Scanlines,
    keep_crisp,
)
from .recommendation_card import open_mal_url
from .recommendation_view_model import RecommendationViewModel
from .resources import cover_placeholder_pixmap, title_placeholder_pixmap


DETAIL_COVER_WIDTH = 300
DETAIL_COVER_HEIGHT = 450
NO_GENRE_CONTRIBUTIONS = "No score contribution breakdown is available."


class RecommendationDetailDialog(QDialog):
    cover_requested = Signal(str)
    not_interested_requested = Signal(object)
    watch_later_requested = Signal(object)
    previous_requested = Signal()
    next_requested = Signal()

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mal_opener: Callable[[QUrl], bool] = QDesktopServices.openUrl,
    ) -> None:
        super().__init__(parent)
        self.model: RecommendationViewModel | None = None
        self._mal_opener = mal_opener
        self._pending_animation = False
        self.setObjectName("recommendationDetailDialog")
        # CHANGE [CRT]: the raster, so this reads as part of the same
        # machine. Installed last in __init__ so it sits above the
        # dialog's own children; it re-raises itself when more arrive.
        self.setWindowTitle("Score Inspector")
        self.setModal(False)
        self.resize(1040, 720)
        self.setMinimumSize(760, 560)
        self._build_ui()
        self.scanlines = Scanlines(self)
        self.scanlines.raise_()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        rack = InstrumentPanel()
        rack.setObjectName("recommendationDetailRack")
        rack_layout = QHBoxLayout(rack)
        rack_layout.setContentsMargins(18, 9, 14, 9)
        rack_layout.setSpacing(SPACE["sm"])
        rack_legend = QLabel("ANIREC  /  SCORE INSPECTOR")
        rack_legend.setObjectName("recommendationDetailRackLegend")
        rack_layout.addWidget(rack_legend)
        rack_layout.addStretch()
        self.previous_button = QPushButton("‹")
        self.previous_button.setObjectName("recommendationDetailPrevious")
        self.previous_button.setProperty("buttonRole", "link")
        self.previous_button.setAccessibleName("Inspect previous recommendation")
        self.previous_button.clicked.connect(self.previous_requested.emit)
        self.navigation_label = QLabel("01 / 01")
        self.navigation_label.setObjectName("recommendationDetailNavigation")
        self.next_button = QPushButton("›")
        self.next_button.setObjectName("recommendationDetailNext")
        self.next_button.setProperty("buttonRole", "link")
        self.next_button.setAccessibleName("Inspect next recommendation")
        self.next_button.clicked.connect(self.next_requested.emit)
        self.close_button = QPushButton("Close")
        self.close_button.setProperty("buttonRole", "ghost")
        self.close_button.setAccessibleName("Close score inspector")
        self.close_button.clicked.connect(self.close)
        rack_layout.addWidget(self.previous_button)
        rack_layout.addWidget(self.navigation_label)
        rack_layout.addWidget(self.next_button)
        rack_layout.addSpacing(SPACE["sm"])
        rack_layout.addWidget(self.close_button)
        root.addWidget(rack)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("recommendationDetailScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("recommendationDetailContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(18, 16, 18, 20)
        content_layout.setSpacing(SPACE["lg"])

        hero = QHBoxLayout()
        hero.setSpacing(SPACE["lg"])
        self.cover_label = QLabel()
        self.cover_label.setObjectName("recommendationDetailCover")
        self.cover_label.setFixedSize(DETAIL_COVER_WIDTH, DETAIL_COVER_HEIGHT)
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        # CHANGE [CRISP-ART]: the card, the row, the bundle stack and the
        # profile all exempt their artwork from the raster; this one never
        # did, so the biggest cover in the application - 300x450, the whole
        # left half of the inspector - was the only one being drawn through
        # a 1-in-3 dark line. Atmosphere over chrome, never over a photograph.
        keep_crisp(self.cover_label)
        self._show_placeholder()
        hero.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignTop)

        inspector_column = QVBoxLayout()
        inspector_column.setSpacing(SPACE["sm"])
        self.title_label = self._label("", "recommendationDetailTitle", word_wrap=True)
        self.secondary_title_label = self._label(
            "", "recommendationDetailSecondaryTitle", word_wrap=True
        )
        self.alternative_titles_label = self._label(
            "", "recommendationDetailAlternatives", word_wrap=True
        )
        inspector_column.addWidget(self.title_label)
        inspector_column.addWidget(self.secondary_title_label)
        inspector_column.addWidget(self.alternative_titles_label)

        facts = QGridLayout()
        facts.setHorizontalSpacing(SPACE["lg"])
        facts.setVerticalSpacing(SPACE["xs"])
        self.mal_score_label = self._label("", "recommendationDetailMalScore")
        self.episodes_label = self._label("", "recommendationDetailEpisodes")
        self.status_label = self._label("", "recommendationDetailStatus")
        self.year_label = self._label("", "recommendationDetailYear")
        self.dates_label = self._label("", "recommendationDetailDates", word_wrap=True)
        self.genres_label = self._label("", "recommendationDetailGenres", word_wrap=True)
        for label in (
            self.mal_score_label,
            self.episodes_label,
            self.status_label,
            self.year_label,
            self.dates_label,
            self.genres_label,
        ):
            label.setProperty("detailFact", True)
        facts.addWidget(self.mal_score_label, 0, 0)
        facts.addWidget(self.episodes_label, 0, 1)
        facts.addWidget(self.status_label, 1, 0)
        facts.addWidget(self.year_label, 1, 1)
        facts.addWidget(self.dates_label, 2, 0, 1, 2)
        facts.addWidget(self.genres_label, 3, 0, 1, 2)
        inspector_column.addLayout(facts)

        self.score_bench = InstrumentPanel()
        self.score_bench.setObjectName("recommendationScoreBench")
        score_layout = QVBoxLayout(self.score_bench)
        score_layout.setContentsMargins(16, 13, 16, 14)
        score_layout.setSpacing(SPACE["sm"])
        score_header = QHBoxLayout()
        score_header.addWidget(self._label("PERSONAL MATCH", "recommendationScoreLegend"))
        score_header.addStretch()
        score_header.addWidget(self._label("EXPLAINED SCORE", "recommendationScoreMode"))
        score_layout.addLayout(score_header)

        readout = QHBoxLayout()
        readout.setSpacing(SPACE["md"])
        score_number = QHBoxLayout()
        score_number.setSpacing(2)
        self.score_value_label = QLabel("0.0")
        self.score_value_label.setObjectName("recommendationScoreValue")
        self.score_percent_label = QLabel("%")
        self.score_percent_label.setObjectName("recommendationScorePercent")
        score_number.addWidget(self.score_value_label, 0, Qt.AlignmentFlag.AlignBottom)
        score_number.addWidget(self.score_percent_label, 0, Qt.AlignmentFlag.AlignTop)
        readout.addLayout(score_number)
        self.reason_label = self._label(
            "", "recommendationDetailReason", word_wrap=True
        )
        readout.addWidget(self.reason_label, 1, Qt.AlignmentFlag.AlignBottom)
        score_layout.addLayout(readout)

        # Compatibility/accessibility text is retained while the visible
        # presentation is the numeric readout and segmented score rail.
        self.personal_match_label = self._label("", "personalMatchLabel")
        self.personal_match_label.setParent(self.score_bench)
        self.personal_match_label.setVisible(False)
        self.contributions_label = self._label(
            "", "recommendationDetailContributions", word_wrap=True
        )
        self.contributions_label.setParent(self.score_bench)
        self.contributions_label.setVisible(False)

        self.score_track = ScoreTrack()
        score_layout.addWidget(self.score_track)
        scale = QHBoxLayout()
        scale.setContentsMargins(1, 0, 1, 0)
        for value in ("0", "25", "50", "75", "100"):
            label = QLabel(value)
            label.setObjectName("recommendationScoreScale")
            if value != "100":
                scale.addWidget(label)
                scale.addStretch()
            else:
                scale.addWidget(label)
        score_layout.addLayout(scale)

        self.contribution_rows = QVBoxLayout()
        self.contribution_rows.setSpacing(0)
        score_layout.addLayout(self.contribution_rows)
        sum_row = QHBoxLayout()
        self.sum_caption_label = QLabel("SUMS TO")
        self.sum_caption_label.setObjectName("recommendationScoreSumCaption")
        self.sum_total_label = QLabel("0.00")
        self.sum_total_label.setObjectName("recommendationScoreSum")
        sum_row.addWidget(self.sum_caption_label)
        sum_row.addStretch()
        sum_row.addWidget(self.sum_total_label)
        score_layout.addLayout(sum_row)
        inspector_column.addWidget(self.score_bench)

        utilities = QHBoxLayout()
        utilities.setSpacing(SPACE["xs"])
        self.watch_later_button = QPushButton("Watch Later")
        self.watch_later_button.setObjectName("recommendationDetailWatchLaterButton")
        self.watch_later_button.setProperty("savedAction", True)
        self.watch_later_button.setCheckable(True)
        self.watch_later_button.clicked.connect(
            lambda: self.model is not None
            and self.watch_later_requested.emit(self.model)
        )
        self.mal_button = QPushButton("Open on MyAnimeList")
        self.mal_button.setObjectName("recommendationDetailMalButton")
        self.mal_button.setProperty("buttonRole", "link")
        self.mal_button.clicked.connect(self._open_mal)
        # CHANGE [NO-VERDICTS]: the breakdown's own Like / Dislike pair is
        # gone with the rest of them, and Hide has taken their place under its
        # honest name. This is the surface where a reader has just read the
        # whole case for a recommendation, so it is the most likely place for
        # them to decide against it.
        self.not_interested_button = QPushButton("Not interested")
        self.not_interested_button.setObjectName(
            "recommendationDetailNotInterestedButton"
        )
        self.not_interested_button.setProperty("feedback", "not-interested")
        self.not_interested_button.setCheckable(True)
        self.not_interested_button.clicked.connect(
            lambda: self.model is not None
            and self.not_interested_requested.emit(self.model)
        )
        utilities.addWidget(self.watch_later_button)
        utilities.addWidget(self.not_interested_button)
        utilities.addStretch()
        utilities.addWidget(self.mal_button)
        inspector_column.addLayout(utilities)
        inspector_column.addStretch()
        hero.addLayout(inspector_column, 1)
        content_layout.addLayout(hero)

        synopsis_panel = InstrumentPanel()
        synopsis_panel.setObjectName("recommendationSynopsisPanel")
        synopsis_layout = QVBoxLayout(synopsis_panel)
        synopsis_layout.setContentsMargins(16, 10, 16, 14)
        synopsis_layout.setSpacing(SPACE["sm"])
        self.synopsis_toggle = QPushButton("READ SYNOPSIS  +")
        self.synopsis_toggle.setObjectName("recommendationSynopsisToggle")
        self.synopsis_toggle.setProperty("buttonRole", "link")
        self.synopsis_toggle.setCheckable(True)
        self.synopsis_toggle.setAccessibleName("Show or hide the anime synopsis")
        self.synopsis_label = self._label(
            "", "recommendationDetailSynopsis", word_wrap=True
        )
        self.synopsis_label.setVisible(False)
        self.synopsis_toggle.toggled.connect(self._set_synopsis_expanded)
        synopsis_layout.addWidget(self.synopsis_toggle)
        synopsis_layout.addWidget(self.synopsis_label)
        content_layout.addWidget(synopsis_panel)
        content_layout.addStretch()
        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)
        self.content_wipe = ChannelWipe(self.scroll.viewport())

        # CHANGE [HONEST-READOUT]: the headline percentage no longer counts up
        # from zero. It used to run 0 -> value over 680ms, which meant that for
        # two thirds of a second this dialog printed a large, confident,
        # wrong number - 13.5% - directly above a breakdown that already read
        # "SUMS TO 94.60". The number is the one thing on this screen that
        # must never be wrong, so it is now set once, final, before paint.
        # The reveal it used to carry lives on the contribution track below,
        # which is decoration and can afford to move.
        self.set_navigation(1, 1)

    @staticmethod
    def _label(text: str, object_name: str, *, word_wrap: bool = False) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(word_wrap)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def set_model(self, model: RecommendationViewModel) -> None:
        self.model = model
        self.setWindowTitle(f"{model.display_title} | Score Inspector")
        self.setAccessibleName(f"Score inspector for {model.display_title}")
        self.title_label.setText(model.display_title)
        self.secondary_title_label.setText(model.secondary_title or "")
        self.secondary_title_label.setVisible(bool(model.secondary_title))
        # CHANGE [NO-NULL-PROSE]: a title with no alternative names used to
        # spend the most valuable line on the screen - directly under the
        # heading - saying so. The absence of data is not content; the row
        # goes away instead.
        self.alternative_titles_label.setText(
            "Alternative titles: " + " · ".join(model.alternative_titles)
            if model.alternative_titles
            else ""
        )
        self.alternative_titles_label.setVisible(bool(model.alternative_titles))
        self.personal_match_label.setText(model.personal_match_text)
        self.score_value_label.setText(f"{model.personal_match:.1f}")
        self.mal_score_label.setText(model.mal_score_text)
        self.genres_label.setText(f"Genres: {model.genres_text}")
        self.episodes_label.setText(f"Episodes: {model.episodes_text}")
        self.status_label.setText(f"Status: {model.status}")
        self.year_label.setText(f"Airing year: {model.year_text}")
        aired_text = model.aired_text
        self.dates_label.setText(f"Aired: {aired_text}" if aired_text else "")
        self.dates_label.setVisible(aired_text is not None)
        self.synopsis_label.setText(model.synopsis)
        self.reason_label.setText(model.reason)
        contribution_text = self._contributions_text(model)
        self.contributions_label.setText(contribution_text)
        self._render_contributions(model)
        self.score_track.set_data(
            model.genre_contributions,
            model.personal_match,
            genres=model.genres,
            studios=model.studios,
        )
        contribution_sum = sum(value for _name, value in model.genre_contributions)
        if model.genre_contributions:
            self.sum_total_label.setText(
                f"{contribution_sum:.2f}  →  {model.personal_match:.1f}%"
            )
        else:
            self.sum_total_label.setText(f"{model.personal_match:.1f}%")
        self.mal_button.setEnabled(bool(model.mal_url))
        self._show_placeholder()
        cover_url = model.large_cover_url or model.cover_url
        if cover_url:
            self.cover_requested.emit(cover_url)
        self.synopsis_toggle.setChecked(False)
        self._pending_animation = True
        if self.isVisible():
            self.content_wipe.run()
            self._animate_score()

    def _render_contributions(self, model: RecommendationViewModel) -> None:
        while self.contribution_rows.count():
            item = self.contribution_rows.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not model.genre_contributions:
            fallback = QLabel(
                " · ".join(model.contributing_genres)
                if model.contributing_genres
                else NO_GENRE_CONTRIBUTIONS
            )
            fallback.setObjectName("recommendationScoreEmpty")
            fallback.setWordWrap(True)
            self.contribution_rows.addWidget(fallback)
            return

        for index, (name, value) in enumerate(model.genre_contributions):
            row = QFrame()
            row.setProperty("scoreContributor", True)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 6, 0, 6)
            row_layout.setSpacing(SPACE["sm"])
            swatch = QFrame()
            swatch.setFixedSize(9, 9)
            lowered = name.casefold()
            tone = "signal" if "community" in lowered or "viewer" in lowered else f"accent{min(index + 1, 4)}"
            if value < 0:
                tone = "negative"
            swatch.setProperty("contributionTone", tone)
            name_label = QLabel(str(name))
            name_label.setProperty("scoreContributorName", True)
            value_label = QLabel(f"{value:+.2f}")
            value_label.setObjectName("recommendationScoreContributionValue")
            row_layout.addWidget(swatch)
            row_layout.addWidget(name_label, 1)
            row_layout.addWidget(value_label)
            self.contribution_rows.addWidget(row)

    def set_navigation(self, index: int, total: int) -> None:
        total = max(1, int(total))
        index = max(1, min(int(index), total))
        self.navigation_label.setText(f"{index:02d} / {total:02d}")
        enabled = total > 1
        self.previous_button.setEnabled(enabled)
        self.next_button.setEnabled(enabled)

    def _set_synopsis_expanded(self, expanded: bool) -> None:
        self.synopsis_label.setVisible(bool(expanded))
        self.synopsis_toggle.setText(
            "HIDE SYNOPSIS  −" if expanded else "READ SYNOPSIS  +"
        )

    def _animate_score(self) -> None:
        if self.model is None:
            return
        self._pending_animation = False
        # The readout is already showing the final value from set_model(); only
        # the track reveals.
        self.score_track.animate()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt API
        super().showEvent(event)
        if self._pending_animation:
            QTimer.singleShot(70, self._animate_score)

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt API
        if event.key() == Qt.Key.Key_Left and self.previous_button.isEnabled():
            self.previous_requested.emit()
            return
        if event.key() == Qt.Key.Key_Right and self.next_button.isEnabled():
            self.next_requested.emit()
            return
        super().keyPressEvent(event)

    def set_local_state(
        self,
        *,
        hidden: bool,
        watch_later: bool,
        actions_enabled: bool,
    ) -> None:
        self.watch_later_button.setText(
            "Remove saved" if watch_later else "Watch Later"
        )
        self.watch_later_button.setChecked(watch_later)
        self.watch_later_button.setEnabled(actions_enabled)
        self.not_interested_button.setChecked(bool(hidden))
        self.not_interested_button.setText(
            "Show again" if hidden else "Not interested"
        )
        self.not_interested_button.setEnabled(actions_enabled)

    def set_cover_visible(self, visible: bool) -> None:
        self.cover_label.setVisible(visible)

    @staticmethod
    def _contributions_text(model: RecommendationViewModel) -> str:
        if model.genre_contributions:
            return "\n".join(
                f"{genre}: {score:+.2f}" for genre, score in model.genre_contributions
            )
        if model.contributing_genres:
            return " · ".join(model.contributing_genres)
        return NO_GENRE_CONTRIBUTIONS

    def set_cover_data(self, data: bytes) -> bool:
        source = QPixmap()
        if not source.loadFromData(data):
            self._show_placeholder()
            return False
        self.cover_label.setPixmap(_fit_detail_cover(source))
        return True

    def _show_placeholder(self) -> None:
        source = (
            title_placeholder_pixmap(
                self.model.display_title, (DETAIL_COVER_WIDTH, DETAIL_COVER_HEIGHT)
            )
            if self.model is not None
            else QPixmap()
        )
        if source.isNull():
            source = cover_placeholder_pixmap()
        if source.isNull():
            source = QPixmap(DETAIL_COVER_WIDTH, DETAIL_COVER_HEIGHT)
            source.fill(Qt.GlobalColor.transparent)
        self.cover_label.setPixmap(_fit_detail_cover(source))

    def _open_mal(self) -> None:
        if self.model is not None:
            open_mal_url(self.model.mal_url, opener=self._mal_opener)


def _fit_detail_cover(source: QPixmap) -> QPixmap:
    return rounded_cover(
        source,
        DETAIL_COVER_WIDTH,
        DETAIL_COVER_HEIGHT,
        RADIUS["md"],
    )
