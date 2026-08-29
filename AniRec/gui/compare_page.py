"""Compare: how one MyAnimeList profile lines up with yours.

The surface is deliberately the same machine as the rest of the application.
It borrows the panel from Discover's header, the readout pairs from the
navigation rail, the large accent number from the score inspector, and the
anime card from the feed. Nothing here is a dashboard: a compatibility figure
is one number on a panel with its supporting counts beside it, not a ring
inside a rounded tile with three siblings.

What it does *not* do is work anything out. Every figure on this page - the
score, the label, the counts, which anime belong in which section and in what
order - arrives prepared from a ``CompatibilityProvider``. That boundary is
the point of the file; see ``compatibility.py`` for why.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .compatibility import (
    CompatibilityReport,
    CompatibilityUnavailable,
    FriendSummary,
    UnavailableReason,
)
from .design_tokens import SPACE
from .instrument_widgets import InstrumentPanel
from .recommendation_card import CARD_WIDTH, RecommendationCard
from .resources import themed_ui_icon, ui_icon_pixmap
from .scaling import scaled
from .texts import COMPARE_TEXT


# Which state panel a refusal turns into. Kept as a table rather than a chain
# of ifs so that adding a reason means adding a row, and so the mapping can be
# read at a glance against the reasons the provider is allowed to return.
STATE_FOR_REASON = {
    UnavailableReason.USER_NOT_FOUND: (
        COMPARE_TEXT.not_found_title,
        COMPARE_TEXT.not_found_message,
        "search",
        "error",
        True,
    ),
    UnavailableReason.PRIVATE_LIST: (
        COMPARE_TEXT.private_title,
        COMPARE_TEXT.private_message,
        "hide",
        "",
        False,
    ),
    UnavailableReason.NETWORK: (
        COMPARE_TEXT.network_title,
        COMPARE_TEXT.network_message,
        "connect",
        "error",
        True,
    ),
    UnavailableReason.API_UNAVAILABLE: (
        COMPARE_TEXT.api_title,
        COMPARE_TEXT.api_message,
        "sync",
        "error",
        True,
    ),
    UnavailableReason.NOT_CONNECTED: (
        COMPARE_TEXT.not_connected_title,
        COMPARE_TEXT.not_connected_message,
        "profile",
        "",
        False,
    ),
    UnavailableReason.FRIENDS_PRIVATE: (
        COMPARE_TEXT.private_title,
        COMPARE_TEXT.friends_private,
        "profile",
        "",
        False,
    ),
    UnavailableReason.BACKEND_MISSING: (
        COMPARE_TEXT.backend_title,
        COMPARE_TEXT.backend_message,
        "details-inspector",
        "",
        False,
    ),
}


def _resolved_colour(role: str, fallback: str) -> str:
    from PySide6.QtWidgets import QApplication

    application = QApplication.instance()
    value = application.property(role) if application is not None else None
    return str(value or fallback)


class StatePanel(QFrame):
    """One centred explanation: waiting, empty, or broken.

    A failure and an absence must not look the same, so the panel carries a
    tone the stylesheet reads. "Their list is private" is an absence and stays
    neutral; "MyAnimeList is unreachable" is a fault and takes the danger
    role. Both offer an action only when there is one worth offering - a retry
    on a private list is the same refusal a second time.
    """

    retry_requested = Signal()
    secondary_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("compareStatePanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACE["3xl"], SPACE["2xl"], SPACE["3xl"], SPACE["2xl"]
        )
        layout.setSpacing(SPACE["md"])
        layout.addStretch()

        self.icon_label = QLabel()
        self.icon_label.setObjectName("compareStateIcon")
        self.icon_label.setFixedSize(scaled(48), scaled(48))
        self.icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_name = "profile"
        layout.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignHCenter)

        self.title_label = QLabel("")
        self.title_label.setObjectName("compareStateTitle")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)

        self.message_label = QLabel("")
        self.message_label.setObjectName("compareStateMessage")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setMaximumWidth(scaled(560))
        # DEFECT: this used to be added straight to the column with
        # AlignHCenter. An alignment flag makes QBoxLayout hand the item its
        # size hint and stop asking heightForWidth, and a word-wrapped label's
        # hint is one line - so every message longer than one line was drawn
        # clipped, overlapping the title above it. Centring it with stretches
        # instead leaves the item unaligned, which is what keeps the wrap
        # height being asked for and honoured.
        message_row = QHBoxLayout()
        message_row.setContentsMargins(0, 0, 0, 0)
        message_row.addStretch(1)
        message_row.addWidget(self.message_label)
        message_row.addStretch(1)
        layout.addLayout(message_row)

        actions = QHBoxLayout()
        actions.setSpacing(SPACE["sm"])
        actions.addStretch()
        self.retry_button = QPushButton(COMPARE_TEXT.retry)
        self.retry_button.setObjectName("compareStateRetry")
        self.retry_button.setProperty("buttonRole", "secondary")
        self.retry_button.clicked.connect(self.retry_requested.emit)
        self.retry_button.setVisible(False)
        actions.addWidget(self.retry_button)
        self.secondary_button = QPushButton("")
        self.secondary_button.setObjectName("compareStateSecondary")
        self.secondary_button.setProperty("buttonRole", "ghost")
        self.secondary_button.clicked.connect(self.secondary_requested.emit)
        self.secondary_button.setVisible(False)
        actions.addWidget(self.secondary_button)
        actions.addStretch()
        layout.addLayout(actions)
        layout.addStretch()

    def show_state(
        self,
        title: str,
        message: str,
        *,
        icon: str = "profile",
        tone: str = "",
        retry: bool = False,
        secondary: str = "",
    ) -> None:
        self.title_label.setText(title)
        self.message_label.setText(message)
        self.retry_button.setVisible(bool(retry))
        self.secondary_button.setText(secondary)
        self.secondary_button.setVisible(bool(secondary))
        self.setProperty("stateTone", tone)
        self.style().unpolish(self)
        self.style().polish(self)
        self._set_icon(icon, tone)

    def _set_icon(self, name: str, tone: str) -> None:
        """Paint the mark in the tone the panel is in.

        A QLabel pixmap does not read the stylesheet's ``color``, so the
        colour has to be handed to the renderer - the same reason the feed's
        empty state does it this way.
        """
        self._icon_name = name
        role = "resolvedDanger" if tone == "error" else "resolvedCoverMark"
        fallback = "#D98363" if tone == "error" else "#2E4636"
        pixmap = ui_icon_pixmap(name, _resolved_colour(role, fallback), scaled(28))
        if pixmap.isNull():
            self.icon_label.clear()
        else:
            self.icon_label.setPixmap(pixmap)

    def retint_icons(self) -> None:
        self._set_icon(self._icon_name, str(self.property("stateTone") or ""))


class CompatibilityHeader(InstrumentPanel):
    """The headline: who, how well, and the three counts behind it.

    The score is one large number in the accent - the same treatment, at the
    same size, the score inspector gives a personal match, because it is the
    same kind of fact. The counts sit beside it as rail readouts rather than
    as tiles: they explain the score, they are not four independent metrics.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("compatibilityHeader")
        self._friend_username = ""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACE["xl"], SPACE["lg"], SPACE["xl"], SPACE["lg"])
        layout.setSpacing(SPACE["xl"])

        identity = QVBoxLayout()
        identity.setSpacing(SPACE["hair"])
        legend_row = QHBoxLayout()
        legend_row.setSpacing(SPACE["sm"])
        self.legend_label = QLabel(COMPARE_TEXT.legend)
        self.legend_label.setObjectName("compatibilityLegend")
        legend_row.addWidget(self.legend_label)
        self.sample_stamp = QLabel(COMPARE_TEXT.sample_stamp)
        self.sample_stamp.setObjectName("compatibilitySampleStamp")
        self.sample_stamp.setToolTip(COMPARE_TEXT.sample_stamp_tooltip)
        self.sample_stamp.setVisible(False)
        legend_row.addWidget(self.sample_stamp)
        legend_row.addStretch(1)
        identity.addLayout(legend_row)

        self.username_label = QLabel("")
        self.username_label.setObjectName("compatibilityUsername")
        # A MAL username runs to 64 characters and this is the largest type on
        # the panel, so it elides rather than pushing the score off the edge.
        self.username_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        identity.addWidget(self.username_label)
        self.match_label = QLabel("")
        self.match_label.setObjectName("compatibilityMatchLabel")
        identity.addWidget(self.match_label)
        layout.addLayout(identity, 1)

        score_block = QVBoxLayout()
        score_block.setSpacing(0)
        score_caption = QLabel(COMPARE_TEXT.score_caption)
        score_caption.setObjectName("compatibilityScoreCaption")
        score_caption.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.score_label = QLabel("N/A")
        self.score_label.setObjectName("compatibilityScore")
        self.score_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        score_block.addWidget(score_caption)
        score_block.addWidget(self.score_label)
        layout.addLayout(score_block)

        stats = QGridLayout()
        stats.setHorizontalSpacing(SPACE["lg"])
        stats.setVerticalSpacing(0)
        self.stat_values: dict[str, QLabel] = {}
        for column, (key, caption) in enumerate(
            (
                ("total", COMPARE_TEXT.stat_total),
                ("shared", COMPARE_TEXT.stat_shared),
                ("both_rated", COMPARE_TEXT.stat_both_rated),
            )
        ):
            caption_label = QLabel(caption)
            caption_label.setObjectName("compatibilityStatKey")
            value_label = QLabel("N/A")
            value_label.setObjectName("compatibilityStatValue")
            value_label.setAccessibleName(caption)
            stats.addWidget(caption_label, 0, column)
            stats.addWidget(value_label, 1, column)
            self.stat_values[key] = value_label
        layout.addLayout(stats)

    def set_summary(self, friend: FriendSummary, *, is_sample: bool = False) -> None:
        self._friend_username = friend.username
        self._render_username()
        self.username_label.setToolTip(friend.username)
        self.username_label.setAccessibleName(
            f"Compatibility with {friend.username}"
        )
        self.score_label.setText(friend.match_score_text)
        # The percentage on its own is a number in a large font. What it means
        # is the label beside it, and a screen reader gets both in one string.
        self.score_label.setAccessibleName(
            f"Match score {friend.match_score_text}"
            + (f", {friend.match_label}" if friend.match_label else "")
        )
        self.match_label.setText(friend.match_label)
        self.match_label.setVisible(bool(friend.match_label))
        self.stat_values["total"].setText(FriendSummary.count_text(friend.total_anime))
        self.stat_values["shared"].setText(
            FriendSummary.count_text(friend.shared_anime)
        )
        self.stat_values["both_rated"].setText(
            FriendSummary.count_text(friend.both_rated)
        )
        self.sample_stamp.setVisible(bool(is_sample))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._render_username()

    def _render_username(self) -> None:
        if not self._friend_username:
            return
        self.username_label.setText(
            self.username_label.fontMetrics().elidedText(
                self._friend_username,
                Qt.TextElideMode.ElideRight,
                max(scaled(80), self.username_label.width()),
            )
        )


