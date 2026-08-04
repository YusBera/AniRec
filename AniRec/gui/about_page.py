"""About page with license attribution and guarded external links."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from ..metadata import APP_NAME, APP_VERSION
from .texts import UI_TEXT


PROJECT_GITHUB_URL = "https://github.com/YusBera/AniRec"


def is_safe_project_url(url: str) -> bool:
    parsed = QUrl(url)
    return (
        parsed.isValid()
        and parsed.scheme().casefold() == "https"
        and parsed.host().casefold() == "github.com"
        and parsed.path().rstrip("/").casefold() == "/yusbera/anirec"
        and not parsed.hasQuery()
        and not parsed.hasFragment()
    )


def open_project_url(url: str) -> bool:
    if not is_safe_project_url(url):
        return False
    return QDesktopServices.openUrl(QUrl(url))


class AboutPage(QWidget):
    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        url_opener: Callable[[str], bool] = open_project_url,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("page-about")
        self.setAccessibleName("About page")
        self._url_opener = url_opener

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title = self._label(f"{APP_NAME} {APP_VERSION}", "pageTitle")
        description = self._label(UI_TEXT.about_description, "aboutDescription")
        owner = self._label(UI_TEXT.about_owner, "aboutOwner")
        contribution = self._label(UI_TEXT.about_gui_contribution, "aboutGuiContribution")
        license_label = self._label(UI_TEXT.about_license, "aboutLicense")
        libraries = self._label(UI_TEXT.about_libraries, "aboutLibraries")
        notice = self._label(UI_TEXT.about_unofficial_notice, "aboutUnofficialNotice")

        self.github_link = QLabel(
            f'<a href="{PROJECT_GITHUB_URL}">{UI_TEXT.github_link_label}</a>'
        )
        self.github_link.setObjectName("aboutGithubLink")
        self.github_link.setAccessibleName("Open the AniRec GitHub repository")
        self.github_link.setTextInteractionFlags(Qt.TextInteractionFlag.LinksAccessibleByKeyboard)
        self.github_link.setOpenExternalLinks(False)
        self.github_link.linkActivated.connect(self._open_link)

        for widget in (
            title,
            description,
            owner,
            contribution,
            license_label,
            self.github_link,
            libraries,
            notice,
        ):
            layout.addWidget(widget)
        layout.addStretch()

    @staticmethod
    def _label(text: str, object_name: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setWordWrap(True)
        return label

    def _open_link(self, url: str) -> None:
        if is_safe_project_url(url):
            self._url_opener(url)

    def complete_text(self) -> str:
        return "\n".join(
            label.text()
            for label in self.findChildren(QLabel)
            if label is not self.github_link
        )
