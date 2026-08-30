"""Safe accessors for packaged GUI resources."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ..infrastructure.paths import resource_path
from ..metadata import APP_ICON_RESOURCE


PLACEHOLDER_IMAGE_RESOURCE = "gui/resources/images/anime-placeholder.svg"
COVER_PLACEHOLDER_RESOURCE = "gui/resources/images/anime-cover-placeholder.svg"


def app_icon(*, base_override: str | Path | None = None) -> QIcon:
    path = resource_path(APP_ICON_RESOURCE, base_override=base_override)
    return QIcon(str(path)) if path.is_file() else QIcon()


def placeholder_pixmap(*, base_override: str | Path | None = None) -> QPixmap:
    path = resource_path(PLACEHOLDER_IMAGE_RESOURCE, base_override=base_override)
    return QPixmap(str(path)) if path.is_file() else QPixmap()


# Natural size of the cover placeholder artwork, and the theme roles its
# three substitutable colours are taken from.
COVER_PLACEHOLDER_SIZE = (440, 660)
COVER_PLACEHOLDER_ROLES = {
    "@ground@": ("resolvedWell", "#040806"),
    "@border@": ("resolvedBorder", "#1E2E24"),
    "@mark@": ("resolvedCoverMark", "#2E4636"),
}

_COVER_PLACEHOLDER_CACHE: dict[tuple[str, str, str], QPixmap] = {}


def cover_placeholder_pixmap(*, base_override: str | Path | None = None) -> QPixmap:
    """Render the "no artwork" plate in the colours of the active theme.

    The file used to be loaded straight through ``QPixmap``, so it shipped
    hardcoded neutral greys: correct against nothing, and in light mode four
    near-black slabs sat in a sage-paper interface. Qt's SVG renderer has no
    CSS cascade, so the palette is substituted into the source text before
    rendering, exactly as ``ui_icon_pixmap`` does for the interface icons.
    """
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    colours = {}
    for token, (role, fallback) in COVER_PLACEHOLDER_ROLES.items():
        value = application.property(role) if application is not None else None
        colours[token] = str(value or fallback)

    key = (colours["@ground@"], colours["@border@"], colours["@mark@"])
    cached = _COVER_PLACEHOLDER_CACHE.get(key)
    if cached is not None:
        return cached

    path = resource_path(COVER_PLACEHOLDER_RESOURCE, base_override=base_override)
    if not path.is_file():
        return QPixmap()
    source = path.read_text(encoding="utf-8")
    for token, colour in colours.items():
        source = source.replace(token, colour)

    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        return QPixmap()
    pixmap = QPixmap(*COVER_PLACEHOLDER_SIZE)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    _COVER_PLACEHOLDER_CACHE[key] = pixmap
    return pixmap


def clear_cover_placeholder_cache() -> None:
    """Drop the rendered plates so the next request re-renders per theme."""
    _COVER_PLACEHOLDER_CACHE.clear()
    _TITLE_PLACEHOLDER_CACHE.clear()


# CHANGE [SAMPLE-PLATE]: one identical grey "A" per card is why the sample
# library - the only thing most people ever see, because it is what the app
# opens on - reads as a broken image grid rather than as a feed. The bundled
# sample carries no artwork and should not: shipping other people's cover art
# inside the binary is a licensing decision, not a design one. So the plate
# stops pretending to be a missing image and becomes a legible stand-in
# instead: the title's own initials, on a ground whose hue is derived from
# the title, so eight cards are eight distinguishable objects. The same plate
# covers a live cover that failed to download.
_TITLE_PLACEHOLDER_CACHE: dict[tuple, QPixmap] = {}

# Hues are picked off a wheel rather than from a fixed list so that any title
# gets one, and the same title always gets the same one.
_PLATE_HUES = 12


def _plate_initials(title: str) -> str:
    """One or two letters that stand for a title on a small plate."""
    words = [word for word in str(title).replace(":", " ").split() if word]
    letters = [word[0] for word in words if word[0].isalnum()]
    if not letters:
        return "?"
    if len(letters) == 1:
        return letters[0].upper()
    return (letters[0] + letters[1]).upper()


def title_placeholder_pixmap(
    title: str, size: tuple[int, int] | None = None
) -> QPixmap:
    """A distinguishable stand-in plate for a title that has no artwork."""
    from hashlib import blake2s

    from PySide6.QtGui import QColor, QFont

    from .design_tokens import FONT_STACK_DISPLAY

    width, height = size or COVER_PLACEHOLDER_SIZE
    text = str(title or "").strip()
    if not text:
        return cover_placeholder_pixmap()

    ground = _resolved("resolvedWell", "#040806")
    border = _resolved("resolvedBorder", "#1E2E24")
    key = (text.casefold(), width, height, ground, border)
    cached = _TITLE_PLACEHOLDER_CACHE.get(key)
    if cached is not None:
        return cached

    digest = blake2s(text.casefold().encode("utf-8"), digest_size=4).digest()
    hue = int.from_bytes(digest, "big") % _PLATE_HUES * (360 // _PLATE_HUES)

    base = QColor(ground)
    tint = QColor.fromHsv(hue, 70, max(38, base.value() + 26))
    mark = QColor.fromHsv(hue, 46, 150)

    pixmap = QPixmap(width, height)
    pixmap.fill(tint)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setPen(QColor(border))
    painter.drawRect(0, 0, width - 1, height - 1)

    font = QFont()
    font.setFamilies([family.strip(' "') for family in FONT_STACK_DISPLAY.split(",")])
    font.setPixelSize(max(18, int(height * 0.30)))
    font.setWeight(QFont.Weight.Bold)
    painter.setFont(font)
    painter.setPen(mark)
    painter.drawText(
        pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), _plate_initials(text)
    )
    painter.end()

    _TITLE_PLACEHOLDER_CACHE[key] = pixmap
    return pixmap


def _resolved(role: str, fallback: str) -> str:
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    value = application.property(role) if application is not None else None
    return str(value or fallback)


FONT_RESOURCE_DIR = "gui/resources/fonts"

# The two faces the workstation design is drawn in. Both are SIL OFL 1.1,
# which is compatible with this project's GPL-3 licence; the licence texts
# ship beside the files and must stay there.
BUNDLED_FONTS = (
    "IBMPlexMono-Regular.ttf",
    "IBMPlexMono-Medium.ttf",
    "IBMPlexMono-SemiBold.ttf",
    "IBMPlexMono-Bold.ttf",
    "MartianMono.ttf",
)

_FONTS_LOADED = False


def load_bundled_fonts(*, base_override: str | Path | None = None) -> tuple[str, ...]:
    """Register the packaged faces with Qt, once per process.

    Every font stack in ``design_tokens`` still names a Windows face behind
    the bundled one, so a file that fails to load costs the design its exact
    typography and nothing else - which is why this reports what it loaded
    rather than raising.
    """
    global _FONTS_LOADED
    from PySide6.QtGui import QFontDatabase

    if _FONTS_LOADED:
        return ()
    loaded: list[str] = []
    for name in BUNDLED_FONTS:
        path = resource_path(f"{FONT_RESOURCE_DIR}/{name}", base_override=base_override)
        if not path.is_file():
            continue
        identifier = QFontDatabase.addApplicationFont(str(path))
        if identifier != -1:
            loaded.extend(QFontDatabase.applicationFontFamilies(identifier))
    _FONTS_LOADED = True
    return tuple(dict.fromkeys(loaded))


UI_ICON_RESOURCE_DIR = "gui/resources/icons/ui"

# Rendered from SVG at a few multiples so the strokes stay crisp on 125% and
# 150% displays rather than being scaled up from a 16px raster.
_ICON_RENDER_SIZES = (16, 20, 24, 32, 40, 48)

_UI_ICON_CACHE: dict[tuple[str, str, int], QPixmap] = {}


def _ui_icon_source(name: str, *, base_override: str | Path | None = None) -> str | None:
    """Read one interface icon, or None when the asset is absent."""
    path = resource_path(f"{UI_ICON_RESOURCE_DIR}/{name}.svg", base_override=base_override)
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return None


def ui_icon_pixmap(
    name: str,
    colour: str,
    size: int = 16,
    *,
    base_override: str | Path | None = None,
) -> QPixmap:
    """Render an interface icon tinted to one colour.

    The assets are authored with ``stroke="currentColor"`` so a single file
    serves every theme and every state. Qt's SVG renderer has no CSS cascade
    and paints ``currentColor`` as black, so the colour is substituted in the
    source text before rendering.
    """
    key = (str(name), str(colour), int(size))
    cached = _UI_ICON_CACHE.get(key)
    if cached is not None:
        return cached

    source = _ui_icon_source(name, base_override=base_override)
    if source is None:
        return QPixmap()
    tinted = source.replace("currentColor", str(colour))

    renderer = QSvgRenderer(QByteArray(tinted.encode("utf-8")))
    pixmap = QPixmap(int(size), int(size))
    pixmap.fill(Qt.GlobalColor.transparent)
    if renderer.isValid():
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        renderer.render(painter)
        painter.end()
    _UI_ICON_CACHE[key] = pixmap
    return pixmap


def ui_icon(
    name: str,
    colour: str,
    *,
    active_colour: str | None = None,
    base_override: str | Path | None = None,
) -> QIcon:
    """Build a multi-resolution QIcon for an interface glyph.

    When an ``-active`` companion exists it is used for the On state, so a
    checked control shows the knocked-out solid rather than the same outline
    in a different tint.
    """
    icon = QIcon()
    for size in _ICON_RENDER_SIZES:
        pixmap = ui_icon_pixmap(name, colour, size, base_override=base_override)
        if not pixmap.isNull():
            icon.addPixmap(pixmap, QIcon.Mode.Normal, QIcon.State.Off)

    on_name = f"{name}-active"
    on_colour = active_colour or colour
    for size in _ICON_RENDER_SIZES:
        pixmap = ui_icon_pixmap(on_name, on_colour, size, base_override=base_override)
        if not pixmap.isNull():
            icon.addPixmap(pixmap, QIcon.Mode.Normal, QIcon.State.On)
    if icon.availableSizes(QIcon.Mode.Normal, QIcon.State.On):
        return icon
    # No active variant on disk: reuse the outline so the On state is not blank.
    for size in _ICON_RENDER_SIZES:
        pixmap = ui_icon_pixmap(name, on_colour, size, base_override=base_override)
        if not pixmap.isNull():
            icon.addPixmap(pixmap, QIcon.Mode.Normal, QIcon.State.On)
    return icon


def ui_icon_file(
    name: str,
    colour: str,
    size: int = 12,
    *,
    base_override: str | Path | None = None,
) -> Path | None:
    """Write one tinted glyph to the cache and return its path.

    Qt stylesheets can only reach an image through ``url()``, and a path is
    not something the packaged stylesheet may contain - it would be baked to
    whichever machine generated it. So the sheet stays path-free and the one
    rule that needs a file is appended at runtime, pointing here.

    The file is rewritten whenever the colour changes, which is what makes it
    follow the theme; a QIcon's cached pixmaps would not.
    """
    from ..infrastructure.paths import cache_dir

    pixmap = ui_icon_pixmap(name, colour, size, base_override=base_override)
    if pixmap.isNull():
        return None
    directory = cache_dir() / "glyphs"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"{name}-{str(colour).lstrip('#')}-{int(size)}.png"
        if not target.is_file() and not pixmap.save(str(target), "PNG"):
            return None
    except OSError:
        return None
    return target


def clear_ui_icon_cache() -> None:
    """Drop rendered glyphs so a theme change re-tints them."""
    _UI_ICON_CACHE.clear()


def themed_ui_icon(name: str, role: str = "resolvedTextSubtle") -> QIcon:
    """Build an icon tinted from a colour the active theme has published.

    Falls back to the workstation defaults when no application is running,
    which keeps the loader usable from tests and from offscreen renders.
    """
    from PySide6.QtWidgets import QApplication

    defaults = {
        "resolvedAccent": "#C6A15B",
        "resolvedText": "#E9E5D6",
        "resolvedTextSubtle": "#7C8C80",
        "resolvedSignal": "#6FC6C0",
        "resolvedAccentContrast": "#0A120E",
    }
    application = QApplication.instance()
    value = application.property(role) if application is not None else None
    colour = str(value or defaults.get(role, "#7C8C80"))
    active = application.property("resolvedAccent") if application is not None else None
    return ui_icon(name, colour, active_colour=str(active or defaults["resolvedAccent"]))
