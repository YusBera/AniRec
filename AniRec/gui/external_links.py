"""Allow-listed outbound links.

Every URL the application can open is matched against an exact allow-list
before it reaches the system browser, so a value that ever comes from stored
settings or API data cannot turn a label into an arbitrary link.
"""

from __future__ import annotations

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices


MAL_API_CONFIG_URL = "https://myanimelist.net/apiconfig"

_ALLOWED = {
    ("myanimelist.net", "/apiconfig"),
}


def is_safe_external_url(url: str) -> bool:
    parsed = QUrl(url)
    return (
        parsed.isValid()
        and parsed.scheme().casefold() == "https"
        and (parsed.host().casefold(), parsed.path().rstrip("/").casefold()) in _ALLOWED
        and not parsed.hasQuery()
        and not parsed.hasFragment()
    )


def open_external_url(url: str) -> bool:
    if not is_safe_external_url(url):
        return False
    return QDesktopServices.openUrl(QUrl(url))
