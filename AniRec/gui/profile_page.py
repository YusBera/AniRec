"""Profile: what this reader's own scores say about them.

The surface is deliberately the same machine as the rest of the application.
It borrows the panel and the readout pairs from Compare, the calibrated rails
from the score inspector, the cell bank from the match badge, the metadata
tags from the feed's cards, and the state panel - the widget itself, not a
lookalike - from Compare, so a section that fails here fails looking exactly
like a comparison that failed there.

What it is not is an analytics dashboard. There are no KPI tiles, no rings, no
gradient charts and no card with a drop shadow: a figure is a caption, a
number in the machine face, and a rail that shows the number's size. Eleven
sections of that read as one panel with eleven legends on it, which is what a
workstation looks like, rather than as eleven widgets from eleven products.

It also works nothing out. Every figure arrives prepared from a
``TasteProfileProvider``; see ``taste_profile.py`` for the boundary and for
the one narrow exception. Sections fail independently: each is wrapped in a
``ProfileSection`` that can be empty, loading or broken on its own, because
"we could not read your genres" is no reason to hide your rating histogram.
"""

from __future__ import annotations

from dataclasses import dataclass

import math

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .compare_page import StatePanel
from .compatibility import UnavailableReason
from .cover_art import rounded_cover
from .design_tokens import RADIUS, SPACE
from .discover_filters import FilterKind
from .instrument_widgets import InstrumentPanel, keep_crisp
from .metadata_tags import MetadataTag
from .profile_widgets import (
    BarRail,
    CellBank,
    PolarityScale,
    ReadoutPair,
    SkeletonBlock,
    TimelinePlot,
    motion_enabled,
)
from .resources import cover_placeholder_pixmap, ui_icon_pixmap
from .scaling import scaled
from .taste_profile import (
    DASH,
    TasteProfile,
    TasteProfileUnavailable,
    TitleVerdict,
    archetype_for,
    count_text,
)
from .texts import PROFILE_TEXT


# Which state panel a refusal turns into. The same table Compare keeps, for
# the same reason: adding a reason means adding a row, and the mapping can be
# read at a glance against the reasons a provider may return.
STATE_FOR_REASON = {
    UnavailableReason.BACKEND_MISSING: (
        PROFILE_TEXT.backend_title,
        PROFILE_TEXT.backend_message,
        "details-inspector",
        "",
        False,
    ),
    UnavailableReason.NOT_CONNECTED: (
        PROFILE_TEXT.not_connected_title,
        PROFILE_TEXT.not_connected_message,
        "profile",
        "",
        False,
    ),
    UnavailableReason.PRIVATE_LIST: (
        PROFILE_TEXT.private_title,
        PROFILE_TEXT.private_message,
        "hide",
        "",
        False,
    ),
    UnavailableReason.NETWORK: (
        PROFILE_TEXT.network_title,
        PROFILE_TEXT.network_message,
        "connect",
        "error",
        True,
    ),
    UnavailableReason.API_UNAVAILABLE: (
        PROFILE_TEXT.api_title,
        PROFILE_TEXT.api_message,
        "sync",
        "error",
        True,
    ),
    UnavailableReason.USER_NOT_FOUND: (
        PROFILE_TEXT.empty_title,
        PROFILE_TEXT.empty_message,
        "profile",
        "",
        False,
    ),
    UnavailableReason.FRIENDS_PRIVATE: (
        PROFILE_TEXT.private_title,
        PROFILE_TEXT.private_message,
        "hide",
        "",
        False,
    ),
}

# The avatar plate, and the poster on a verdict row. Both square-cornered and
# both small: this page is about numbers, and artwork is here to identify a
# title, not to be looked at.
AVATAR_SIZE = 64
VERDICT_COVER_WIDTH = 40
VERDICT_COVER_HEIGHT = 60

# The narrowest a fingerprint module or a hot-takes column may be drawn before
# the grid drops to fewer columns.
FINGERPRINT_MIN_WIDTH = 216
COLUMN_MIN_WIDTH = 320

# CHANGE [INSTRUMENT-GRID]: wide enough that a ten-row histogram still reads,
# narrow enough that a 1600px window fits three across and a laptop fits two.
# The old full-width sections gave every chart the one proportion that suits
# none of them.
INSTRUMENT_MIN_WIDTH = 420

# A fact card holds a legend, a figure and a sentence of about eighty
# characters. Narrower than an instrument because it carries no chart.
FACT_MIN_WIDTH = 320


class ReflowGrid(QWidget):
    """Widgets laid into as many columns of at least ``minimum`` width as fit.

    Three sections of this page need the same behaviour, and it is the same
    arithmetic the feed and Compare already use for their card rows - n
    columns need n widths and n-1 gaps - so a fingerprint module, a hot-takes
    column and a Discover card all break at window sizes that agree.
    """

    def __init__(
        self,
        minimum: int,
        parent: QWidget | None = None,
        *,
        spacing: str = "sm",
        uniform_height: bool = False,
        slots: int = 0,
        avoid_orphans: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("profileReflow")
        self._minimum = minimum
        self._uniform_height = uniform_height
        # CHANGE [KEEP-THE-SLOT]: how many columns this row is *for*, when the
        # caller knows. The column count is otherwise capped at the number of
        # widgets present, so a row that expects three and receives one gives
        # that one a full-page-width column - which is how a single receipt
        # ended up as a 1600px box with a title in the left corner. With a
        # slot count the lone widget keeps a third of the row and the rest
        # stays empty, which is a gap rather than a stretched object.
        self._slots = int(slots)
        # CHANGE [USE-THE-WIDTH]: whether a lone widget on the last row is
        # worth dropping a whole column for. It is, for a bank of five peer
        # readings that reads as one strip. It is not for the ten collapsed
        # instrument panels: ten in three columns leaves one orphan, and
        # avoiding it cost a third of the page's width on every row above.
        self._avoid_orphans = bool(avoid_orphans)
        self._widgets: list[QWidget] = []
        self._columns = 0
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setSpacing(scaled(SPACE[spacing]))

    @property
    def widgets(self) -> tuple[QWidget, ...]:
        return tuple(self._widgets)

    def set_widgets(self, widgets) -> None:
        for widget in self._widgets:
            widget.setParent(None)
            widget.deleteLater()
        self._widgets = list(widgets)
        for widget in self._widgets:
            widget.setParent(self)
            widget.show()
        self._columns = 0
        self._relayout()

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._relayout()

    def _relayout(self) -> None:
        if not self._widgets:
            return
        minimum = scaled(self._minimum)
        gap = self.grid.horizontalSpacing()
        available = max(self.width(), minimum)
        fits = max(1, (available + gap) // (minimum + gap))
        wanted = self._slots or len(self._widgets)
        columns = max(1, min(wanted, fits))
        # Never leave a single module alone on the last row. Five readings in
        # four columns is a strip of four and an orphan, which reads as a
        # mistake; three and two reads as a deliberate arrangement, and the
        # modules only get wider for it.
        if (
            self._avoid_orphans
            and not self._slots
            and columns > 2
            and len(self._widgets) % columns == 1
        ):
            columns -= 1
        if columns != self._columns:
            self._columns = columns
            while self.grid.count():
                self.grid.takeAt(0)
            for index, widget in enumerate(self._widgets):
                self.grid.addWidget(
                    widget, index // columns, index % columns, Qt.AlignmentFlag.AlignTop
                )
            for column in range(max(columns, self.grid.columnCount())):
                self.grid.setColumnStretch(column, 1 if column < columns else 0)
        self._equalize_widget_heights(columns, available, gap)

    def _equalize_widget_heights(
        self, columns: int, available: int, gap: int
    ) -> None:
        """Give compact statistic modules one shared frame height.

        Word-wrapped descriptions naturally produce different size hints.
        Fingerprint modules are one bank of peer readouts, though, so their
        frames should still terminate on the same baseline at every reflow.
        Other users of ``ReflowGrid`` remain content-sized.
        """
        if not self._uniform_height:
            return
        item_width = max(
            scaled(self._minimum),
            (available - max(0, columns - 1) * gap) // columns,
        )
        heights = []
        for widget in self._widgets:
            widget.setMinimumHeight(0)
            layout = widget.layout()
            if layout is not None and layout.hasHeightForWidth():
                heights.append(layout.totalHeightForWidth(item_width))
            else:
                heights.append(widget.sizeHint().height())
        if heights:
            shared_height = max(heights)
            for widget in self._widgets:
                widget.setMinimumHeight(shared_height)


class ProfileSection(QFrame):
    """One legend, one explanation, and one body that can fail on its own.

    The body is a stack of three: the content, a skeleton the same height as
    the content, and an error panel with a retry. A section that cannot be
    read says so in its own frame and leaves the ten around it standing,
    which is the difference between a page that degrades and a page that
    disappears.
    """

    retry_requested = Signal(str)

    def __init__(
        self,
        section_id: str,
        title: str,
        description: str = "",
        parent: QWidget | None = None,
        *,
        skeleton_rows: int = 3,
    ) -> None:
        super().__init__(parent)
        self.section_id = section_id
        self.setObjectName("profileSection")
        self.setAccessibleName(title.title())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["sm"]))

        heading = QHBoxLayout()
        heading.setSpacing(scaled(SPACE["sm"]))
        # CHANGE [INSTRUMENT-GRID]: the legend is a control now. Eleven
        # sections at full page width put every chart in a short, very wide
        # box - the worst possible shape for a bar chart - and made the page
        # a scroll rather than a panel. They fold, and they sit two or three
        # to a row, so each one is a squarer widget with a bigger graph in it.
        self.title_label = QPushButton(title)
        self.title_label.setObjectName("profileSectionTitle")
        self.title_label.setCheckable(True)
        self.title_label.setChecked(True)
        self.title_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.title_label.toggled.connect(self.set_expanded)
        heading.addWidget(self.title_label)
        self.badge_label = QLabel("")
        self.badge_label.setObjectName("profileSectionBadge")
        self.badge_label.setVisible(False)
        heading.addWidget(self.badge_label)
        heading.addStretch(1)
        layout.addLayout(heading)

        if description:
            self.description_label = QLabel(description)
            self.description_label.setObjectName("profileSectionDescription")
            self.description_label.setWordWrap(True)
            layout.addWidget(self.description_label)

        self.stack = QStackedWidget()
        self.stack.setObjectName("profileSectionStack")
        stack_layout = self.stack.layout()
        if stack_layout is not None:
            stack_layout.setContentsMargins(0, 0, 0, 0)

        self.body = QWidget()
        self.body.setObjectName("profileSectionBody")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(scaled(SPACE["md"]))
        self._body_index = self.stack.addWidget(self.body)

        self.skeleton = SkeletonBlock(skeleton_rows)
        self._skeleton_index = self.stack.addWidget(self.skeleton)

        self.error_panel = self._build_error(title)
        self._error_index = self.stack.addWidget(self.error_panel)

        # An absence and a fault must not look the same, which is the rule the
        # Compare state panel already follows: "we have not measured this yet"
        # is the dashed note the feed uses for an empty section, not a red
        # frame with a retry that would ask the reader to fix nothing.
        self.empty_panel = QLabel(PROFILE_TEXT.section_empty)
        self.empty_panel.setObjectName("profileSectionEmpty")
        self.empty_panel.setWordWrap(True)
        self._empty_index = self.stack.addWidget(self.empty_panel)

        layout.addWidget(self.stack)
        self.show_loading()

    def set_expanded(self, expanded: bool) -> None:
        """Fold the body away, leaving the legend as the handle."""
        expanded = bool(expanded)
        if self.title_label.isChecked() != expanded:
            self.title_label.setChecked(expanded)
        self.stack.setVisible(expanded)
        description = getattr(self, "description_label", None)
        if description is not None:
            description.setVisible(expanded)
        self.title_label.setAccessibleDescription(
            "Expanded" if expanded else "Collapsed"
        )

    @property
    def is_expanded(self) -> bool:
        return self.stack.isVisibleTo(self)

    def _build_error(self, title: str) -> QWidget:
        panel = QFrame()
        panel.setObjectName("profileSectionError")
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
        )
        layout.setSpacing(scaled(SPACE["md"]))
        message = QLabel(PROFILE_TEXT.section_error.format(section=title))
        message.setObjectName("profileSectionErrorText")
        message.setWordWrap(True)
        layout.addWidget(message, 1)
        retry = QPushButton(PROFILE_TEXT.section_retry)
        retry.setObjectName("profileSectionRetry")
        retry.setProperty("buttonRole", "secondary")
        retry.setCursor(Qt.CursorShape.PointingHandCursor)
        retry.setAccessibleName(f"Retry loading {title.title()}")
        retry.clicked.connect(lambda: self.retry_requested.emit(self.section_id))
        layout.addWidget(retry)
        self.error_message = message
        self.retry_button = retry
        return panel

    def add_body(self, widget: QWidget) -> None:
        self.body_layout.addWidget(widget)

    def set_badge(self, text: str) -> None:
        self.badge_label.setText(text)
        self.badge_label.setVisible(bool(text))

    def show_content(self) -> None:
        self.stack.setCurrentIndex(self._body_index)

    def show_loading(self) -> None:
        self.stack.setCurrentIndex(self._skeleton_index)

    def show_error(self, message: str = "") -> None:
        if message:
            self.error_message.setText(message)
        self.stack.setCurrentIndex(self._error_index)

    def show_empty(self, message: str = "") -> None:
        self.empty_panel.setText(message or PROFILE_TEXT.section_empty)
        self.stack.setCurrentIndex(self._empty_index)


