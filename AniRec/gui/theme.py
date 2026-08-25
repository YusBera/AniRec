"""Application-wide Qt theme and font scale management."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QApplication

from ..infrastructure.paths import resource_path
from ..models.domain import DEFAULT_GRADIENT_END, DEFAULT_GRADIENT_START
from .design_tokens import palette
from .qss_builder import DEFAULT_BASE_POINT_SIZE, build_stylesheet


MINIMUM_FONT_SCALE = 0.80
MAXIMUM_FONT_SCALE = 1.40


class ThemePreference(str, Enum):
    LIGHT = "light"
    DARK = "dark"
    OLED = "oled"
    GRADIENT = "gradient"
    SYSTEM = "system"




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
        self.gui_scale = 1.0
        self.gradient_start = DEFAULT_GRADIENT_START
        self.gradient_end = DEFAULT_GRADIENT_END
        self._base_font = QFont(application.font())
        # Follow the desktop when the user asked for "System". Without this the
        # app kept whichever mode was in force at startup until it was
        # restarted or the settings were saved again.
        try:
            application.styleHints().colorSchemeChanged.connect(
                self._on_color_scheme_changed
            )
        except (AttributeError, RuntimeError):
            # Older Qt builds do not expose the signal. Following the desktop
            # live is a convenience, never a requirement.
            pass

    def _on_color_scheme_changed(self, *_args) -> None:
        if self.requested_theme is ThemePreference.SYSTEM:
            self.apply(ThemePreference.SYSTEM, font_scale=self.font_scale)

    def apply(
        self,
        preference: ThemePreference | str,
        *,
        font_scale: float = 1.0,
        gradient_start: str | None = None,
        gradient_end: str | None = None,
        gui_scale: float = 1.0,
    ) -> ThemePreference:
        self.requested_theme = ThemePreference(preference)
        if gradient_start:
            self.gradient_start = gradient_start
        if gradient_end:
            self.gradient_end = gradient_end
        self.active_theme = self._resolve_theme(self.requested_theme)
        # CHANGE [BUG-SCALE-MATCH]: the readability bound belongs to the user's
        # font preference only. Multiplying the GUI scale in before clamping
        # meant a 1.5 interface scale was capped to 1.4 for text, so the
        # cards grew and the words in them did not, and nothing lined up.
        self.font_scale = max(MINIMUM_FONT_SCALE, min(MAXIMUM_FONT_SCALE, float(font_scale)))
        self.gui_scale = max(0.5, min(2.0, float(gui_scale)))

        self._apply_font_scale()
        self.application.setStyleSheet(self._load_stylesheet(self.active_theme))
        self.application.setProperty("themePreference", self.requested_theme.value)
        self.application.setProperty("activeTheme", self.active_theme.value)
        self.application.setProperty("fontScale", self.font_scale)
        # CHANGE [BUG-BADGE]: publish the resolved palette. Anything that
        # paints itself rather than being styled by QSS, such as the match
        # bar, needs the colours actually in force; asking for the palette
        # by theme name returned defaults for gradient and left the bar grey.
        colours = palette(
            self.active_theme.value,
            gradient_start=self.gradient_start,
            gradient_end=self.gradient_end,
        )
        self.application.setProperty("resolvedAccent", colours["accent"])
        self.application.setProperty("resolvedAccentContrast", colours["accent_contrast"])
        self.application.setProperty("resolvedBackground", colours["bg"])
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
        """Render the stylesheet for a theme at the current font scale.

        Generated rather than read from disk, so that font sizes can be scaled
        with the user's setting. The packaged .qss files remain the reference
        copy of the same output and are still used if generation ever fails.
        """
        try:
            return build_stylesheet(
                theme.value,
                base_point_size=self._base_point_size(),
                font_scale=self.font_scale * self.gui_scale,
                gradient_start=self.gradient_start,
                gradient_end=self.gradient_end,
            )
        except (KeyError, ValueError):
            return self._packaged_stylesheet(theme)

    def _packaged_stylesheet(self, theme: ThemePreference) -> str:
        stylesheet_path = resource_path(
            Path("gui") / "resources" / "styles" / f"{theme.value}.qss",
            base_override=self.resource_root,
        )
        try:
            return stylesheet_path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return ""

    def _base_point_size(self) -> float:
        size = self._base_font.pointSizeF()
        return size if size > 0 else DEFAULT_BASE_POINT_SIZE

    def _apply_font_scale(self) -> None:
        font = QFont(self._base_font)
        base_size = font.pointSizeF()
        if base_size <= 0:
            base_size = 10.0
        font.setPointSizeF(max(8.0, base_size * self.font_scale * self.gui_scale))
        self.application.setFont(font)
