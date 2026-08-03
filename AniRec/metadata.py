"""Central application metadata shared by launchers and GUI surfaces."""

from __future__ import annotations

from . import __app_name__, __version__


APP_NAME = __app_name__
APP_VERSION = __version__
ORGANIZATION_NAME = "AniRec"
ORGANIZATION_DOMAIN = "github.com/YusBera/AniRec"

DEFAULT_WINDOW_WIDTH = 1280
DEFAULT_WINDOW_HEIGHT = 720
MINIMUM_WINDOW_WIDTH = 960
MINIMUM_WINDOW_HEIGHT = 600

APP_ICON_RESOURCE = "gui/resources/icons/anirec.svg"