class ComparisonSectionView(QFrame):
    """One prepared section, drawn as a row of the feed's own cards.

    The cards are ``RecommendationCard`` with a comparison strip, not a
    lookalike: an anime is the same object here as it is on Discover, and
    building a second card for it would mean maintaining the cover fitting,
    the line budgets and the eliding twice.
    """

    details_requested = Signal(object)
    cover_requested = Signal(str)

    def __init__(self, section, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.section = section
        self.setObjectName("comparisonSection")
        self.cards: list[RecommendationCard] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACE["sm"])

        heading = QHBoxLayout()
        heading.setSpacing(SPACE["sm"])
        title = QLabel(section.title)
        title.setObjectName("comparisonSectionTitle")
        heading.addWidget(title)
        count = len(section.entries)
        if count:
            count_label = QLabel(
                COMPARE_TEXT.section_count_one
                if count == 1
                else COMPARE_TEXT.section_count.format(count=count)
            )
            count_label.setObjectName("comparisonSectionCount")
            heading.addWidget(count_label)
        heading.addStretch(1)
        layout.addLayout(heading)

        if section.description:
            description = QLabel(section.description)
            description.setObjectName("comparisonSectionDescription")
            description.setWordWrap(True)
            layout.addWidget(description)

        if not section.entries:
            # An empty section explains itself rather than disappearing. A
            # heading that vanishes when there is nothing under it makes the
            # page a different shape for every friend, and hides the fact that
            # "you never disagree" is itself a result.
            empty = QLabel(section.empty_message or COMPARE_TEXT.empty_section_default)
            empty.setObjectName("comparisonSectionEmpty")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            return

        # A wrapping grid rather than a horizontal scroller: this page already
        # scrolls vertically, and a row that scrolls sideways inside a page
        # that scrolls down is two gestures fighting over one wheel.
        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(SPACE["lg"])
        self.grid.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        for entry in section.entries:
            card = RecommendationCard(entry.model, self, comparison=entry.scores)
            # Reviewing belongs to Discover. Here the card is evidence for a
            # comparison, and six controls on each of twelve cards would bury
            # the only thing this page is about.
            card.set_actions_visible(False)
            card.details_requested.connect(self.details_requested.emit)
            card.cover_requested.connect(self.cover_requested.emit)
            self.cards.append(card)
        layout.addLayout(self.grid)
        self._laid_out_columns = 0
        self._reflow()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()

    def _reflow(self) -> None:
        """Fit as many cards to the row as the width allows.

        Same arithmetic the feed uses - n columns need n widths and n-1 gaps -
        so a comparison row and a Discover row break at the same window sizes.
        """
        if not self.cards:
            return
        gap = self.grid.horizontalSpacing()
        minimum = scaled(CARD_WIDTH)
        available = max(self.width(), minimum)
        columns = max(1, (available + gap) // (minimum + gap))
        if columns == self._laid_out_columns:
            return
        self._laid_out_columns = columns
        while self.grid.count():
            self.grid.takeAt(0)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(
                card, index // columns, index % columns, Qt.AlignmentFlag.AlignTop
            )
        for column in range(max(columns, self.grid.columnCount())):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)