class AvatarPlate(QLabel):
    """The reader's MAL avatar, or their initials on an empty plate.

    Square, hairlined, and the same size in both states, so a profile with no
    avatar is not a differently-shaped header. The fallback is the display
    face on the sunken surface rather than a coloured circle: a generated
    pastel disc is the one avatar convention that would look imported.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileAvatar")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedSize(scaled(AVATAR_SIZE), scaled(AVATAR_SIZE))
        keep_crisp(self)
        self._initials = "??"

    def set_identity(self, initials: str, username: str) -> None:
        self._initials = initials or "??"
        self.setPixmap(QPixmap())
        self.setText(self._initials)
        self.setAccessibleName(
            PROFILE_TEXT.avatar_fallback_accessible.format(username=username or DASH)
        )

    def set_avatar_data(self, data: bytes, username: str = "") -> None:
        """Show a fetched avatar. Unused until a provider supplies a URL."""
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            return
        size = scaled(AVATAR_SIZE)
        self.setText("")
        self.setPixmap(rounded_cover(pixmap, size, size, RADIUS["sm"]))
        self.setAccessibleName(
            PROFILE_TEXT.avatar_accessible.format(username=username or DASH)
        )

    def apply_scale(self) -> None:
        self.setFixedSize(scaled(AVATAR_SIZE), scaled(AVATAR_SIZE))


class ProfileHeader(InstrumentPanel):
    """Who this is, and the four counts that describe the shape of their list.

    Identity on the left, counts on the right as readout pairs - the same
    treatment Compare gives the counts behind a match score, because these are
    the same kind of fact: supporting figures for the page, not four metrics
    that happen to be near each other.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileHeader")
        self._username = ""

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["xl"]), scaled(SPACE["lg"]),
            scaled(SPACE["xl"]), scaled(SPACE["lg"]),
        )
        layout.setSpacing(scaled(SPACE["lg"]))

        self.avatar = AvatarPlate()
        layout.addWidget(self.avatar, 0, Qt.AlignmentFlag.AlignTop)

        identity = QVBoxLayout()
        identity.setSpacing(scaled(SPACE["hair"]))
        legend_row = QHBoxLayout()
        legend_row.setSpacing(scaled(SPACE["sm"]))
        legend = QLabel(PROFILE_TEXT.identity_legend)
        legend.setObjectName("profileLegend")
        legend_row.addWidget(legend)
        self.sample_stamp = QLabel(PROFILE_TEXT.sample_stamp)
        self.sample_stamp.setObjectName("profileSampleStamp")
        self.sample_stamp.setToolTip(PROFILE_TEXT.sample_stamp_tooltip)
        self.sample_stamp.setVisible(False)
        legend_row.addWidget(self.sample_stamp)
        legend_row.addStretch(1)
        identity.addLayout(legend_row)

        self.username_label = QLabel(DASH)
        self.username_label.setObjectName("profileUsername")
        # A MAL username runs to 64 characters and this is the largest type on
        # the panel, so it elides rather than pushing the counts off the edge.
        self.username_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        identity.addWidget(self.username_label)
        self.member_label = QLabel(PROFILE_TEXT.member_since_unknown)
        self.member_label.setObjectName("profileMemberSince")
        identity.addWidget(self.member_label)
        identity.addStretch(1)
        layout.addLayout(identity, 1)

        stats = QGridLayout()
        stats.setHorizontalSpacing(scaled(SPACE["xl"]))
        stats.setVerticalSpacing(0)
        self.stats: dict[str, ReadoutPair] = {}
        for column, (key, caption) in enumerate(
            (
                ("completed", PROFILE_TEXT.stat_completed),
                ("episodes", PROFILE_TEXT.stat_episodes),
                ("days", PROFILE_TEXT.stat_days),
                ("mean", PROFILE_TEXT.stat_mean),
            )
        ):
            readout = ReadoutPair(caption, DASH, size="lg")
            stats.addWidget(readout, 0, column)
            self.stats[key] = readout
        layout.addLayout(stats)

    def set_profile(self, profile: TasteProfile) -> None:
        identity = profile.identity
        self._username = identity.username
        self._render_username()
        self.username_label.setToolTip(identity.username)
        self.username_label.setAccessibleName(f"Profile: {identity.username or DASH}")
        self.member_label.setText(
            PROFILE_TEXT.member_since.format(year=identity.member_since)
            if identity.member_since
            else PROFILE_TEXT.member_since_unknown
        )
        self.avatar.set_identity(identity.initials, identity.username)
        self.stats["completed"].set_value(count_text(identity.completed))
        self.stats["episodes"].set_value(count_text(identity.episodes))
        self.stats["days"].set_value(identity.days_text)
        self.stats["mean"].set_value(identity.mean_text, tone="you")
        self.sample_stamp.setVisible(bool(profile.is_sample))

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._render_username()

    def _render_username(self) -> None:
        if not self._username:
            return
        self.username_label.setText(
            self.username_label.fontMetrics().elidedText(
                self._username,
                Qt.TextElideMode.ElideRight,
                max(scaled(80), self.username_label.width()),
            )
        )


