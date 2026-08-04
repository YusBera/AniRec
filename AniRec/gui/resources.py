"""Safe accessors for packaged GUI resources."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap

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


def cover_placeholder_pixmap(*, base_override: str | Path | None = None) -> QPixmap:
    path = resource_path(COVER_PLACEHOLDER_RESOURCE, base_override=base_override)
    return QPixmap(str(path)) if path.is_file() else QPixmap()
