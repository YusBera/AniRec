"""The genre and studio search box, and the list it drops beneath itself.

Written rather than assembled from QCompleter for one reason: a completer
offers strings, and this has to offer *typed* things. "Shaft // Studio" and
"Psychological // Genre" are different filters that happen to be spelled
differently, and the reader has to be able to see which is which before
choosing, not after.

Keyboard first. Down and Up walk the list, Enter takes the highlighted
suggestion, Escape closes without choosing, and the field keeps focus
throughout so typing never has to stop. The list is a child widget rather than
a popup window: a popup is a second top-level window that Qt will happily show
in the wrong place on a multi-monitor setup, and this only ever has to appear
directly under a field it already knows the position of.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import SPACE
from ..presentation.filters import FilterKind
from ..presentation.metadata_index import MetadataCatalog, MetadataSuggestion
from .resources import themed_ui_icon
from .scaling import scaled
from .texts import FILTER_TEXT


# How tall the suggestion list may grow. Four rows and a bit, so it is
# obviously scrollable when there are more without covering the results.
MAXIMUM_LIST_HEIGHT = 168
SUGGESTION_ROW_HEIGHT = 26


class MetadataTypeahead(QWidget):
    """A labelled field that turns typing into one genre or studio filter."""

    suggestion_chosen = Signal(object)

    def __init__(
        self,
        catalog: MetadataCatalog,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.setObjectName("metadataTypeahead")
        self._suggestions: tuple[MetadataSuggestion, ...] = ()
        self._active_filters: tuple[tuple[FilterKind, str], ...] = ()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["xs"]))

        # A real label, associated with the field by buddy, rather than a
        # placeholder. Placeholder text disappears the moment anyone types,
        # which is exactly when a person who cannot see the field needs it.
        self.label = QLabel(FILTER_TEXT.search_label)
        self.label.setObjectName("filterControlLabel")
        layout.addWidget(self.label)

        self.field = QLineEdit()
        self.field.setObjectName("metadataTypeaheadInput")
        self.field.setPlaceholderText(FILTER_TEXT.search_placeholder)
        self.field.setAccessibleName(FILTER_TEXT.search_accessible)
        self.field.setClearButtonEnabled(True)
        self.field.addAction(
            themed_ui_icon("search"), QLineEdit.ActionPosition.LeadingPosition
        )
        self.label.setBuddy(self.field)
        layout.addWidget(self.field)

        self.suggestion_list = QListWidget(self)
        self.suggestion_list.setObjectName("metadataSuggestionList")
        self.suggestion_list.setFrameShape(QFrame.Shape.NoFrame)
        self.suggestion_list.setMaximumHeight(scaled(MAXIMUM_LIST_HEIGHT))
        self.suggestion_list.setUniformItemSizes(True)
        self.suggestion_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        # The field keeps focus while the list is walked, so the caret never
        # leaves the text and typing can continue mid-selection.
        self.suggestion_list.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.suggestion_list.setVisible(False)
        layout.addWidget(self.suggestion_list)

        self.empty_label = QLabel(FILTER_TEXT.search_no_results)
        self.empty_label.setObjectName("metadataSuggestionEmpty")
        self.empty_label.setWordWrap(True)
        self.empty_label.setVisible(False)
        layout.addWidget(self.empty_label)

        self.field.textEdited.connect(self._on_text_edited)
        self.field.installEventFilter(self)
        self.suggestion_list.itemClicked.connect(self._on_item_clicked)

    # ---- state -----------------------------------------------------------

    def set_active_filters(self, pairs) -> None:
        """Tell the box what is already on, so it stops offering it.

        A suggestion that is already an active filter is a dead row: choosing
        it changes nothing, and the reader has to work out why. Hiding it is
        also what keeps a duplicate pill from being possible at this entry
        point at all.
        """
        self._active_filters = tuple(pairs or ())
        if self.suggestion_list.isVisible():
            self._refresh(self.field.text())

    def clear(self) -> None:
        self.field.clear()
        self._close_list()

    @property
    def suggestions(self) -> tuple[MetadataSuggestion, ...]:
        return self._suggestions

    @property
    def is_open(self) -> bool:
        return self.suggestion_list.isVisible()

    # ---- behaviour -------------------------------------------------------

    def _on_text_edited(self, text: str) -> None:
        self._refresh(text)

    def _refresh(self, text: str) -> None:
        query = str(text or "").strip()
        if not query:
            self._close_list()
            return
        self._suggestions = self.catalog.search(query, exclude=self._active_filters)
        self.suggestion_list.clear()
        for suggestion in self._suggestions:
            item = QListWidgetItem(
                FILTER_TEXT.search_suggestion.format(
                    value=suggestion.value, type=suggestion.type_label
                )
            )
            item.setData(Qt.ItemDataRole.UserRole, suggestion)
            item.setSizeHint(
                item.sizeHint().expandedTo(
                    item.sizeHint().__class__(0, scaled(SUGGESTION_ROW_HEIGHT))
                )
            )
            self.suggestion_list.addItem(item)

        has_results = bool(self._suggestions)
        self.suggestion_list.setVisible(has_results)
        # An empty result is a real answer, not a reason to show nothing: a
        # box that silently stops responding reads as broken.
        self.empty_label.setVisible(not has_results)
        self.empty_label.setText(FILTER_TEXT.search_no_results_for.format(query=query))
        if has_results:
            self.suggestion_list.setCurrentRow(0)

    def _close_list(self) -> None:
        self._suggestions = ()
        self.suggestion_list.clear()
        self.suggestion_list.setVisible(False)
        self.empty_label.setVisible(False)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        suggestion = item.data(Qt.ItemDataRole.UserRole)
        if suggestion is not None:
            self._choose(suggestion)

    def _choose(self, suggestion: MetadataSuggestion) -> None:
        self.field.clear()
        self._close_list()
        self.suggestion_chosen.emit(suggestion)

    def _step(self, offset: int) -> None:
        count = self.suggestion_list.count()
        if count == 0:
            return
        current = self.suggestion_list.currentRow()
        # Wrapping, because a list this short is faster to walk round than to
        # back out of.
        self.suggestion_list.setCurrentRow((current + offset) % count)

    def eventFilter(self, watched, event) -> bool:
        if watched is not self.field or event.type() != QEvent.Type.KeyPress:
            return super().eventFilter(watched, event)
        key = event.key()
        if key == Qt.Key.Key_Down and self.suggestion_list.isVisible():
            self._step(1)
            return True
        if key == Qt.Key.Key_Up and self.suggestion_list.isVisible():
            self._step(-1)
            return True
        if key == Qt.Key.Key_Escape:
            if self.suggestion_list.isVisible() or self.empty_label.isVisible():
                self._close_list()
                return True
            return super().eventFilter(watched, event)
        if key in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            item = self.suggestion_list.currentItem()
            if self.suggestion_list.isVisible() and item is not None:
                suggestion = item.data(Qt.ItemDataRole.UserRole)
                if suggestion is not None:
                    self._choose(suggestion)
                    return True
            # Enter with nothing highlighted is not an error and not a filter
            # either. Swallowing it stops the surrounding form treating a
            # search as a submission of something else.
            return True
        return super().eventFilter(watched, event)


class ProfileInput(QWidget):
    """The "add a friend's list" field, and the ceiling it enforces.

    Kept beside the typeahead because it is the same shape of control - a
    labelled field that turns text into a pill - but it is a separate widget
    because what it produces is not a catalogue term. A username is not
    something the frontend can validate against anything it already has, so
    this only normalises and hands it on.
    """

    profile_submitted = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileInput")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["xs"]))

        self.label = QLabel(FILTER_TEXT.profile_label)
        self.label.setObjectName("filterControlLabel")
        layout.addWidget(self.label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(scaled(SPACE["sm"]))
        self.field = QLineEdit()
        self.field.setObjectName("profileInputField")
        self.field.setPlaceholderText(FILTER_TEXT.profile_placeholder)
        self.field.setAccessibleName(FILTER_TEXT.profile_accessible)
        # MAL's own ceiling. Stops a paste of something that is plainly not a
        # username from reaching the request at all.
        self.field.setMaxLength(64)
        self.label.setBuddy(self.field)
        self.field.returnPressed.connect(self._submit)
        row.addWidget(self.field, 1)

        from PySide6.QtWidgets import QPushButton

        self.add_button = QPushButton(FILTER_TEXT.profile_add)
        self.add_button.setObjectName("profileInputAdd")
        self.add_button.setProperty("buttonRole", "secondary")
        self.add_button.setAccessibleName(FILTER_TEXT.profile_add_accessible)
        self.add_button.clicked.connect(self._submit)
        row.addWidget(self.add_button)
        layout.addLayout(row)

        self.message_label = QLabel("")
        self.message_label.setObjectName("profileInputMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(False)
        # Tied to the field, so a reader who lands on the input is told what
        # went wrong there rather than having to find the sentence themselves.
        self.field.setAccessibleDescription("")
        layout.addWidget(self.message_label)

    def _submit(self) -> None:
        text = self.field.text().strip()
        if not text:
            return
        self.profile_submitted.emit(text)

    def accept(self) -> None:
        """Clear the field after a username was taken."""
        self.field.clear()
        self.set_message("")

    def set_message(self, message: str, *, tone: str = "error") -> None:
        self.message_label.setText(message or "")
        self.message_label.setProperty("tone", tone if message else "")
        self.message_label.setVisible(bool(message))
        self.field.setAccessibleDescription(message or "")
        self.message_label.style().unpolish(self.message_label)
        self.message_label.style().polish(self.message_label)

    def set_limit_reached(self, reached: bool) -> None:
        """Say why the control stopped working, in the place it stopped.

        Disabling a field with no explanation is the version of this that
        looks like a bug. The ceiling is a decision this interface made, so it
        says so where the decision is felt.
        """
        self.field.setEnabled(not reached)
        self.add_button.setEnabled(not reached)
        if reached:
            self.set_message(FILTER_TEXT.profile_limit, tone="warn")
        elif self.message_label.text() == FILTER_TEXT.profile_limit:
            self.set_message("")