class VerdictHero(InstrumentPanel):
    """The page's opening statement: what kind of reader this is.

    CHANGE [READOUT-LEAD]: the surface used to begin with five equally
    weighted readings and leave the reader to work out which one was about
    them. Five numbers of equal size say "here is a dashboard"; one sentence
    says "here is you". The readings are not gone - they are the quiet line
    underneath, and the full instrument is further down the page.

    The figure line is deliberately the muted role rather than the accent.
    Amber on this page means "yours", and if the headline and its supporting
    arithmetic both shout, neither is the headline.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileVerdict")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["xl"]), scaled(SPACE["lg"]),
            scaled(SPACE["xl"]), scaled(SPACE["lg"]),
        )
        layout.setSpacing(scaled(SPACE["xs"]))

        self.legend_label = QLabel(PROFILE_TEXT.verdict_legend)
        self.legend_label.setObjectName("profileLegend")
        layout.addWidget(self.legend_label)

        self.name_label = QLabel("")
        self.name_label.setObjectName("profileVerdictName")
        self.name_label.setWordWrap(True)
        layout.addWidget(self.name_label)

        self.sentence_label = QLabel("")
        self.sentence_label.setObjectName("profileVerdictSentence")
        self.sentence_label.setWordWrap(True)
        layout.addWidget(self.sentence_label)

        # CHANGE [ONE-BOARD]: the figures behind the claim are tiles on the
        # board below, not a row inside this panel. Spread across a full-width
        # hero they were three numbers with 400px between them; on the board
        # they sit beside every other derived fact, which is what they are.
        # The hero states the claim and stops.

    def set_archetype(self, archetype) -> None:
        """Draw the reading, or say plainly that there is not one."""
        if archetype:
            name, sentence = archetype.name, archetype.sentence
        else:
            name = PROFILE_TEXT.verdict_plain_name
            sentence = PROFILE_TEXT.verdict_plain_sentence
            readings = ()
        self.name_label.setText(f"{PROFILE_TEXT.verdict_prefix} {name}.")
        self.sentence_label.setText(sentence)
        self.setAccessibleName(f"{self.name_label.text()} {sentence}")


def _fact_mark_colour(tone: str) -> str:
    """Tint the mark with the same meaning its figure carries."""
    from PySide6.QtWidgets import QApplication

    role, fallback = (
        ("resolvedDanger", "#D98363")
        if tone == "against"
        else ("resolvedAccent", "#D9A441")
    )
    application = QApplication.instance()
    value = application.property(role) if application is not None else None
    return str(value or fallback)


@dataclass(frozen=True)
class UnlistedFact:
    """One derived fact, as a card wants it: a mark, a figure, a sentence."""

    icon: str
    legend: str
    value: str
    caption: str
    tone: str = "you"


# Which mark stands for which season. Drawn in the same plotted, butt-capped
# language as the rest of the interface set rather than as illustration: a
# soft autumn leaf would be the first rounded thing in the application.
# The fingerprint readings and the named-title receipts, as marks. Every one
# of these facts is derived by comparing this reader against everyone else,
# which is why they belong on the same board under the same heading.
_READING_ICONS = {
    "community-sync": "fact-sync",
    "rating-bias": "fact-bias",
    "contrarian": "fact-contrarian",
    "completion": "fact-completion",
    "mainstream": "fact-mainstream",
}

_SEASON_ICONS = {
    "winter": "fact-season-winter",
    "spring": "fact-season-spring",
    "summer": "fact-season-summer",
    "fall": "fact-season-fall",
    "autumn": "fact-season-fall",
}


class UnlistedFactCard(InstrumentPanel):
    """One fact, built to be looked at rather than read past.

    CHANGE [FUN-FACTS]: these were seven sentences with a rule down the left,
    stacked in a column. Everything interesting about them - a studio you
    clash with, the years you keep coming back to - was buried mid-sentence
    at body size, and the panel read as a paragraph. The figure is the thing
    somebody screenshots and sends to a group chat, so it is set large and
    the sentence explains it underneath.
    """

    def __init__(self, fact: UnlistedFact, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.fact = fact
        self.setObjectName("profileFactCard")
        self.setProperty("tone", fact.tone)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["lg"]), scaled(SPACE["md"]),
            scaled(SPACE["lg"]), scaled(SPACE["md"]),
        )
        layout.setSpacing(scaled(SPACE["xs"]))

        head = QHBoxLayout()
        head.setSpacing(scaled(SPACE["sm"]))
        self.mark = QLabel()
        self.mark.setObjectName("profileFactMark")
        self.mark.setFixedSize(scaled(22), scaled(22))
        self.mark.setPixmap(
            ui_icon_pixmap(fact.icon, _fact_mark_colour(fact.tone), scaled(22))
        )
        head.addWidget(self.mark, 0, Qt.AlignmentFlag.AlignVCenter)
        self.legend_label = QLabel(fact.legend)
        self.legend_label.setObjectName("profileFactLegend")
        head.addWidget(self.legend_label, 0, Qt.AlignmentFlag.AlignVCenter)
        head.addStretch(1)
        layout.addLayout(head)

        self.value_label = QLabel(fact.value)
        self.value_label.setObjectName("profileFactValue")
        self.value_label.setProperty("tone", fact.tone)
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label)

        self.caption_label = QLabel(fact.caption)
        self.caption_label.setObjectName("profileFactCaption")
        self.caption_label.setWordWrap(True)
        layout.addWidget(self.caption_label)
        layout.addStretch(1)

        self.setAccessibleName(f"{fact.legend.title()}: {fact.value}. {fact.caption}")


class UnlistedFacts(ReflowGrid):
    """The derived facts as a board of cards, named for being derived.

    Every one of these comes out of comparing this reader's scores against
    everyone else's, which is exactly why none of it appears on a MyAnimeList
    profile. The heading says so; the cards are what make somebody want to
    show one to a friend.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        # Uniform height: captions run one to three lines, and aligned to the
        # top that leaves every row with a ragged underside. One frame height
        # per row is what makes a board read as a board.
        super().__init__(
            FACT_MIN_WIDTH,
            parent,
            spacing="lg",
            avoid_orphans=False,
            uniform_height=True,
        )
        self.setObjectName("profileUnlisted")
        self._facts: tuple[UnlistedFact, ...] = ()

    def set_profile(self, profile) -> None:
        self._facts = board_facts(profile)
        self.set_widgets([UnlistedFactCard(fact) for fact in self._facts])

    @property
    def facts(self) -> tuple[UnlistedFact, ...]:
        return self._facts

    @property
    def sentences(self) -> tuple[str, ...]:
        return tuple(f"{fact.value} {fact.caption}".strip() for fact in self._facts)


def reading_facts(profile) -> tuple[UnlistedFact, ...]:
    """The fingerprint readings, as tiles.

    These are not on a MyAnimeList profile either: "you disagree with the
    consensus on a third of your list" is a comparison against everybody
    else, which is the same claim every other tile on this board makes.
    """
    facts = []
    for reading in profile.fingerprint:
        facts.append(
            UnlistedFact(
                # CHANGE [HONEST-FALLBACK]: an unknown reading used to be
                # handed the community-sync mark, which asserts a specific
                # meaning the tile may not have. fact-unknown is a plate with
                # a dash in it - the same "no value" mark the rest of the
                # interface uses - and claims nothing.
                _READING_ICONS.get(reading.reading_id, "fact-unknown"),
                reading.caption,
                reading.value_text,
                reading.detail or reading.label,
                tone="you" if reading.tone == "you" else "",
            )
        )
    return tuple(facts)


def receipt_facts(profile) -> tuple[UnlistedFact, ...]:
    """The named titles, as tiles.

    A title is the strongest evidence this page has - "you rated Stone Ocean
    a 1 and everyone else 8.05" is the fact people repeat - so it sits on the
    board with the rest rather than in a row of its own that goes half empty
    whenever a profile is missing one.
    """
    facts = []
    biggest = getattr(profile.hype_killers, "biggest", None)
    if biggest is not None and biggest.title:
        facts.append(
            UnlistedFact(
                "fact-hype",
                PROFILE_TEXT.receipt_hype,
                biggest.title,
                PROFILE_TEXT.receipt_versus.format(
                    you=biggest.your_score_text,
                    community=biggest.community_score_text,
                ),
                tone="against",
            )
        )
    deepest = getattr(profile.hidden_gems, "deepest", None)
    if deepest is not None and deepest.title:
        facts.append(
            UnlistedFact(
                "fact-gem",
                PROFILE_TEXT.receipt_gem,
                deepest.title,
                PROFILE_TEXT.receipt_versus.format(
                    you=deepest.your_score_text,
                    community=deepest.community_score_text,
                ),
            )
        )
    rewatch = getattr(profile.habits, "most_rewatched", None)
    if rewatch is not None and rewatch.title:
        facts.append(
            UnlistedFact(
                "fact-rewatch",
                PROFILE_TEXT.receipt_rewatch,
                rewatch.title,
                PROFILE_TEXT.receipt_rewatch_detail.format(
                    watches=rewatch.watches_text
                ),
            )
        )
    return tuple(facts)


def board_facts(profile) -> tuple[UnlistedFact, ...]:
    """Everything the board shows, in one list.

    CHANGE [ONE-BOARD]: this used to be three separate grids stacked down the
    page - the reading's figures, the named titles, the derived facts - each
    with its own item count and therefore its own leftover space. A reader
    with three fingerprint readings and one receipt got three figures spread
    across a full-width row with 400px gaps, then a single 540px receipt
    beside 1100px of nothing, then six cards in a four-column grid. Three
    grids, three sets of holes.
    
    They are one kind of thing - a fact derived by comparing this reader
    against everyone else - and they share one shape: a legend, a figure, and
    a sentence. As one grid there is a single partial row, at the end, which
    is what a board is supposed to look like.

    Order matters: the readings are the general shape of the reader, the
    named titles are the proof, and the studio and era facts are the
    curiosities. Broad to specific.
    """
    return reading_facts(profile) + receipt_facts(profile) + unlisted_facts(profile)


def unlisted_facts(profile) -> tuple[UnlistedFact, ...]:
    """Compose the derived-only facts, skipping whatever is not there.

    A free function so the wording and the selection can be tested without a
    widget, and so a provider that answers with half a profile produces a
    shorter board rather than a row of "N/A" cards.
    """
    facts: list[UnlistedFact] = []

    nemesis = getattr(profile.studios, "nemesis", None)
    if nemesis is not None and nemesis.name:
        facts.append(
            UnlistedFact(
                "fact-nemesis",
                PROFILE_TEXT.unlisted_nemesis_legend,
                nemesis.name,
                PROFILE_TEXT.unlisted_nemesis_caption.format(
                    watched=nemesis.watched_text, average=nemesis.average_text
                ),
                tone="against",
            )
        )
    trusted = getattr(profile.studios, "most_trusted", None)
    if trusted is not None and trusted.name:
        facts.append(
            UnlistedFact(
                "fact-trusted",
                PROFILE_TEXT.unlisted_trusted_legend,
                trusted.name,
                PROFILE_TEXT.unlisted_trusted_caption.format(
                    average=trusted.average_text
                ),
            )
        )
    divisive = getattr(profile.genres, "divisive", None)
    if divisive is not None and divisive.name:
        facts.append(
            UnlistedFact(
                "fact-divisive",
                PROFILE_TEXT.unlisted_divisive_legend,
                divisive.name,
                PROFILE_TEXT.unlisted_divisive_caption,
            )
        )
    golden = getattr(profile.eras, "golden", None)
    if golden is not None and golden.label:
        facts.append(
            UnlistedFact(
                "fact-era",
                PROFILE_TEXT.unlisted_golden_legend,
                golden.label,
                PROFILE_TEXT.unlisted_golden_caption.format(
                    average=golden.average_text
                ),
            )
        )
    season = str(getattr(profile.eras, "season_of_choice", "") or "")
    if season:
        facts.append(
            UnlistedFact(
                # A season nobody recognises is not a calendar either.
                _SEASON_ICONS.get(season.casefold(), "fact-unknown"),
                PROFILE_TEXT.unlisted_season_legend,
                season.title(),
                PROFILE_TEXT.unlisted_season_caption.format(season=season.lower()),
            )
        )
    gems = getattr(profile.hidden_gems, "rate_text", "")
    if gems and gems != DASH:
        facts.append(
            UnlistedFact(
                "fact-gem",
                PROFILE_TEXT.unlisted_gems_legend,
                gems,
                PROFILE_TEXT.unlisted_gems_caption,
            )
        )
    hype = getattr(profile.hype_killers, "count", None)
    if hype:
        facts.append(
            UnlistedFact(
                "fact-hype",
                PROFILE_TEXT.unlisted_hype_legend,
                str(hype),
                PROFILE_TEXT.unlisted_hype_caption,
                tone="against",
            )
        )
    return tuple(facts)


