"""Application-wide Qt theme and font scale management."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from ..infrastructure.paths import resource_path


MINIMUM_FONT_SCALE = 0.80
MAXIMUM_FONT_SCALE = 1.40


class ThemePreference(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


_FALLBACK_STYLES = {
    ThemePreference.LIGHT: """
/* AniRec fallback light */
QWidget { background: #f7f8fc; color: #1d2433; }
QPushButton { background: #e7eaf3; border: 2px solid #a9b1c4; padding: 7px; }
QPushButton:hover { background: #dce2f2; }
QPushButton:focus { border: 2px solid #315bd6; }
QPushButton:disabled { color: #747b8b; background: #eceef3; }
QPushButton:checked { background: #315bd6; color: #ffffff; }
""",
    ThemePreference.DARK: """
/* AniRec fallback dark */
QWidget { background: #03050a; color: #f2f4fa; }
QPushButton { background: #111827; border: 2px solid #596176; padding: 7px; }
QPushButton:hover { background: #182238; }
QPushButton:focus { border: 2px solid #8da8ff; }
QPushButton:disabled { color: #8d94a8; background: #080c14; }
QPushButton:checked { background: #6f8cff; color: #10131a; }
""",
}


class ThemeManager:
    """Apply a resource-backed theme and bounded global font scale."""

    def __init__(
        self,
        application: QApplication,
        *,
        resource_root: str | Path | None = None,
    ) -> None:
        self.application = application
        self.resource_root = resource_root
        self.requested_theme = ThemePreference.SYSTEM
        self.active_theme = ThemePreference.LIGHT
        self.font_scale = 1.0
        self._base_font = QFont(application.font())

    def apply(
        self,
        preference: ThemePreference | str,
        *,
        font_scale: float = 1.0,
    ) -> ThemePreference:
        self.requested_theme = ThemePreference(preference)
        self.active_theme = self._resolve_theme(self.requested_theme)
        self.font_scale = max(MINIMUM_FONT_SCALE, min(MAXIMUM_FONT_SCALE, float(font_scale)))

        self.application.setStyleSheet(self._load_stylesheet(self.active_theme))
        self._apply_font_scale()
        self.application.setProperty("themePreference", self.requested_theme.value)
        self.application.setProperty("activeTheme", self.active_theme.value)
        self.application.setProperty("fontScale", self.font_scale)
        return self.active_theme

    def _resolve_theme(self, preference: ThemePreference) -> ThemePreference:
        if preference is not ThemePreference.SYSTEM:
            return preference

        style_hints = self.application.styleHints()
        color_scheme = style_hints.colorScheme()
        if color_scheme == Qt.ColorScheme.Dark:
            return ThemePreference.DARK
        if color_scheme == Qt.ColorScheme.Light:
            return ThemePreference.LIGHT

        window_color = self.application.palette().color(QPalette.ColorRole.Window)
        return ThemePreference.DARK if window_color.lightness() < 128 else ThemePreference.LIGHT

    def _load_stylesheet(self, theme: ThemePreference) -> str:
        stylesheet_path = resource_path(
            Path("gui") / "resources" / "styles" / f"{theme.value}.qss",
            base_override=self.resource_root,
        )
        try:
            stylesheet = stylesheet_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return _FALLBACK_STYLES[theme].strip()
        return stylesheet or _FALLBACK_STYLES[theme].strip()

    def _apply_font_scale(self) -> None:
        font = QFont(self._base_font)
        base_size = font.pointSizeF()
        if base_size <= 0:
            base_size = 10.0
        font.setPointSizeF(max(8.0, base_size * self.font_scale))
        self.application.setFont(font)
