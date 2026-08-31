"""Two colour choosers and a live preview, for the gradient theme.

Addresses: FEAT1 (live colour preview), BUG2 (the preview scales).

Qt has no CSS custom properties, so a theme is rendered from tokens rather
than declared. The preview here paints the same gradient the shell will use,
built from the same helper, so what is shown is what gets applied.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .design_tokens import gradient_palette


class GradientPreview(QWidget):
    """Paints the gradient, with sample text in the colour it will really use."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("gradientPreview")
        self.setMinimumHeight(72)
        self.setAccessibleName("Preview of the selected gradient")
        self._start = "#1B1A20"
        self._end = "#2A1D1B"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        self.title_label = QLabel("Your recommendations")
        self.title_label.setObjectName("gradientPreviewTitle")
        self.body_label = QLabel("Sample text on the gradient you chose.")
        self.body_label.setObjectName("gradientPreviewBody")
        layout.addWidget(self.title_label)
        layout.addWidget(self.body_label)
        layout.addStretch()
        self.set_colours(self._start, self._end)

    def set_colours(self, start: str, end: str) -> None:
        self._start, self._end = start, end
        # Derived by the same function the theme uses, so the preview cannot
        # promise something the applied theme will not deliver, including the
        # text colour chosen from the brightness of the two colours.
        colours = gradient_palette(start, end)
        self.setStyleSheet(
            f"QWidget#gradientPreview {{"
            f" background: qlineargradient(x1:0, y1:0, x2:1, y2:1,"
            f" stop:0 {start}, stop:1 {end});"
            f" border: 1px solid {colours['border']}; border-radius: 1px; }}"
            f" QLabel#gradientPreviewTitle {{ color: {colours['text_strong']};"
            f" font-weight: 700; background: transparent; }}"
            f" QLabel#gradientPreviewBody {{ color: {colours['text_muted']};"
            f" background: transparent; }}"
        )


class GradientPicker(QWidget):
    """Start and end colour buttons above a live preview."""

    # Emitted continuously while a colour is being chosen, for live preview.
    changed = Signal(str, str)
    # CHANGE [FEAT1]: emitted only when Done is pressed, so callers can tell
    # a preview apart from a value that should be written to the config.
    committed = Signal(str, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._start = "#1B1A20"
        self._end = "#2A1D1B"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.start_button = QPushButton()
        self.start_button.setObjectName("gradientStartButton")
        self.start_button.setAccessibleName("Choose the gradient start colour")
        self.start_button.clicked.connect(lambda: self._choose("start"))
        self.end_button = QPushButton()
        self.end_button.setObjectName("gradientEndButton")
        self.end_button.setAccessibleName("Choose the gradient end colour")
        self.end_button.clicked.connect(lambda: self._choose("end"))
        buttons.addWidget(self.start_button, 1)
        buttons.addWidget(self.end_button, 1)
        layout.addLayout(buttons)

        self.preview = GradientPreview()
        layout.addWidget(self.preview)
        self._refresh()

    @property
    def start(self) -> str:
        return self._start

    @property
    def end(self) -> str:
        return self._end

    def set_colours(self, start: str, end: str) -> None:
        self._start = _normalised(start, self._start)
        self._end = _normalised(end, self._end)
        self._refresh()

    def _choose(self, which: str) -> None:
        """Open the picker and follow the selection as it is dragged.

        CHANGE [FEAT1]: previously this used QColorDialog.getColor(), which is
        modal and only reports a colour once OK is pressed, so a user had to
        confirm, look at the result, and reopen the picker to judge it. The
        dialog now runs with currentColorChanged connected, so the interface
        updates while the selector is dragged.

        CHANGE [FEAT1]: the colour in force when the picker opened is captured
        first, and restored if the dialog is cancelled or closed, so nothing is
        committed until Done is pressed. QColorDialog already provides both
        buttons, so no new control is needed.
        """
        original_start, original_end = self._start, self._end
        current = QColor(self._start if which == "start" else self._end)

        dialog = QColorDialog(current, self)
        dialog.setWindowTitle(
            "Gradient start colour" if which == "start" else "Gradient end colour"
        )
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)

        def preview(colour: QColor) -> None:
            if not colour.isValid():
                return
            self._apply(which, colour.name().upper())
            # Live, but not committed: the caller repaints from these values.
            self.changed.emit(self._start, self._end)

        dialog.currentColorChanged.connect(preview)
        accepted = dialog.exec() == QColorDialog.DialogCode.Accepted

        if accepted and dialog.selectedColor().isValid():
            self._apply(which, dialog.selectedColor().name().upper())
        else:
            # CHANGE [FEAT1]: revert to the value captured at open time.
            self._start, self._end = original_start, original_end
            self._refresh()
        self.changed.emit(self._start, self._end)
        if accepted:
            self.committed.emit(self._start, self._end)

    def _apply(self, which: str, value: str) -> None:
        if which == "start":
            self._start = value
        else:
            self._end = value
        self._refresh()

    def _refresh(self) -> None:
        for button, colour, label in (
            (self.start_button, self._start, "From"),
            (self.end_button, self._end, "To"),
        ):
            button.setText(f"{label}  {colour}")
            readable = "#000000" if QColor(colour).lightness() > 127 else "#FFFFFF"
            button.setStyleSheet(
                f"background: {colour}; color: {readable};"
                " border: 1px solid rgba(128,128,128,0.5); border-radius: 1px;"
                " padding: 8px 10px; font-weight: 600;"
            )
        self.preview.set_colours(self._start, self._end)


def _normalised(value: object, fallback: str) -> str:
    colour = QColor(str(value or ""))
    return colour.name().upper() if colour.isValid() else fallback