def unlisted_sentences(profile) -> tuple[str, ...]:
    """The same facts as plain sentences, for anything that wants prose."""
    return tuple(
        f"{fact.value} {fact.caption}".strip() for fact in unlisted_facts(profile)
    )


class FingerprintModule(QFrame):
    """One statistic in the fingerprint: caption, figure, verdict, instrument.

    Four rows in a fixed order, so five of these side by side scan as one
    strip of readouts rather than as five tiles. Which instrument sits on the
    bottom row is the reading's own business - a proportion gets cells, a
    position between two extremes gets a two-ended scale - and the row is
    always the same height either way.
    """

    def __init__(self, reading, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reading = reading
        self.setObjectName("profileFingerprintModule")
        self.setProperty("tone", reading.tone or "neutral")
        self.setAccessibleName(reading.accessible_text)
        self.setToolTip(reading.detail or reading.caption)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
        )
        layout.setSpacing(scaled(SPACE["hair"]))

        caption = QLabel(reading.caption)
        caption.setObjectName("profileFingerprintCaption")
        layout.addWidget(caption)

        value = QLabel(reading.value_text)
        value.setObjectName("profileFingerprintValue")
        layout.addWidget(value)

        label = QLabel(reading.label or "")
        label.setObjectName("profileFingerprintLabel")
        # CHANGE [BUG1]: added to the layout before its visibility is set.
        # setVisible(True) on a label the layout has not adopted yet is
        # setVisible on a widget with no parent, and a parentless QWidget is
        # a top-level window - so opening Profile flashed one empty frame per
        # fingerprint reading. Same defect as the feed's cards and rows, in
        # the one constructor the original sweep did not reach.
        layout.addWidget(label)
        label.setVisible(bool(reading.label))

        layout.addSpacing(scaled(SPACE["xs"]))
        self.instrument = self._build_instrument(reading)
        layout.addWidget(self.instrument)

        if reading.detail:
            detail = QLabel(reading.detail)
            detail.setObjectName("profileFingerprintDetail")
            detail.setWordWrap(True)
            layout.addWidget(detail)
        layout.addStretch(1)

    def _build_instrument(self, reading) -> QWidget:
        if reading.readout == "scale":
            holder = QWidget()
            holder.setObjectName("profileBlock")
            column = QVBoxLayout(holder)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(scaled(SPACE["hair"]))
            scale = PolarityScale()
            scale.set_position(
                reading.position if reading.position is not None else 0.5
            )
            scale.setAccessibleName(reading.accessible_text)
            column.addWidget(scale)
            ends = QHBoxLayout()
            ends.setSpacing(scaled(SPACE["xs"]))
            low = QLabel(reading.scale_low)
            low.setObjectName("profileScaleEnd")
            high = QLabel(reading.scale_high)
            high.setObjectName("profileScaleEnd")
            high.setAlignment(Qt.AlignmentFlag.AlignRight)
            ends.addWidget(low)
            ends.addStretch(1)
            ends.addWidget(high)
            column.addLayout(ends)
            self._animated = scale
            return holder
        bank = CellBank(tone="you" if reading.tone == "you" else "community")
        bank.set_fraction(reading.position or 0.0)
        bank.setAccessibleName(reading.accessible_text)
        self._animated = bank
        return bank

    def animate(self) -> None:
        animated = getattr(self, "_animated", None)
        if animated is not None:
            animated.animate()


class TasteFingerprint(ReflowGrid):
    """The fingerprint modules, in as many columns as the width allows."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(FINGERPRINT_MIN_WIDTH, parent, uniform_height=True)
        self.setObjectName("profileFingerprint")

    def set_readings(self, readings) -> None:
        self.set_widgets([FingerprintModule(reading) for reading in readings])

    def animate(self) -> None:
        for module in self.widgets:
            module.animate()


class RatingDistributionChart(QWidget):
    """The 1-10 histogram, one ruled rail per score, with its counts beside it.

    Rows rather than columns: ten labelled bars reading downward fits the
    page's one-column rhythm, keeps every count on the same baseline as its
    score, and never squeezes a two-digit label into a bar's width the way a
    vertical histogram does at narrow widths.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileHistogram")
        self.rails: list[BarRail] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["md"]))

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(scaled(SPACE["md"]))
        self.grid.setVerticalSpacing(scaled(SPACE["xs"]))
        self.grid.setColumnStretch(1, 1)
        layout.addLayout(self.grid)

        self.summary = QHBoxLayout()
        self.summary.setSpacing(scaled(SPACE["xl"]))
        layout.addLayout(self.summary)
        self.summary_readouts: dict[str, ReadoutPair] = {}
        for key, caption in (
            ("mean", PROFILE_TEXT.distribution_mean),
            ("median", PROFILE_TEXT.distribution_median),
            ("mode", PROFILE_TEXT.distribution_mode),
            ("usage", PROFILE_TEXT.distribution_scale_usage),
            ("total", PROFILE_TEXT.distribution_total),
        ):
            readout = ReadoutPair(caption, DASH)
            self.summary_readouts[key] = readout
            self.summary.addWidget(readout)
        self.summary.addStretch(1)

    def set_distribution(self, distribution) -> None:
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.rails = []
        peak = distribution.peak or 1
        for row, bucket in enumerate(distribution.ordered):
            score = QLabel(f"{bucket.score:2d}")
            score.setObjectName("profileHistogramScore")
            score.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            rail = BarRail(tone="you")
            rail.set_fraction(bucket.count / peak)
            rail.setAccessibleName(f"Score {bucket.score}: {bucket.count:,} titles")
            count = QLabel(f"{bucket.count:,}")
            count.setObjectName("profileHistogramCount")
            count.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.grid.addWidget(score, row, 0)
            self.grid.addWidget(rail, row, 1)
            self.grid.addWidget(count, row, 2)
            self.rails.append(rail)

        self.summary_readouts["mean"].set_value(distribution.mean_text, tone="you")
        self.summary_readouts["median"].set_value(distribution.median_text)
        self.summary_readouts["mode"].set_value(distribution.mode_text)
        self.summary_readouts["usage"].set_value(distribution.scale_usage_text)
        self.summary_readouts["total"].set_value(f"{distribution.total:,}")

    def animate(self) -> None:
        for rail in self.rails:
            rail.animate()


