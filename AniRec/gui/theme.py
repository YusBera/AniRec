"""Application-wide Qt theme and font scale management."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QPalette
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
        self.application.setProperty("resolvedSurface", colours["surface"])
        self.application.setProperty("resolvedWell", colours["well"])
        self.application.setProperty("resolvedBorder", colours["border"])
        self.application.setProperty("resolvedText", colours["text"])
        self.application.setProperty("resolvedTextSubtle", colours["text_subtle"])
        self.application.setProperty("resolvedSignal", colours["focus"])
        # The rail's ground. Published so a lamp can fill its own box with the
        # colour behind it and declare itself opaque: a translucent 16px widget
        # forces Qt to repaint every ancestor under it on each flicker tick,
        # which measured as 8 full-window repaints a second while idle.
        self.application.setProperty("resolvedSidebar", colours["sidebar"])
        # The dim wordmark on the "no artwork" plate. Published because Qt's
        # SVG renderer has no cascade, so the colour is substituted into the
        # placeholder's source text before it is rendered.
        self.application.setProperty("resolvedCoverMark", colours["border_strong"])
        # CHANGE [LINK]: rich text takes its anchor colour from
        # ``QPalette::Link``, never from a stylesheet ``color``. The sheet
        # declared ``QLabel#wizardApiLink { color: $accent_soft; }`` and that
        # rule has no effect on an <a> - the wizard's link shipped rendering
        # #99ebff, a blue belonging to no theme here, on the first screen a
        # new user sees. This is the same class of bug as the unstyled slider
        # that drew in the platform highlight colour.
        #
        # Set on the palette, so every rich-text link in the application is
        # fixed in one place rather than per label.
        link_palette = QPalette(self.application.palette())
        link_palette.setColor(QPalette.ColorRole.Link, QColor(colours["accent_soft"]))
        link_palette.setColor(
            QPalette.ColorRole.LinkVisited, QColor(colours["accent_soft"])
        )
        self.application.setPalette(link_palette)
        # Publish painted-widget colours before the style change event.  The
        # score rail and scanline panels then repaint in the incoming palette,
        # rather than briefly retaining the previous theme.
        self.application.setStyleSheet(
            self._load_stylesheet(self.active_theme) + self._glyph_rules(colours)
        )
        return self.active_theme

    @staticmethod
    def _glyph_rules(colours: dict) -> str:
        """Stylesheet rules that need a file on disk, built for this theme.

        CHANGE [AFFORDANCE]: the combo boxes had no drop-down indicator at
        all. ``QComboBox::drop-down`` was styled with a width and no image,
        and styling a sub-control makes Qt stop drawing its native part -
        measured as two distinct colours in the whole 28px arrow zone, both
        of them background. A select that looks exactly like a read-only text
        field is a control nobody knows they can open.

        Qt will not collapse a zero-sized bordered box into a triangle the way
        CSS does - that renders as a small rectangle - so this needs a real
        image, and an image needs a path that cannot live in the packaged
        sheet. Hence a runtime append.
        """
        from .resources import ui_icon_file

        path = ui_icon_file("chevron-down", colours.get("text_muted", "#849686"), 14)
        if path is None:
            return ""
        up = ui_icon_file("chevron-up", colours.get("text_muted", "#849686"), 14)
        url = str(path).replace("\\", "/")
        rules = [
            "\nQComboBox::drop-down { border: none; width: 26px; }",
            "QComboBox::down-arrow { image: url(%s); width: 12px; height: 12px; }" % url,
            "QComboBox::down-arrow:disabled { image: none; }",
        ]
        if up is not None:
            # CHANGE [AFFORDANCE]: the spin buttons were Qt's own, drawn in the
            # platform's light grey - the only controls in the app belonging to
            # no theme - and they forced the widget to 40px while every other
            # control measured 36. A size and a glyph settle both.
            up_url = str(up).replace("\\", "/")
            for kind in ("QSpinBox", "QDoubleSpinBox"):
                rules.extend(
                    [
                        "%s::up-button, %s::down-button {"
                        " subcontrol-origin: border; width: 20px; height: 17px;"
                        " border: none; background: transparent; }" % (kind, kind),
                        "%s::up-button { subcontrol-position: top right; }" % kind,
                        "%s::down-button { subcontrol-position: bottom right; }" % kind,
                        "%s::up-arrow { image: url(%s); width: 10px; height: 10px; }"
                        % (kind, up_url),
                        "%s::down-arrow { image: url(%s); width: 10px; height: 10px; }"
                        % (kind, url),
                    ]
                )
        tick = ui_icon_file(
            "check", colours.get("accent_contrast", "#0A0F0B"), 14
        )
        if tick is not None:
            # CHANGE [STATE]: a checked box was a filled accent square with
            # nothing in it - the shape a colour swatch has - so the only
            # thing separating on from off was fill. Qt stops drawing its own
            # indicator once the sub-control is restyled, which is why the
            # tick went missing in the first place. This puts one back, in the
            # contrast colour, because it sits on the accent.
            rules.append(
                "QCheckBox::indicator:checked {"
                " image: url(%s); }" % str(tick).replace("\\", "/")
            )
        return "\n".join(rules) + "\n"

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
