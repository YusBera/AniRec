"""One line reporting what a MyAnimeList sync found.

Deliberately a strip notice rather than a modal or a notification centre.

The modal was the obvious first idea and the wrong one: it interrupts a
launch to say something that is at worst pleasant and at best a small
request, and a popup that fires on boot is the kind of thing people learn to
dismiss without reading. What is being reported here is not urgent - the
anime was finished days ago - so it earns a line, not a stop.

A notification centre was the second idea and is still too much. Rows would
have to be stored, ordered, individually dismissed and individually rendered
before any of it could say the one thing worth saying. This reads the current
snapshot, states it in a sentence, and offers exactly the two actions that
sentence supports.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QPushButton,
    QSizePolicy,
    QWidget,
)

try:
    from ..services.mal_sync_service import MalSyncState, SyncedCompletion
    from .recommendation_card import ElidingLabel, open_mal_url
except ImportError:  # Compatibility with the top-level import path.
    from gui.recommendation_card import ElidingLabel, open_mal_url
    from services.mal_sync_service import MalSyncState, SyncedCompletion


# Naming beats counting up to a point, and past it the line gets long enough
# to be elided - which loses a title rather than summarising it.
NAMED_LIMIT = 2


@dataclass(frozen=True)
class SyncNoticeContent:
    """What the strip should say, and what it can offer to do about it."""

    sentence: str
    rate_mal_id: int | None = None

    @property
    def is_empty(self) -> bool:
        return not self.sentence


def _join(titles: tuple[str, ...], remainder: int) -> str:
    """One "and", at the end, wherever the list stops.

    Joining the named titles with "and" and then appending "and N more"
    produced "C and B and 1 more" - two conjunctions doing one job. The comma
    carries the middle whenever there is anything after it.
    """
    if remainder <= 0:
        return " and ".join(titles)
    return f"{', '.join(titles)} and {remainder} more"


def _titles(records: tuple[SyncedCompletion, ...]) -> tuple[tuple[str, ...], int]:
    named = tuple(item.title for item in records[:NAMED_LIMIT] if item.title)
    return named, max(0, len(records) - len(named))


def build_notice(state: MalSyncState) -> SyncNoticeContent:
    """Turn a sync snapshot into one sentence.

    Pure, and separate from the widget, because the interesting part is the
    wording and the wording is what changes. Three cases in order of what the
    reader can act on:

    * Something AniRec recommended was finished and never rated. This is the
      only case with a request in it, so it leads and it names titles.
    * Something AniRec recommended was finished and rated. Nothing to do;
      worth saying once because it is the loop closing.
    * Something was finished that AniRec did not recommend. Reported without
      any claim of credit - it is why the title left the feed.
    """
    pending = state.unacknowledged
    if not pending:
        return SyncNoticeContent("")

    unscored = state.unscored
    if unscored:
        named, remainder = _titles(unscored)
        subject = _join(named, remainder) if named else f"{len(unscored)} anime"
        singular = len(unscored) == 1
        return SyncNoticeContent(
            f"You finished {subject}, and "
            f"{'it has' if singular else 'they have'} no score on "
            "MyAnimeList yet.",
            rate_mal_id=unscored[0].mal_id,
        )

    credited = tuple(item for item in pending if item.from_watch_later)
    if credited:
        named, remainder = _titles(credited)
        subject = _join(named, remainder) if named else f"{len(credited)} anime"
        return SyncNoticeContent(
            f"You finished {subject} from your Watch Later list. "
            "Moved out of the feed."
        )

    count = len(pending)
    # "you finished anime" is what a bare count of one produced, so the
    # singular gets an article rather than the number.
    noun = "an anime" if count == 1 else f"{count} anime"
    return SyncNoticeContent(
        f"MyAnimeList shows you finished {noun}. Removed from your feed."
    )


class SyncNotice(QFrame):
    """The strip line, and the two things it can do."""

    dismissed = Signal()
    rate_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("syncNotice")
        self._rate_mal_id: int | None = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Anime titles are long and this line shares a strip with the profile
        # and connection readouts, so the sentence has to be allowed to end
        # in an ellipsis. A plain QLabel clips it mid-word instead, which
        # reads as text running into the window edge rather than as text that
        # has been shortened - the same defect the cards fixed.
        self.message_label = ElidingLabel("")
        self.message_label.setObjectName("syncNoticeText")
        # Preferred, not Ignored: the label should ask for the width its
        # sentence actually needs, and give it up only when the strip is too
        # narrow to grant it. Ignored discards the request entirely, which
        # elided the line while a third of the strip sat empty beside it.
        self.message_label.setSizePolicy(
            QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred
        )
        self.message_label.setMinimumWidth(0)
        layout.addWidget(self.message_label, 1)

        self.rate_button = QPushButton("Rate it on MyAnimeList")
        self.rate_button.setObjectName("syncNoticeRateButton")
        self.rate_button.setProperty("buttonRole", "secondary")
        self.rate_button.clicked.connect(self._on_rate_clicked)
        layout.addWidget(self.rate_button)

        self.dismiss_button = QPushButton("Dismiss")
        self.dismiss_button.setObjectName("syncNoticeDismissButton")
        self.dismiss_button.setProperty("buttonRole", "ghost")
        self.dismiss_button.clicked.connect(self.dismissed.emit)
        layout.addWidget(self.dismiss_button)

        self.setVisible(False)

    def _on_rate_clicked(self) -> None:
        if self._rate_mal_id is not None:
            self.rate_requested.emit(self._rate_mal_id)

    def set_state(self, state: MalSyncState | None) -> None:
        content = build_notice(state) if state is not None else SyncNoticeContent("")
        self._rate_mal_id = content.rate_mal_id
        self.message_label.setText(content.sentence)
        self.rate_button.setVisible(content.rate_mal_id is not None)
        self.setVisible(not content.is_empty)


def open_mal_entry(mal_id: int, *, opener=QDesktopServices.openUrl) -> bool:
    """Open one anime's MyAnimeList page.

    Rating is done on MyAnimeList rather than here on purpose. Writing a score
    back needs the ``write:users`` scope, which the application does not ask
    for; sending somebody to the page that already does it is honest, and it
    is what the next sync will pick up.
    """
    return open_mal_url(f"https://myanimelist.net/anime/{int(mal_id)}", opener=opener)