class VerdictRow(QFrame):
    """One anime, your score, the community's, and the gap between them.

    Built from the row the feed already uses rather than from a new card: a
    small poster on the left when there is one, the title, then the figures in
    the machine face. The direction of the gap is a word as well as a colour
    and a sign, because a page that says "you liked this more" only in amber
    says nothing at all to a reader who cannot see amber.
    """

    cover_requested = Signal(str)

    def __init__(
        self,
        verdict: TitleVerdict,
        parent: QWidget | None = None,
        *,
        show_cover: bool = False,
        rank_field: str = "",
        # CHANGE [RECEIPTS]: a rewatch note is a title and a count, with no
        # two opinions to set against each other. Drawn through the standard
        # row it produced "YOU N/A  MAL N/A" - two empty columns reserved for
        # a comparison that does not exist here. The caller says what figure
        # this row is actually about.
        figures: tuple[tuple[str, str, str], ...] | None = None,
    ) -> None:
        super().__init__(parent)
        self.verdict = verdict
        self.setObjectName("profileVerdictRow")
        self.setProperty("direction", verdict.direction)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["sm"]), scaled(SPACE["xs"]),
            scaled(SPACE["sm"]), scaled(SPACE["xs"]),
        )
        layout.setSpacing(scaled(SPACE["md"]))

        self.cover_label: QLabel | None = None
        if show_cover:
            self.cover_label = QLabel()
            self.cover_label.setObjectName("profileVerdictCover")
            self.cover_label.setFixedSize(
                scaled(VERDICT_COVER_WIDTH), scaled(VERDICT_COVER_HEIGHT)
            )
            keep_crisp(self.cover_label)
            self.show_placeholder()
            layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignVCenter)

        identity = QVBoxLayout()
        identity.setSpacing(0)
        # The row is as tall as its poster, so the text block is centred
        # against it rather than being spread from top to bottom by the
        # layout, which is what put a title and its year at opposite ends.
        identity.addStretch(1)
        self.title_label = QLabel(verdict.title)
        self.title_label.setObjectName("profileVerdictTitle")
        self.title_label.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self.title_label.setToolTip(verdict.title)
        identity.addWidget(self.title_label)
        meta = self._meta_text(verdict, rank_field)
        if meta:
            meta_label = QLabel(meta)
            meta_label.setObjectName("profileVerdictMeta")
            identity.addWidget(meta_label)
        identity.addStretch(1)
        layout.addLayout(identity, 1)

        figure_row = QHBoxLayout()
        figure_row.setSpacing(scaled(SPACE["lg"]))
        custom_figures = figures is not None
        if figures is None:
            figures = (
                (PROFILE_TEXT.you, verdict.your_score_text, "you"),
                (PROFILE_TEXT.community, verdict.community_score_text, "community"),
            )
            if verdict.delta is not None:
                figures += ((PROFILE_TEXT.delta, verdict.delta_text, "gap"),)
        # Kept so the spoken version and anything checking this row can be
        # built from exactly what was drawn.
        self.figures = tuple(figures)
        for caption, value, tone in self.figures:
            figure_row.addWidget(self._figure(caption, value, tone))
        layout.addLayout(figure_row)

        # The spoken version has to carry the figures that were actually
        # drawn. Built from the same tuple for that reason: a row that shows
        # "TIMES 6x" and announces "You N/A, community N/A" has moved the
        # defect rather than fixed it.
        if custom_figures:
            spoken = ", ".join(
                f"{caption.lower()} {value}" for caption, value, _tone in self.figures
            )
            self.setAccessibleName(f"{verdict.title}. {spoken}")
        else:
            # CHANGE [SPOKEN-GAP]: the gap column was drawn and never spoken.
            # A sighted reader got "-5.7"; a screen reader got "below
            # community", which is the direction without the size - and the
            # size is the whole point of a section about disagreement.
            gap = (
                f" by {verdict.delta_text}" if verdict.delta is not None else ""
            )
            self.setAccessibleName(
                f"{verdict.title}. You {verdict.your_score_text}, "
                f"community {verdict.community_score_text}, "
                f"{self._direction_words(verdict)}{gap}"
            )
        self._title_text = verdict.title

    @staticmethod
    def _direction_words(verdict: TitleVerdict) -> str:
        if verdict.direction == "above":
            return PROFILE_TEXT.above_community.lower()
        if verdict.direction == "below":
            return PROFILE_TEXT.below_community.lower()
        return "level with the community"

    @staticmethod
    def _meta_text(verdict: TitleVerdict, rank_field: str) -> str:
        if rank_field == "rank" and verdict.ranked_position is not None:
            return f"{PROFILE_TEXT.rank} {verdict.rank_text}"
        if rank_field == "popularity" and verdict.popularity_rank is not None:
            return f"{PROFILE_TEXT.popularity} {verdict.popularity_text}"
        if verdict.year is not None:
            return str(verdict.year)
        return ""

    def _figure(self, caption: str, value: str, field: str) -> QWidget:
        holder = QWidget()
        # Named so the stylesheet can keep it transparent. An unnamed QWidget
        # picks up the global page background and paints a dark rectangle over
        # whatever panel it is sitting on.
        holder.setObjectName("profileBlock")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)
        column.addStretch(1)
        caption_label = QLabel(caption)
        caption_label.setObjectName("profileVerdictCaption")
        value_label = QLabel(value)
        value_label.setObjectName("profileVerdictValue")
        value_label.setProperty("field", field)
        column.addWidget(caption_label)
        column.addWidget(value_label)
        column.addStretch(1)
        holder.setAccessibleName(f"{caption} {value}")
        return holder

    def show_placeholder(self) -> None:
        if self.cover_label is None:
            return
        placeholder = cover_placeholder_pixmap()
        if placeholder.isNull():
            return
        self.cover_label.setPixmap(
            rounded_cover(
                placeholder,
                scaled(VERDICT_COVER_WIDTH),
                scaled(VERDICT_COVER_HEIGHT),
                RADIUS["sm"],
            )
        )

    def request_cover(self) -> None:
        """Ask for artwork, if this row has any to ask for.

        The sample profile carries no cover URLs, in the way the sample
        library does not, so this is the path a real provider will use rather
        than one exercised today.
        """
        if self.cover_label is None or not self.verdict.cover_url:
            return
        self.cover_requested.emit(self.verdict.cover_url)

    def set_cover_data(self, data: bytes) -> None:
        if self.cover_label is None:
            return
        pixmap = QPixmap()
        if not data or not pixmap.loadFromData(data):
            return
        self.cover_label.setPixmap(
            rounded_cover(
                pixmap,
                scaled(VERDICT_COVER_WIDTH),
                scaled(VERDICT_COVER_HEIGHT),
                RADIUS["sm"],
            )
        )

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self.title_label.setText(
            self.title_label.fontMetrics().elidedText(
                self._title_text,
                Qt.TextElideMode.ElideRight,
                max(scaled(60), self.title_label.width()),
            )
        )


class HighlightPanel(InstrumentPanel):
    """The one title a section wants to single out, on its own plate.

    Used twice - the biggest casualty and the deepest cut - and identical both
    times, because they are the same kind of statement pointing in opposite
    directions. The legend above it is what says which.
    """

    def __init__(
        self,
        legend: str,
        verdict: TitleVerdict,
        parent: QWidget | None = None,
        *,
        rank_field: str = "rank",
        tone: str = "",
        figures: tuple[tuple[str, str, str], ...] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("profileHighlight")
        self.setProperty("tone", tone)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
        )
        layout.setSpacing(scaled(SPACE["xs"]))

        legend_label = QLabel(legend)
        legend_label.setObjectName("profileHighlightLegend")
        layout.addWidget(legend_label)

        self.row = VerdictRow(
            verdict,
            show_cover=bool(verdict.cover_url),
            rank_field=rank_field,
            figures=figures,
        )
        layout.addWidget(self.row)
        self.setAccessibleName(f"{legend.title()}: {self.row.accessibleName()}")


class VerdictColumn(QWidget):
    """An optional heading and a short run of verdict rows.

    The heading is optional because a section whose whole body is one list
    has already named itself in its legend, and printing "HYPE KILLERS" twice
    within eighty pixels is the sort of thing that makes a page look
    generated rather than laid out.
    """

    def __init__(
        self,
        heading: str,
        verdicts,
        parent: QWidget | None = None,
        *,
        show_cover: bool = False,
        rank_field: str = "",
        empty_message: str = "",
    ) -> None:
        super().__init__(parent)
        self.setObjectName("profileVerdictColumn")
        self.rows: list[VerdictRow] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["xs"]))

        if heading:
            heading_label = QLabel(heading)
            heading_label.setObjectName("profileColumnHeading")
            layout.addWidget(heading_label)

        # A poster slot is worth its width only when there is artwork to put
        # in it. Decided per column rather than per row so the titles in one
        # list stay on a common left edge.
        show_cover = show_cover and any(
            verdict.cover_url for verdict in verdicts
        )

        if not verdicts:
            empty = QLabel(empty_message or PROFILE_TEXT.section_empty)
            empty.setObjectName("profileEmptyNote")
            empty.setWordWrap(True)
            layout.addWidget(empty)
            return
        for verdict in verdicts:
            row = VerdictRow(verdict, show_cover=show_cover, rank_field=rank_field)
            self.rows.append(row)
            layout.addWidget(row)


class GenreRow(QFrame):
    """One genre: a selectable row carrying its share, its count and its average.

    Focusable and activated by Space or Enter, like the filter pills, because
    selecting a genre changes what the list underneath it shows and an
    interaction that only a mouse can reach is not an interaction.
    """

    selected = Signal(str)

    def __init__(self, reading, peak: float, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.reading = reading
        self.setObjectName("profileGenreRow")
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setProperty("selected", False)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["sm"]), scaled(SPACE["hair"]),
            scaled(SPACE["sm"]), scaled(SPACE["hair"]),
        )
        layout.setSpacing(scaled(SPACE["md"]))

        name = QLabel(reading.name)
        name.setObjectName("profileGenreName")
        name.setMinimumWidth(scaled(112))
        layout.addWidget(name)

        self.rail = BarRail(tone="you")
        self.rail.set_fraction((reading.share or 0.0) / peak if peak else 0.0)
        layout.addWidget(self.rail, 1)

        watched = QLabel(reading.watched_text)
        watched.setObjectName("profileGenreValue")
        watched.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        watched.setMinimumWidth(scaled(36))
        layout.addWidget(watched)

        average = QLabel(reading.average_text)
        average.setObjectName("profileGenreValue")
        average.setProperty("field", "average")
        average.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        average.setMinimumWidth(scaled(44))
        layout.addWidget(average)

        self.setAccessibleName(
            f"{reading.name}: {reading.watched_text} watched, "
            f"average score {reading.average_text}"
        )
        self.setAccessibleDescription("Select to list the titles behind these figures")

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", bool(selected))
        self.style().unpolish(self)
        self.style().polish(self)

    def animate(self) -> None:
        self.rail.animate()

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.selected.emit(self.reading.name)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            self.selected.emit(self.reading.name)
            return
        super().keyPressEvent(event)


