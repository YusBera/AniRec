"""Detects widgets that become top-level windows by accident.

Addresses: BUG1 (windows flashing open and shut on almost any interaction).

In Qt a widget with no parent *is* a window. Calling setVisible(True) or
show() on a widget before a layout has adopted it therefore opens a real
top-level window, which then disappears as soon as the layout takes it. The
symptom is a blank frame with a title bar that flickers for a moment, and it
is easy to write by accident because the code reads as if it only sets a flag.

This guard watches for it. It is a diagnostic, not a workaround: it reports
the offending widget and the call stack so the cause can be fixed at source.
Attach it in tests, or set ANIREC_GUARD_STRAY_WINDOWS=1 to log at runtime.
"""

from __future__ import annotations

import logging
import traceback
from dataclasses import dataclass, field

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QDialog, QMainWindow, QMenu, QWidget


LOGGER = logging.getLogger("AniRec.gui")

# Types that are supposed to be windows.
INTENTIONAL_WINDOWS = (QDialog, QMainWindow, QMenu)

# Qt gives every top-level widget a window *type*, and most of them are
# legitimate: a tooltip, a combo box popup and a tool window are all top-level
# by design. Only a plain Window is suspicious, because that is what a widget
# becomes when setParent(None) orphans it or when it is shown before a layout
# adopts it. Watching isWindow() alone reported every tooltip in the app.
SUSPICIOUS_WINDOW_TYPES = (Qt.WindowType.Window,)


@dataclass
class StrayWindow:
    class_name: str
    object_name: str
    width: int
    height: int
    window_type: str = "Window"
    stack: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        where = "\n    ".join(self.stack) or "<no application frames>"
        return (
            f"{self.class_name}(objectName={self.object_name!r}) "
            f"{self.width}x{self.height} was shown as a top-level window.\n"
            f"    {where}"
        )


class StrayWindowGuard(QObject):
    """Records every widget shown as a window that was never meant to be one."""

    def __init__(self, *, log: bool = True) -> None:
        super().__init__()
        self.sightings: list[StrayWindow] = []
        self._log = log
        self._allowed: set[int] = set()

    def allow(self, widget: QWidget) -> None:
        """Treat this widget as a legitimate window.

        A test usually shows the widget under test with no parent, which makes
        it a window by definition. That is the harness, not the defect.
        """
        self._allowed.add(id(widget))

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if event.type() is QEvent.Type.Show and isinstance(watched, QWidget):
            if (
                watched.isWindow()
                and watched.windowType() in SUSPICIOUS_WINDOW_TYPES
                and not isinstance(watched, INTENTIONAL_WINDOWS)
                and id(watched) not in self._allowed
            ):
                sighting = StrayWindow(
                    class_name=type(watched).__name__,
                    object_name=watched.objectName(),
                    width=watched.width(),
                    height=watched.height(),
                    window_type=watched.windowType().name,
                    stack=[
                        f"{frame.filename}:{frame.lineno} in {frame.name}"
                        for frame in traceback.extract_stack()[:-1]
                        if "AniRec" in frame.filename
                    ][-6:],
                )
                self.sightings.append(sighting)
                if self._log:
                    LOGGER.warning("Stray top-level window: %s", sighting)
        return False


def install(application: QApplication | None = None, *, log: bool = True) -> StrayWindowGuard:
    """Attach a guard and return it. The caller must keep the reference.

    Qt does not own event filters, so a guard that is not stored is collected
    immediately and silently watches nothing.
    """
    application = application or QApplication.instance()
    if application is None:
        raise RuntimeError("A QApplication must exist before installing the guard.")
    guard = StrayWindowGuard(log=log)
    application.installEventFilter(guard)
    return guard