class ComparePage(QWidget):
    """The Compare surface: pick a profile, then read the comparison."""

    compare_requested = Signal(str)
    friends_requested = Signal()
    sample_requested = Signal()
    details_requested = Signal(object)
    cover_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page-compare")
        self.setAccessibleName("Compare page")
        self._loading_username = ""
        self._report: CompatibilityReport | None = None
        self._own_username: str | None = None
        self._section_views: list[ComparisonSectionView] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACE["sm"], SPACE["sm"], SPACE["sm"], SPACE["sm"])
        layout.setSpacing(SPACE["md"])
        layout.addWidget(self._build_selector())

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("compareContentStack")
        stack_layout = self.content_stack.layout()
        if stack_layout is not None:
            stack_layout.setContentsMargins(0, 0, 0, 0)
            stack_layout.setSpacing(0)

        self.state_panel = StatePanel()
        self.state_panel.retry_requested.connect(self._retry)
        self.state_panel.secondary_requested.connect(self.sample_requested.emit)
        self.state_index = self.content_stack.addWidget(self.state_panel)

        self.result_scroll = QScrollArea()
        self.result_scroll.setObjectName("compareResultScroll")
        self.result_scroll.setWidgetResizable(True)
        self.result_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.result_container = QWidget()
        self.result_container.setObjectName("compareResultContainer")
        self.result_layout = QVBoxLayout(self.result_container)
        self.result_layout.setContentsMargins(0, 0, 0, 0)
        self.result_layout.setSpacing(SPACE["xl"])
        self.header = CompatibilityHeader()
        self.result_layout.addWidget(self.header)
        self.result_layout.addStretch(1)
        self.result_scroll.setWidget(self.result_container)
        self.result_index = self.content_stack.addWidget(self.result_scroll)

        layout.addWidget(self.content_stack, 1)
        self.show_idle()

    # ---- the selector ----------------------------------------------------

    def _build_selector(self) -> QWidget:
        panel = InstrumentPanel()
        panel.setObjectName("compareSelector")
        outer = QVBoxLayout(panel)
        outer.setContentsMargins(SPACE["md"], SPACE["sm"], SPACE["md"], SPACE["sm"])
        outer.setSpacing(SPACE["xs"])

        channel = QLabel(COMPARE_TEXT.channel)
        channel.setObjectName("compareChannel")
        outer.addWidget(channel)

        hint = QLabel(COMPARE_TEXT.hint)
        hint.setObjectName("compareHint")
        hint.setWordWrap(True)
        outer.addWidget(hint)

        row = QHBoxLayout()
        row.setSpacing(SPACE["md"])

        # The friends list is an accelerator, never a gate. It is built first
        # and can be empty, private or missing without the field beside it
        # caring - which is why manual entry is not conditional on it.
        friends_block = QVBoxLayout()
        friends_block.setSpacing(SPACE["xs"])
        self.friends_label = QLabel(COMPARE_TEXT.friends_label)
        self.friends_label.setObjectName("filterControlLabel")
        friends_block.addWidget(self.friends_label)
        self.friends_picker = QComboBox()
        self.friends_picker.setObjectName("compareFriendPicker")
        self.friends_picker.setAccessibleName(COMPARE_TEXT.friends_accessible)
        self.friends_label.setBuddy(self.friends_picker)
        self.friends_picker.addItem(COMPARE_TEXT.friends_placeholder, None)
        self.friends_picker.currentIndexChanged.connect(self._on_friend_chosen)
        friends_block.addWidget(self.friends_picker)
        row.addLayout(friends_block, 1)

        username_block = QVBoxLayout()
        username_block.setSpacing(SPACE["xs"])
        self.username_label = QLabel(COMPARE_TEXT.username_label)
        self.username_label.setObjectName("filterControlLabel")
        username_block.addWidget(self.username_label)
        field_row = QHBoxLayout()
        field_row.setSpacing(SPACE["sm"])
        self.username_input = QLineEdit()
        self.username_input.setObjectName("compareUsernameInput")
        self.username_input.setPlaceholderText(COMPARE_TEXT.username_placeholder)
        self.username_input.setAccessibleName(COMPARE_TEXT.username_accessible)
        self.username_input.setMaxLength(64)
        self.username_label.setBuddy(self.username_input)
        self.username_input.returnPressed.connect(self._submit)
        field_row.addWidget(self.username_input, 1)
        self.submit_button = QPushButton(COMPARE_TEXT.submit)
        self.submit_button.setObjectName("compareSubmit")
        self.submit_button.setProperty("buttonRole", "primary")
        self.submit_button.setAccessibleName(COMPARE_TEXT.submit_accessible)
        self.submit_button.setIcon(
            themed_ui_icon("connect", role="resolvedAccentContrast")
        )
        self.submit_button.clicked.connect(self._submit)
        field_row.addWidget(self.submit_button)
        username_block.addLayout(field_row)
        self.input_message = QLabel("")
        self.input_message.setObjectName("compareInputMessage")
        self.input_message.setWordWrap(True)
        self.input_message.setVisible(False)
        username_block.addWidget(self.input_message)
        row.addLayout(username_block, 2)
        outer.addLayout(row)

        self.friends_notice = QLabel("")
        self.friends_notice.setObjectName("compareFriendsNotice")
        self.friends_notice.setWordWrap(True)
        self.friends_notice.setVisible(False)
        outer.addWidget(self.friends_notice)
        return panel

    def retint_icons(self) -> None:
        self.submit_button.setIcon(
            themed_ui_icon("connect", role="resolvedAccentContrast")
        )
        self.state_panel.retint_icons()

    # ---- input -----------------------------------------------------------

    def set_own_username(self, username: str | None) -> None:
        """Remember whose list "yours" is, so comparing with it can be refused."""
        self._own_username = (username or "").strip() or None

    def _submit(self) -> None:
        self.request(self.username_input.text())

    def _on_friend_chosen(self, _index: int) -> None:
        username = self.friends_picker.currentData()
        if username:
            self._set_input_message("")
            self.username_input.setText(str(username))
            self.request(str(username))

    def request(self, username: str) -> None:
        """Ask for one comparison, unless it is already the one in flight.

        The duplicate guard is what stops a double press, or a friend chosen
        twice from the picker, starting a second identical request while the
        first is still running.
        """
        name = str(username).strip()
        if not name:
            self._set_input_message(COMPARE_TEXT.username_required)
            self.username_input.setFocus(Qt.FocusReason.OtherFocusReason)
            return
        self._set_input_message("")
        if self._own_username and name.casefold() == self._own_username.casefold():
            self.show_state(
                COMPARE_TEXT.self_compare_title,
                COMPARE_TEXT.self_compare_message,
                icon="profile",
            )
            return
        if self._loading_username and name.casefold() == self._loading_username.casefold():
            return
        self.compare_requested.emit(name)

    def _set_input_message(self, message: str) -> None:
        self.input_message.setText(message)
        self.input_message.setVisible(bool(message))
        self.username_input.setAccessibleDescription(message)

    def _retry(self) -> None:
        target = self.username_input.text().strip() or self._loading_username
        if target:
            # A retry has to be able to reach the network again, and the guard
            # above would refuse a repeat of the name that just failed.
            self._loading_username = ""
            self.compare_requested.emit(target)

    # ---- friends ---------------------------------------------------------

    def set_friends(self, friends) -> None:
        friends = tuple(friends or ())
        self.friends_picker.blockSignals(True)
        self.friends_picker.clear()
        self.friends_picker.addItem(COMPARE_TEXT.friends_placeholder, None)
        for friend in friends:
            self.friends_picker.addItem(friend.username, friend.username)
        self.friends_picker.setCurrentIndex(0)
        self.friends_picker.blockSignals(False)
        self.friends_picker.setEnabled(bool(friends))
        self.set_friends_notice(
            "" if friends else COMPARE_TEXT.friends_empty
        )

    def set_friends_notice(self, message: str) -> None:
        """Explain an absent friends list without making it look like a fault.

        This is the non-blocking message the surface promises: the picker goes
        quiet, the sentence says why, and the field beside it is untouched.
        """
        self.friends_notice.setText(message or "")
        self.friends_notice.setVisible(bool(message))
        self.friends_picker.setEnabled(self.friends_picker.count() > 1)
        # The reason belongs to the control it is about, so a keyboard user
        # landing on the picker hears why it is empty.
        self.friends_picker.setAccessibleDescription(message or "")

    def set_friends_unavailable(self, reason: UnavailableReason) -> None:
        self.set_friends(())
        self.set_friends_notice(
            COMPARE_TEXT.friends_private
            if reason is UnavailableReason.FRIENDS_PRIVATE
            else COMPARE_TEXT.friends_unavailable
        )

    # ---- states ----------------------------------------------------------

    @property
    def report(self) -> CompatibilityReport | None:
        return self._report

    @property
    def is_loading(self) -> bool:
        return bool(self._loading_username)

    def show_idle(self) -> None:
        self._loading_username = ""
        self._set_busy(False)
        self.state_panel.show_state(
            COMPARE_TEXT.idle_title, COMPARE_TEXT.idle_message, icon="profile"
        )
        self.content_stack.setCurrentIndex(self.state_index)

    def show_loading(self, username: str) -> None:
        """Say a comparison is running, without throwing away the last one.

        When a report is already on screen the panel underneath is left alone
        and only the control reports the work. Replacing a good comparison
        with a spinner loses the thing the reader was looking at, and if the
        new request fails they are left with nothing rather than with what
        they had.
        """
        self._loading_username = str(username).strip()
        self._set_busy(True)
        if self._report is not None:
            return
        self.state_panel.show_state(
            COMPARE_TEXT.loading_title.format(username=self._loading_username),
            COMPARE_TEXT.loading_message,
            icon="sync-working",
        )
        self.content_stack.setCurrentIndex(self.state_index)

    def show_state(
        self,
        title: str,
        message: str,
        *,
        icon: str = "profile",
        tone: str = "",
        retry: bool = False,
        secondary: str = "",
    ) -> None:
        self._loading_username = ""
        self._set_busy(False)
        self.state_panel.show_state(
            title, message, icon=icon, tone=tone, retry=retry, secondary=secondary
        )
        self.content_stack.setCurrentIndex(self.state_index)

    def show_unavailable(
        self, error: CompatibilityUnavailable, *, offer_sample: bool = False
    ) -> None:
        """Draw the refusal the provider actually gave.

        Keeping the reasons apart is the whole reason the provider returns
        them. Collapsing "their list is private" and "MyAnimeList is down"
        into one apology makes the first look like a fault the reader can wait
        out and the second look like their own mistake.
        """
        title, message, icon, tone, retry = STATE_FOR_REASON.get(
            error.reason,
            (COMPARE_TEXT.api_title, COMPARE_TEXT.api_message, "sync", "error", True),
        )
        username = self._loading_username or self.username_input.text().strip()
        secondary = ""
        if error.reason is UnavailableReason.BACKEND_MISSING and offer_sample:
            secondary = COMPARE_TEXT.backend_sample_action
        # A refusal that carries its own sentence has better information than
        # the generic one for its class, so it wins.
        if error.message:
            message = error.message
        self.show_state(
            title,
            message.format(username=username) if "{username}" in message else message,
            icon=icon,
            tone=tone,
            retry=retry,
            secondary=secondary,
        )

    def show_report(self, report: CompatibilityReport) -> None:
        self._loading_username = ""
        self._set_busy(False)
        self._report = report
        self.header.set_summary(report.friend, is_sample=report.is_sample)
        self.username_input.setText(report.friend.username)

        for view in self._section_views:
            view.hide()
            self.result_layout.removeWidget(view)
            view.setParent(None)
            view.deleteLater()
        self._section_views = []

        # The trailing stretch is taken out and put back so sections always
        # sit above it rather than being appended after it.
        stretch = self.result_layout.takeAt(self.result_layout.count() - 1)
        for section in report.sections:
            view = ComparisonSectionView(section, self.result_container)
            view.details_requested.connect(self.details_requested.emit)
            view.cover_requested.connect(self.cover_requested.emit)
            self.result_layout.addWidget(view)
            self._section_views.append(view)
        self.result_layout.addItem(stretch)
        self.content_stack.setCurrentIndex(self.result_index)

    def _set_busy(self, busy: bool) -> None:
        self.submit_button.setEnabled(not busy)
        self.submit_button.setText(
            COMPARE_TEXT.submit_busy if busy else COMPARE_TEXT.submit
        )
        self.friends_picker.setEnabled(
            not busy and self.friends_picker.count() > 1
        )

    def deliver_cover(self, url: str, data: bytes) -> None:
        """Hand a downloaded image to every card waiting on it."""
        for view in self._section_views:
            for card in view.cards:
                if card.model.cover_url == url:
                    card.set_cover_data(data)

    def request_visible_covers(self) -> None:
        for view in self._section_views:
            for card in view.cards:
                card.request_cover()