class GenreDNAView(QWidget):
    """Genre distribution, the three verdicts, and the drill-down beneath.

    The distribution is bars, not a ring. A donut would have to be read by
    arc length against a legend, when the thing a reader actually wants from
    this section is "which of these did I score well" - two columns of numbers
    on a common baseline, which is a table with a bar in it.
    """

    metadata_filter_requested = Signal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileGenreDNA")
        self.rows: list[GenreRow] = []
        self._readings: dict[str, object] = {}
        self._selected = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["md"]))

        # These are peer facts, so their columns must be allocated equally.
        # A horizontal box distributes from each child's preferred width;
        # longer legends then make the middle fact visibly wider than the
        # others. The grid ignores those content-size differences and keeps
        # all three readouts on one regular measure.
        self.verdict_row = QGridLayout()
        self.verdict_row.setHorizontalSpacing(scaled(SPACE["xl"]))
        self.verdict_row.setVerticalSpacing(0)
        for column in range(3):
            self.verdict_row.setColumnStretch(column, 1)
        layout.addLayout(self.verdict_row)
        self.verdict_blocks: list[QWidget] = []

        self.rows_layout = QVBoxLayout()
        self.rows_layout.setSpacing(scaled(SPACE["hair"]))
        layout.addLayout(self.rows_layout)

        self.drill = QFrame()
        self.drill.setObjectName("profileGenreDrill")
        self.drill_layout = QVBoxLayout(self.drill)
        self.drill_layout.setContentsMargins(
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
            scaled(SPACE["md"]), scaled(SPACE["sm"]),
        )
        self.drill_layout.setSpacing(scaled(SPACE["hair"]))
        layout.addWidget(self.drill)

    def set_genres(self, genres) -> None:
        while self.verdict_row.count():
            item = self.verdict_row.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self.verdict_blocks = []
        for column, (legend, verdict, detail) in enumerate((
            (PROFILE_TEXT.genre_best, genres.best_match, ""),
            (PROFILE_TEXT.genre_weakness, genres.weakness, ""),
            (
                PROFILE_TEXT.genre_divisive,
                genres.divisive,
                genres.divisive.detail if genres.divisive else "",
            ),
        )):
            if verdict is None:
                continue
            block = self._verdict_block(legend, verdict, detail)
            block.setSizePolicy(
                QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
            )
            self.verdict_blocks.append(block)
            self.verdict_row.addWidget(block, 0, column)

        for row in self.rows:
            row.setParent(None)
            row.deleteLater()
        self.rows = []
        self._readings = {reading.name: reading for reading in genres.readings}
        peak = genres.peak_share or 1.0
        for reading in genres.readings:
            row = GenreRow(reading, peak, self)
            row.selected.connect(self.select_genre)
            self.rows.append(row)
            self.rows_layout.addWidget(row)
        if genres.readings:
            self.select_genre(genres.readings[0].name)

    def _verdict_block(self, legend: str, verdict, detail: str) -> QWidget:
        holder = QWidget()
        holder.setObjectName("profileBlock")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(scaled(SPACE["hair"]))
        legend_label = QLabel(legend)
        legend_label.setObjectName("profileVerdictLegend")
        legend_label.setWordWrap(True)
        legend_label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )
        # Every block reserves the same two-line legend band. A longer label
        # can wrap without moving its tag and figures lower than its peers.
        legend_label.setMinimumHeight(legend_label.fontMetrics().lineSpacing() * 2)
        column.addWidget(legend_label)

        tag = MetadataTag(FilterKind.GENRE, verdict.name)
        tag.clicked.connect(
            lambda _checked=False, value=verdict.name: self.metadata_filter_requested.emit(
                FilterKind.GENRE, value
            )
        )
        column.addWidget(tag, 0, Qt.AlignmentFlag.AlignLeft)

        figures = QHBoxLayout()
        figures.setSpacing(scaled(SPACE["md"]))
        figures.addWidget(
            ReadoutPair(PROFILE_TEXT.genre_watched, verdict.watched_text)
        )
        figures.addWidget(
            ReadoutPair(PROFILE_TEXT.genre_average, verdict.average_text, tone="you")
        )
        figures.addStretch(1)
        column.addLayout(figures)

        if detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("profileVerdictDetail")
            column.addWidget(detail_label)
        # Three blocks of different heights sit in one row; without this the
        # shorter two spread their contents and their legends stop lining up.
        column.addStretch(1)
        holder.setAccessibleName(
            f"{legend.title()}: {verdict.name}, {verdict.watched_text} watched, "
            f"average {verdict.average_text}"
        )
        return holder

    def select_genre(self, name: str) -> None:
        self._selected = name
        for row in self.rows:
            row.set_selected(row.reading.name == name)
        while self.drill_layout.count():
            item = self.drill_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        heading = QLabel(PROFILE_TEXT.genre_titles_heading.format(genre=name.upper()))
        heading.setObjectName("profileColumnHeading")
        self.drill_layout.addWidget(heading)
        reading = self._readings.get(name)
        titles = getattr(reading, "titles", ()) if reading is not None else ()
        if not titles:
            empty = QLabel(PROFILE_TEXT.genre_titles_empty)
            empty.setObjectName("profileEmptyNote")
            self.drill_layout.addWidget(empty)
            return
        for entry in titles:
            row = QWidget()
            row.setObjectName("profileBlock")
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(scaled(SPACE["md"]))
            title = QLabel(entry.title)
            title.setObjectName("profileTitleName")
            score = QLabel(entry.your_score_text)
            score.setObjectName("profileTitleScore")
            score.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            row_layout.addWidget(title, 1)
            row_layout.addWidget(score)
            row.setAccessibleName(f"{entry.title}, you rated {entry.your_score_text}")
            self.drill_layout.addWidget(row)

    def animate(self) -> None:
        for row in self.rows:
            row.animate()


class StudioDNAView(QWidget):
    """Three studio verdicts, and the houses behind them as filter tags.

    Kept small on purpose. These are profile facts - the studio you watch
    most, the one you trust, the one you keep bouncing off - not a ranking
    table, and giving them a table's worth of room would say otherwise.
    """

    metadata_filter_requested = Signal(object, str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileStudioDNA")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["md"]))
        self.verdict_row = QHBoxLayout()
        self.verdict_row.setSpacing(scaled(SPACE["xl"]))
        layout.addLayout(self.verdict_row)
        self.tag_row = QHBoxLayout()
        self.tag_row.setSpacing(scaled(SPACE["xs"]))
        layout.addLayout(self.tag_row)

    def set_studios(self, studios) -> None:
        for row in (self.verdict_row, self.tag_row):
            while row.count():
                item = row.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()

        for legend, studio, tone in (
            (PROFILE_TEXT.studio_most_watched, studios.most_watched, ""),
            (PROFILE_TEXT.studio_most_trusted, studios.most_trusted, "you"),
            (PROFILE_TEXT.studio_nemesis, studios.nemesis, "against"),
        ):
            if studio is None:
                continue
            self.verdict_row.addWidget(self._verdict_block(legend, studio, tone))
        self.verdict_row.addStretch(1)

        for studio in studios.readings:
            tag = MetadataTag(FilterKind.STUDIO, studio.name)
            tag.setToolTip(
                f"{studio.name}, {studio.watched_text} watched, "
                f"average {studio.average_text}"
            )
            tag.clicked.connect(
                lambda _checked=False, value=studio.name: self.metadata_filter_requested.emit(
                    FilterKind.STUDIO, value
                )
            )
            self.tag_row.addWidget(tag)
        self.tag_row.addStretch(1)

    def _verdict_block(self, legend: str, studio, tone: str) -> QWidget:
        holder = QWidget()
        holder.setObjectName("profileBlock")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(scaled(SPACE["hair"]))
        legend_label = QLabel(legend)
        legend_label.setObjectName("profileVerdictLegend")
        column.addWidget(legend_label)
        name = QLabel(studio.name)
        name.setObjectName("profileVerdictName")
        column.addWidget(name)
        figures = QHBoxLayout()
        figures.setSpacing(scaled(SPACE["md"]))
        figures.addWidget(ReadoutPair(PROFILE_TEXT.studio_titles, studio.watched_text))
        figures.addWidget(
            ReadoutPair(
                PROFILE_TEXT.genre_average,
                studio.average_text,
                tone="you" if tone == "you" else ("against" if tone else ""),
            )
        )
        figures.addStretch(1)
        column.addLayout(figures)
        column.addStretch(1)
        holder.setAccessibleName(
            f"{legend.title()}: {studio.name}, {studio.watched_text} titles, "
            f"average {studio.average_text}"
        )
        return holder


class EraPreferencesView(QWidget):
    """Which decade of anime this reader finishes, and which season they favour."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileEras")
        self.rails: list[BarRail] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["md"]))

        self.golden_row = QHBoxLayout()
        self.golden_row.setSpacing(scaled(SPACE["xl"]))
        layout.addLayout(self.golden_row)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(scaled(SPACE["md"]))
        self.grid.setVerticalSpacing(scaled(SPACE["xs"]))
        self.grid.setColumnStretch(1, 1)
        layout.addLayout(self.grid)

        self.season_heading = QLabel(PROFILE_TEXT.era_season_heading)
        self.season_heading.setObjectName("profileColumnHeading")
        layout.addWidget(self.season_heading)
        self.season_grid = QGridLayout()
        self.season_grid.setContentsMargins(0, 0, 0, 0)
        self.season_grid.setHorizontalSpacing(scaled(SPACE["md"]))
        self.season_grid.setVerticalSpacing(scaled(SPACE["xs"]))
        self.season_grid.setColumnStretch(1, 1)
        layout.addLayout(self.season_grid)

    def set_eras(self, eras) -> None:
        for grid in (self.golden_row, self.grid, self.season_grid):
            while grid.count():
                item = grid.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.setParent(None)
                    widget.deleteLater()
        self.rails = []

        if eras.golden is not None:
            block = QWidget()
            block.setObjectName("profileBlock")
            column = QVBoxLayout(block)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(scaled(SPACE["hair"]))
            legend = QLabel(PROFILE_TEXT.era_golden)
            legend.setObjectName("profileVerdictLegend")
            name = QLabel(eras.golden.label)
            name.setObjectName("profileVerdictName")
            column.addWidget(legend)
            column.addWidget(name)
            figures = QHBoxLayout()
            figures.setSpacing(scaled(SPACE["md"]))
            figures.addWidget(
                ReadoutPair(PROFILE_TEXT.genre_average, eras.golden.average_text, tone="you")
            )
            figures.addWidget(
                ReadoutPair(PROFILE_TEXT.genre_watched, eras.golden.watched_text)
            )
            figures.addStretch(1)
            column.addLayout(figures)
            column.addStretch(1)
            block.setAccessibleName(
                f"Golden era: {eras.golden.label}, average {eras.golden.average_text}"
            )
            self.golden_row.addWidget(block)
        if eras.season_of_choice:
            block = QWidget()
            block.setObjectName("profileBlock")
            column = QVBoxLayout(block)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(scaled(SPACE["hair"]))
            legend = QLabel(PROFILE_TEXT.era_season_choice)
            legend.setObjectName("profileVerdictLegend")
            name = QLabel(eras.season_of_choice)
            name.setObjectName("profileVerdictName")
            column.addWidget(legend)
            column.addWidget(name)
            column.addStretch(1)
            block.setAccessibleName(
                f"Season of choice: {eras.season_of_choice.title()}"
            )
            self.golden_row.addWidget(block)
        self.golden_row.addStretch(1)

        peak = eras.peak_watched or 1
        for row_index, bucket in enumerate(eras.buckets):
            label = QLabel(bucket.label)
            label.setObjectName("profileEraLabel")
            rail = BarRail(tone="you")
            rail.set_fraction((bucket.watched or 0) / peak)
            rail.setAccessibleName(
                f"{bucket.label}: {bucket.watched_text} watched, "
                f"average {bucket.average_text}"
            )
            watched = QLabel(bucket.watched_text)
            watched.setObjectName("profileEraValue")
            watched.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            average = QLabel(bucket.average_text)
            average.setObjectName("profileEraValue")
            average.setProperty("field", "average")
            average.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.grid.addWidget(label, row_index, 0)
            self.grid.addWidget(rail, row_index, 1)
            self.grid.addWidget(watched, row_index, 2)
            self.grid.addWidget(average, row_index, 3)
            self.rails.append(rail)

        # Seasons are averages, not counts, so their rails cannot be drawn
        # from zero: four averages between 7.1 and 8.0 would come out as four
        # bars of the same length and the section would say nothing. They are
        # drawn against a whole-point span instead, and that span is printed
        # beside the heading, because a suppressed baseline that is not
        # declared is the oldest misleading chart there is.
        averages = [
            season.average for season in eras.seasons if season.average is not None
        ]
        low = float(math.floor(min(averages))) if averages else 0.0
        high = max(low + 1.0, float(math.ceil(max(averages))) if averages else low + 1.0)
        self.season_heading.setText(
            f"{PROFILE_TEXT.era_season_heading}   {PROFILE_TEXT.era_season_scale}"
            f"  {low:.1f}–{high:.1f}"
            if averages
            else PROFILE_TEXT.era_season_heading
        )
        for row_index, season in enumerate(eras.seasons):
            label = QLabel(season.name)
            label.setObjectName("profileEraLabel")
            rail = BarRail(tone="community")
            rail.set_fraction(
                ((season.average or low) - low) / (high - low)
            )
            rail.setAccessibleName(
                f"{season.name.title()}: average score {season.average_text}"
            )
            value = QLabel(season.average_text)
            value.setObjectName("profileEraValue")
            value.setProperty("field", "average")
            value.setAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self.season_grid.addWidget(label, row_index, 0)
            self.season_grid.addWidget(rail, row_index, 1)
            self.season_grid.addWidget(value, row_index, 2)
            self.rails.append(rail)

    def animate(self) -> None:
        for rail in self.rails:
            rail.animate()


class WatchingHabitsView(QWidget):
    """The behavioural percentages, as one strip of readouts with their rails."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileHabits")
        self.banks: list[CellBank] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["md"]))
        self.modules = ReflowGrid(FINGERPRINT_MIN_WIDTH, spacing="md")
        layout.addWidget(self.modules)
        self.rewatch_label = QLabel("")
        self.rewatch_label.setObjectName("profileRewatchNote")
        self.rewatch_label.setVisible(False)
        layout.addWidget(self.rewatch_label)

    def set_habits(self, habits) -> None:
        self.banks = []
        modules = []
        for reading in habits.readings:
            module = QWidget()
            module.setObjectName("profileBlock")
            column = QVBoxLayout(module)
            column.setContentsMargins(0, 0, 0, 0)
            column.setSpacing(scaled(SPACE["xs"]))
            readout = ReadoutPair(reading.caption, reading.value_text, size="lg")
            column.addWidget(readout)
            bank = CellBank(tone="you")
            bank.set_fraction(reading.position or 0.0)
            bank.setAccessibleName(f"{reading.caption.title()}: {reading.value_text}")
            column.addWidget(bank)
            self.banks.append(bank)
            modules.append(module)
        self.modules.set_widgets(modules)

        note = habits.most_rewatched
        if note is not None:
            self.rewatch_label.setText(
                f"{PROFILE_TEXT.habits_rewatched}   {note.title}   {note.watches_text}"
            )
            self.rewatch_label.setAccessibleName(
                f"Most rewatched: {note.title}, {note.watches_text} watches"
            )
        self.rewatch_label.setVisible(note is not None)

    def animate(self) -> None:
        for bank in self.banks:
            bank.animate()


