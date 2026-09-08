"""Explainable GenreStat summary, relative bars, and detail table."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..models import GenreStat


NOT_RATED = "Not rated"
NO_EXAMPLES = "No examples available"


@dataclass(frozen=True)
class GenreStatViewModel:
    genre: str
    importance_score: float
    importance_text: str
    completed_count: int
    average_user_score: float | None
    average_user_score_text: str
    missing_score_count: int
    example_titles: tuple[str, ...]
    examples_text: str

    @classmethod
    def from_genre_stat(cls, stat: GenreStat) -> "GenreStatViewModel":
        importance = _finite(stat.importance_score) or 0.0
        average = _finite(stat.average_user_score)
        examples = tuple(
            text
            for value in stat.example_titles
            if (text := _clean_text(value)) is not None
        )
        return cls(
            genre=_clean_text(stat.genre) or "Unknown genre",
            importance_score=importance,
            importance_text=f"{importance:.2f}",
            completed_count=max(0, int(stat.completed_count)),
            average_user_score=average,
            average_user_score_text=(
                f"{average:.2f} / 10" if average is not None else NOT_RATED
            ),
            missing_score_count=max(0, int(stat.missing_score_count)),
            example_titles=examples,
            examples_text=" · ".join(examples) if examples else NO_EXAMPLES,
        )


def genre_stat_view_models(
    stats: tuple[GenreStat, ...] | list[GenreStat],
) -> tuple[GenreStatViewModel, ...]:
    models = tuple(GenreStatViewModel.from_genre_stat(stat) for stat in stats)
    return tuple(sorted(models, key=lambda item: -item.importance_score))


class GenreAnalysisPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page-genre-analysis")
        self.setAccessibleName("Genre Analysis page")
        self.models: tuple[GenreStatViewModel, ...] = ()
        self.metric_values: dict[str, QLabel] = {}
        self.bar_widgets: list[tuple[QLabel, QProgressBar, QLabel]] = []
        self._build_ui()
        self.set_genre_stats(())

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)
        title = QLabel("Genre Analysis")
        title.setObjectName("pageTitle")
        description = QLabel(
            "Understand which genres most strongly shape your personal recommendations."
        )
        description.setObjectName("pageDescription")
        description.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(description)

        self.empty_label = QLabel(
            "No genre analysis is available yet. Run recommendations from Home first."
        )
        self.empty_label.setObjectName("genreAnalysisEmptyState")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        root.addWidget(self.empty_label, 1)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("genreAnalysisScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 8, 8, 8)
        content_layout.setSpacing(16)

        metrics = QGridLayout()
        metrics.setSpacing(12)
        for column, (key, label) in enumerate(
            (
                ("genres", "Analyzed genres"),
                ("strongest", "Strongest genre"),
                ("completed", "Completed entries counted"),
                ("average", "Average user score"),
            )
        ):
            card = QFrame()
            card.setObjectName("dashboardMetricCard")
            layout = QVBoxLayout(card)
            caption = QLabel(label)
            caption.setObjectName("dashboardMetricLabel")
            value = QLabel("N/A")
            value.setObjectName("dashboardMetricValue")
            value.setWordWrap(True)
            self.metric_values[key] = value
            layout.addWidget(caption)
            layout.addWidget(value)
            metrics.addWidget(card, 0, column)
        content_layout.addLayout(metrics)

        bar_title = QLabel("Relative genre importance")
        bar_title.setObjectName("dashboardSectionTitle")
        bar_explanation = QLabel(
            "Bars compare each importance score with the strongest genre (100%). "
            "The exact calculated score is shown at the right."
        )
        bar_explanation.setObjectName("pageDescription")
        bar_explanation.setWordWrap(True)
        content_layout.addWidget(bar_title)
        content_layout.addWidget(bar_explanation)
        self.bars_frame = QFrame()
        self.bars_frame.setObjectName("genreBarsFrame")
        self.bars_layout = QVBoxLayout(self.bars_frame)
        self.bars_layout.setContentsMargins(12, 12, 12, 12)
        self.bars_layout.setSpacing(8)
        content_layout.addWidget(self.bars_frame)

        table_title = QLabel("Genre details")
        table_title.setObjectName("dashboardSectionTitle")
        content_layout.addWidget(table_title)
        self.table = QTableWidget(0, 6)
        self.table.setObjectName("genreAnalysisTable")
        self.table.setHorizontalHeaderLabels(
            (
                "Genre",
                "Importance score",
                "Completed anime",
                "Average user score",
                "Missing scores",
                "Top-rated examples",
            )
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        content_layout.addWidget(self.table)
        self.scroll.setWidget(content)
        root.addWidget(self.scroll, 1)

    def set_genre_stats(
        self, stats: tuple[GenreStat, ...] | list[GenreStat]
    ) -> None:
        self.models = genre_stat_view_models(stats)
        has_data = bool(self.models)
        self.empty_label.setVisible(not has_data)
        self.scroll.setVisible(has_data)
        if not has_data:
            self._clear_bars()
            self.table.setRowCount(0)
            return
        self._update_metrics()
        self._update_bars()
        self._update_table()

    def _update_metrics(self) -> None:
        available_scores = [
            model.average_user_score
            for model in self.models
            if model.average_user_score is not None
        ]
        self.metric_values["genres"].setText(str(len(self.models)))
        self.metric_values["strongest"].setText(self.models[0].genre)
        self.metric_values["completed"].setText(
            str(sum(model.completed_count for model in self.models))
        )
        self.metric_values["average"].setText(
            f"{sum(available_scores) / len(available_scores):.2f} / 10"
            if available_scores
            else NOT_RATED
        )

    def _clear_bars(self) -> None:
        while self.bars_layout.count():
            item = self.bars_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self.bar_widgets.clear()

    def _update_bars(self) -> None:
        self._clear_bars()
        strongest = max((model.importance_score for model in self.models), default=0.0)
        for model in self.models:
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            genre = QLabel(model.genre)
            genre.setObjectName("genreBarLabel")
            genre.setWordWrap(True)
            genre.setMinimumWidth(150)
            genre.setMaximumWidth(230)
            bar = QProgressBar()
            bar.setObjectName("genreImportanceBar")
            bar.setRange(0, 1000)
            relative = (
                max(0.0, model.importance_score) / strongest * 100
                if strongest > 0
                else 0.0
            )
            bar.setValue(round(relative * 10))
            bar.setFormat(f"{relative:.1f}% of strongest")
            exact = QLabel(model.importance_text)
            exact.setObjectName("genreImportanceExactScore")
            exact.setMinimumWidth(72)
            exact.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            layout.addWidget(genre)
            layout.addWidget(bar, 1)
            layout.addWidget(exact)
            self.bars_layout.addWidget(row)
            self.bar_widgets.append((genre, bar, exact))

    def _update_table(self) -> None:
        self.table.setRowCount(len(self.models))
        for row, model in enumerate(self.models):
            values = (
                model.genre,
                model.importance_text,
                str(model.completed_count),
                model.average_user_score_text,
                str(model.missing_score_count),
                model.examples_text,
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {1, 2, 3, 4}:
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                    )
                self.table.setItem(row, column, item)
        self.table.resizeColumnsToContents()
        self.table.setMinimumHeight(min(440, 72 + len(self.models) * 34))


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.casefold() in {"none", "nan", "null"}:
        return None
    return text


def _finite(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None