class RatingTimelineView(QWidget):
    """Mean score per year, with the years labelled under the plot."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("profileTimeline")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(scaled(SPACE["xs"]))

        top = QHBoxLayout()
        top.setSpacing(scaled(SPACE["xl"]))
        self.trend = ReadoutPair(PROFILE_TEXT.timeline_trend, DASH, size="lg", tone="you")
        top.addWidget(self.trend)
        self.trend_detail = QLabel("")
        self.trend_detail.setObjectName("profileVerdictDetail")
        top.addWidget(self.trend_detail, 0, Qt.AlignmentFlag.AlignBottom)
        top.addStretch(1)
        layout.addLayout(top)

        self.plot = TimelinePlot()
        layout.addWidget(self.plot)

        self.axis = QHBoxLayout()
        self.axis.setContentsMargins(0, 0, 0, 0)
        self.axis.setSpacing(0)
        layout.addLayout(self.axis)

    def set_timeline(self, timeline) -> None:
        self.trend.set_value(timeline.trend or DASH, tone="you")
        self.trend_detail.setText(timeline.trend_detail)
        self.plot.set_points(
            ((point.year, point.average) for point in timeline.points),
            timeline.bounds,
        )
        low, high = timeline.bounds
        self.plot.setAccessibleName(
            "Mean score by year: "
            + ", ".join(
                f"{point.year} {point.average_text}" for point in timeline.points
            )
        )
        self.plot.setToolTip(
            f"{PROFILE_TEXT.timeline_axis_low} {low:.1f} / "
            f"{PROFILE_TEXT.timeline_axis_high} {high:.1f}"
        )
        while self.axis.count():
            item = self.axis.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for point in timeline.points:
            label = QLabel(str(point.year))
            label.setObjectName("profileAxisTick")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.axis.addWidget(label, 1)

    def animate(self) -> None:
        self.plot.animate()


class ProfilePage(QWidget):
    """The Profile surface: a header, then eleven readouts about one reader."""

    retry_requested = Signal()
    sample_requested = Signal()
    metadata_filter_requested = Signal(object, str)
    cover_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("page-profile")
        self.setAccessibleName("Profile page")
        self._profile: TasteProfile | None = None
        self.sections: dict[str, ProfileSection] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            scaled(SPACE["sm"]), scaled(SPACE["sm"]),
            scaled(SPACE["sm"]), scaled(SPACE["sm"]),
        )
        layout.setSpacing(scaled(SPACE["md"]))

        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("profileContentStack")
        stack_layout = self.content_stack.layout()
        if stack_layout is not None:
            stack_layout.setContentsMargins(0, 0, 0, 0)
            stack_layout.setSpacing(0)

        # The same panel Compare shows, so an unreadable profile and an
        # unreadable comparison are the same object in the same place.
        self.state_panel = StatePanel()
        self.state_panel.retry_requested.connect(self.retry_requested.emit)
        self.state_panel.secondary_requested.connect(self.sample_requested.emit)
        self._state_index = self.content_stack.addWidget(self.state_panel)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("profileScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container.setObjectName("profileContainer")
        self.container_layout = QVBoxLayout(container)
        self.container_layout.setContentsMargins(0, 0, 0, scaled(SPACE["xl"]))
        self.container_layout.setSpacing(scaled(SPACE["xl"]))
        self._build_sections()
        self.container_layout.addStretch(1)
        self.scroll.setWidget(container)
        self._result_index = self.content_stack.addWidget(self.scroll)

        layout.addWidget(self.content_stack, 1)
        self.show_idle()

    # ---- construction ----------------------------------------------------

    def _build_sections(self) -> None:
        channel = QLabel(PROFILE_TEXT.channel)
        channel.setObjectName("profileChannel")
        self.container_layout.addWidget(channel)
        hint = QLabel(PROFILE_TEXT.hint)
        hint.setObjectName("profileHint")
        hint.setWordWrap(True)
        self.container_layout.addWidget(hint)

        self.header = ProfileHeader()
        self.container_layout.addWidget(self.header)

        # The page's opening statement, then the named titles that prove it.
        self.verdict = VerdictHero()
        self.container_layout.addWidget(self.verdict)

        # The wink, as its own titled section rather than a fact buried in a
        # chart. This is the part of the page that could not be screenshotted
        # off MyAnimeList, so it is named for that.
        self.unlisted = UnlistedFacts()
        self._unlisted_section = ProfileSection(
            "unlisted",
            PROFILE_TEXT.unlisted_title,
            PROFILE_TEXT.unlisted_description,
            skeleton_rows=5,
        )
        self._unlisted_section.add_body(self.unlisted)
        self.sections["unlisted"] = self._unlisted_section
        self.container_layout.addWidget(self._unlisted_section)

        # Everything below is the instrument: the same eleven readings, now
        # folded shut and laid out as widgets rather than as a scroll.
        instruments_title = QLabel(PROFILE_TEXT.instruments_title)
        instruments_title.setObjectName("profileSectionTitle")
        instruments_title.setProperty("staticLegend", True)
        self.container_layout.addWidget(instruments_title)
        instruments_hint = QLabel(PROFILE_TEXT.instruments_description)
        instruments_hint.setObjectName("profileSectionDescription")
        instruments_hint.setWordWrap(True)
        self.container_layout.addWidget(instruments_hint)

        self.instrument_grid = ReflowGrid(
            INSTRUMENT_MIN_WIDTH, spacing="lg", avoid_orphans=False
        )
        self.container_layout.addWidget(self.instrument_grid)
        self._instruments: list[ProfileSection] = []

        self.fingerprint = TasteFingerprint()
        self._add_section(
            "fingerprint",
            PROFILE_TEXT.fingerprint_title,
            PROFILE_TEXT.fingerprint_description,
            self.fingerprint,
            skeleton_rows=3,
        )

        self.histogram = RatingDistributionChart()
        self._add_section(
            "distribution",
            PROFILE_TEXT.distribution_title,
            PROFILE_TEXT.distribution_description,
            self.histogram,
            skeleton_rows=10,
        )

        self.hot_takes = ReflowGrid(COLUMN_MIN_WIDTH, spacing="xl")
        self._add_section(
            "hot-takes",
            PROFILE_TEXT.hot_takes_title,
            PROFILE_TEXT.hot_takes_description,
            self.hot_takes,
            skeleton_rows=5,
        )

        self.hype_killers = QWidget()
        self.hype_layout = QVBoxLayout(self.hype_killers)
        self.hype_layout.setContentsMargins(0, 0, 0, 0)
        self.hype_layout.setSpacing(scaled(SPACE["md"]))
        self._add_section(
            "hype-killers",
            PROFILE_TEXT.hype_killers_title,
            PROFILE_TEXT.hype_killers_description,
            self.hype_killers,
            skeleton_rows=4,
        )

        self.hidden_gems = QWidget()
        self.gems_layout = QVBoxLayout(self.hidden_gems)
        self.gems_layout.setContentsMargins(0, 0, 0, 0)
        self.gems_layout.setSpacing(scaled(SPACE["md"]))
        self._add_section(
            "hidden-gems",
            PROFILE_TEXT.hidden_gems_title,
            PROFILE_TEXT.hidden_gems_description,
            self.hidden_gems,
            skeleton_rows=4,
        )

        self.genres = GenreDNAView()
        self.genres.metadata_filter_requested.connect(
            self.metadata_filter_requested.emit
        )
        self._add_section(
            "genres",
            PROFILE_TEXT.genre_title,
            PROFILE_TEXT.genre_description,
            self.genres,
            skeleton_rows=8,
        )

        self.studios = StudioDNAView()
        self.studios.metadata_filter_requested.connect(
            self.metadata_filter_requested.emit
        )
        self._add_section(
            "studios",
            PROFILE_TEXT.studio_title,
            PROFILE_TEXT.studio_description,
            self.studios,
            skeleton_rows=2,
        )

        self.eras = EraPreferencesView()
        self._add_section(
            "eras",
            PROFILE_TEXT.era_title,
            PROFILE_TEXT.era_description,
            self.eras,
            skeleton_rows=6,
        )

        self.habits = WatchingHabitsView()
        self._add_section(
            "habits",
            PROFILE_TEXT.habits_title,
            PROFILE_TEXT.habits_description,
            self.habits,
            skeleton_rows=2,
        )

        self.timeline = RatingTimelineView()
        self._add_section(
            "timeline",
            PROFILE_TEXT.timeline_title,
            PROFILE_TEXT.timeline_description,
            self.timeline,
            skeleton_rows=4,
        )

        # Every instrument now exists; lay them into the reflowing grid in
        # the order they were declared.
        self.instrument_grid.set_widgets(self._instruments)

    def _add_section(
        self,
        section_id: str,
        title: str,
        description: str,
        body: QWidget,
        *,
        skeleton_rows: int,
    ) -> ProfileSection:
        section = ProfileSection(
            section_id, title, description, skeleton_rows=skeleton_rows
        )
        section.add_body(body)
        section.retry_requested.connect(lambda _id: self.retry_requested.emit())
        self.sections[section_id] = section
        # Collapsed by default: the reader has already been told what they
        # are, above. These are for the reader who wants to check the working.
        section.set_expanded(False)
        self._instruments.append(section)
        return section

    # ---- states ----------------------------------------------------------

    def show_idle(self) -> None:
        self.state_panel.show_state(
            PROFILE_TEXT.backend_title,
            PROFILE_TEXT.backend_message,
            icon="details-inspector",
            secondary=PROFILE_TEXT.backend_sample_action,
        )
        self.content_stack.setCurrentIndex(self._state_index)

    def show_loading(self) -> None:
        self.state_panel.show_state(
            PROFILE_TEXT.loading_title,
            PROFILE_TEXT.loading_message,
            icon="sync",
        )
        self.content_stack.setCurrentIndex(self._state_index)

    def show_unavailable(
        self, error: TasteProfileUnavailable, *, offer_sample: bool = False
    ) -> None:
        title, message, icon, tone, retry = STATE_FOR_REASON.get(
            error.reason,
            (
                PROFILE_TEXT.backend_title,
                PROFILE_TEXT.backend_message,
                "details-inspector",
                "",
                False,
            ),
        )
        self.state_panel.show_state(
            title,
            error.message or message,
            icon=icon,
            tone=tone,
            retry=retry,
            secondary=PROFILE_TEXT.backend_sample_action if offer_sample else "",
        )
        self.content_stack.setCurrentIndex(self._state_index)

    @property
    def is_showing_profile(self) -> bool:
        return self.content_stack.currentIndex() == self._result_index

    def show_profile(self, profile: TasteProfile) -> None:
        """Draw a prepared profile, section by section.

        Each section is filled inside its own guard. A provider that answers
        with a malformed genre block should cost the reader their genre panel
        and nothing else, which is the whole reason the sections are separate
        objects rather than one long layout.
        """
        self._profile = profile
        self.header.set_profile(profile)
        # The reading first, and deliberately not inside a guarded section: a
        # page whose entire purpose is to tell you what kind of reader you are
        # should not be able to render without saying anything.
        self.verdict.set_archetype(archetype_for(profile))

        self._fill("unlisted", lambda: self._fill_unlisted(profile))
        self._fill("fingerprint", lambda: self._fill_fingerprint(profile))
        self._fill("distribution", lambda: self._fill_distribution(profile))
        self._fill("hot-takes", lambda: self._fill_hot_takes(profile))
        self._fill("hype-killers", lambda: self._fill_hype_killers(profile))
        self._fill("hidden-gems", lambda: self._fill_hidden_gems(profile))
        self._fill("genres", lambda: self._fill_genres(profile))
        self._fill("studios", lambda: self._fill_studios(profile))
        self._fill("eras", lambda: self._fill_eras(profile))
        self._fill("habits", lambda: self._fill_habits(profile))
        self._fill("timeline", lambda: self._fill_timeline(profile))

        self.content_stack.setCurrentIndex(self._result_index)
        self.animate()

    def _fill(self, section_id: str, filler) -> None:
        section = self.sections[section_id]
        try:
            filled = filler()
        except (AttributeError, TypeError, ValueError, ZeroDivisionError):
            section.show_error()
            return
        if filled is False:
            section.set_badge("")
            section.show_empty()
            return
        section.show_content()

    def _fill_unlisted(self, profile: TasteProfile) -> bool:
        self.unlisted.set_profile(profile)
        return bool(self.unlisted.sentences)

    def _fill_fingerprint(self, profile: TasteProfile) -> bool:
        if not profile.fingerprint:
            return False
        self.fingerprint.set_readings(profile.fingerprint)
        return True

    def _fill_distribution(self, profile: TasteProfile) -> bool:
        distribution = profile.rating_distribution
        if not distribution:
            return False
        self.histogram.set_distribution(distribution)
        return True

    def _fill_hot_takes(self, profile: TasteProfile) -> bool:
        takes = profile.hot_takes
        if not takes:
            return False
        columns = [
            VerdictColumn(
                PROFILE_TEXT.hot_takes_higher,
                takes.higher,
                show_cover=True,
                empty_message=PROFILE_TEXT.hot_takes_empty,
            ),
            VerdictColumn(
                PROFILE_TEXT.hot_takes_lower,
                takes.lower,
                show_cover=True,
                empty_message=PROFILE_TEXT.hot_takes_empty,
            ),
        ]
        for column in columns:
            for row in column.rows:
                row.cover_requested.connect(self.cover_requested.emit)
        self.hot_takes.set_widgets(columns)
        return True

    def _fill_hype_killers(self, profile: TasteProfile) -> bool:
        killers = profile.hype_killers
        if not killers:
            return False
        self._clear(self.hype_layout)
        self.sections["hype-killers"].set_badge(
            f"{PROFILE_TEXT.hype_killed}  {killers.count_text}"
        )
        if killers.biggest is not None:
            highlight = HighlightPanel(
                PROFILE_TEXT.hype_killers_biggest,
                killers.biggest,
                rank_field="rank",
                tone="against",
            )
            highlight.row.cover_requested.connect(self.cover_requested.emit)
            self.hype_layout.addWidget(highlight)
        column = VerdictColumn(
            "",
            killers.entries,
            rank_field="rank",
            empty_message=PROFILE_TEXT.hype_killers_empty,
        )
        self.hype_layout.addWidget(column)
        return True

    def _fill_hidden_gems(self, profile: TasteProfile) -> bool:
        gems = profile.hidden_gems
        if not gems:
            return False
        self._clear(self.gems_layout)
        self.sections["hidden-gems"].set_badge(
            f"{PROFILE_TEXT.hidden_gem_rate}  {gems.rate_text}"
        )
        if gems.deepest is not None:
            highlight = HighlightPanel(
                PROFILE_TEXT.hidden_gems_deepest,
                gems.deepest,
                rank_field="popularity",
                tone="you",
            )
            highlight.row.cover_requested.connect(self.cover_requested.emit)
            self.gems_layout.addWidget(highlight)
        column = VerdictColumn(
            "",
            gems.entries,
            rank_field="popularity",
            empty_message=PROFILE_TEXT.hidden_gems_empty,
        )
        self.gems_layout.addWidget(column)
        return True

    def _fill_genres(self, profile: TasteProfile) -> bool:
        if not profile.genres:
            return False
        self.genres.set_genres(profile.genres)
        return True

    def _fill_studios(self, profile: TasteProfile) -> bool:
        if not profile.studios:
            return False
        self.studios.set_studios(profile.studios)
        return True

    def _fill_eras(self, profile: TasteProfile) -> bool:
        if not profile.eras:
            return False
        self.eras.set_eras(profile.eras)
        return True

    def _fill_habits(self, profile: TasteProfile) -> bool:
        if not profile.habits:
            return False
        self.habits.set_habits(profile.habits)
        return True

    def _fill_timeline(self, profile: TasteProfile) -> bool:
        if not profile.timeline:
            return False
        self.timeline.set_timeline(profile.timeline)
        return True

    @staticmethod
    def _clear(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    # ---- housekeeping ----------------------------------------------------

    def animate(self) -> None:
        """Fill every instrument on the page once, together.

        One pass rather than a stagger: a page that reveals eleven sections in
        sequence is a title card, and by the time the last bar arrives the
        reader has finished reading the first. On a machine that has asked for
        less motion this draws the finished state immediately.
        """
        if not motion_enabled():
            return
        for widget in (
            self.fingerprint,
            self.histogram,
            self.genres,
            self.eras,
            self.habits,
            self.timeline,
        ):
            widget.animate()

    def request_visible_covers(self) -> None:
        for row in self._cover_rows():
            row.request_cover()

    def _cover_rows(self):
        """Every row on the page that has a poster slot."""
        return tuple(self.findChildren(VerdictRow))

    def apply_scale(self) -> None:
        """Re-fix every hand-sized dimension after the GUI scale changes."""
        self.header.avatar.apply_scale()
        for widget in self.findChildren(QWidget):
            rescale = getattr(widget, "apply_scale", None)
            if callable(rescale) and widget is not self:
                rescale()

    def retint_icons(self) -> None:
        """Redraw everything rendered from an SVG after the palette changes.

        The state panel's mark and the cover placeholder are both painted at
        a colour taken from the theme, so both have to be asked again rather
        than left holding the previous palette's pixmap.
        """
        self.state_panel.retint_icons()
        for row in self._cover_rows():
            row.show_placeholder()
