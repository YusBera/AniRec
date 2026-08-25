"""Addresses: BUG2 (DPI and GUI scale, portrait centring), FEAT2 (match badge).

Every hand-chosen pixel dimension here goes through ``scaled()`` so the whole
card grows and shrinks with the GUI Scale setting. Qt stylesheets have no
relative units to use instead.
Reference-aligned recommendation card with safe cover and MAL actions.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QFocusEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
)
from PySide6.QtWidgets import (
    QFrame,
    QStyle,
    QStyleOption,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .cover_art import rounded_cover
from .design_tokens import RADIUS, SPACE
from .match_badge import (
    BADGE_BOTTOM_INSET,
    BAR_SIDE_INSET,
    MatchBadge,
    should_show_badge,
)
from .scaling import scaled
from .recommendation_view_model import RecommendationViewModel
from .resources import cover_placeholder_pixmap


CARD_WIDTH = 224
# A 2:3 poster, the standard shape for anime cover art. Sized so that a whole
# card, including the review actions, fits the default window without
# scrolling; at the previous size the buttons sat below the fold.
# 2:3 exactly (172*3 == 258*2). Trimmed a little from 176x264 to buy back the
# height the extra spacing cost, so the review loop still fits the default
# window with room to spare.
COVER_WIDTH = 172
COVER_HEIGHT = 258
# Matches the card's own corner radius so the portrait sits inside it rather
# than cutting across it.
COVER_RADIUS = RADIUS["md"]

# Line budgets for the wrapped labels. Generous enough that clipping is rare,
# and identical for every card so the rows line up across the grid.
TITLE_LINES = 2
SECONDARY_TITLE_LINES = 1
META_LINES = 1
GENRE_LINES = 2
REASON_LINES = 3


class CoverMemoryCache:
    def __init__(self, maximum_items: int = 64) -> None:
        self.maximum_items = maximum_items
        self._items: OrderedDict[str, QPixmap] = OrderedDict()

    def get(self, url: str) -> QPixmap | None:
        pixmap = self._items.get(url)
        if pixmap is not None:
            self._items.move_to_end(url)
        return pixmap

    def put(self, url: str, pixmap: QPixmap) -> None:
        self._items[url] = pixmap
        self._items.move_to_end(url)
        while len(self._items) > self.maximum_items:
            self._items.popitem(last=False)

    def clear(self) -> None:
        self._items.clear()


MEMORY_COVER_CACHE = CoverMemoryCache()


def open_mal_url(url: str | None, *, opener: Callable[[QUrl], bool] = QDesktopServices.openUrl) -> bool:
    if not url:
        return False
    parsed = QUrl(url)
    if (
        not parsed.isValid()
        or parsed.scheme().casefold() != "https"
        or parsed.host().casefold() not in {"myanimelist.net", "www.myanimelist.net"}
        or not parsed.path().startswith("/anime/")
    ):
        return False
    segments = [segment for segment in parsed.path().split("/") if segment]
    if len(segments) < 2 or segments[0].casefold() != "anime" or not segments[1].isdigit():
        return False
    return opener(parsed)


class ElidingLabel(QLabel):
    """A single-line label that ends in an ellipsis rather than being cut off.

    CHANGE [BUG7]: the alternative, rewriting the label's text, makes text()
    report a string the anime is not called, so anything reading the card's
    contents sees a truncated title as if it were the real one. Eliding while
    painting keeps the full string on the widget, and re-fits by itself after
    a resize or a font change instead of relying on somebody remembering to
    recompute it.
    """

    def paintEvent(self, _event) -> None:
        option = QStyleOption()
        option.initFrom(self)
        painter = QPainter(self)
        # The stylesheet owns the background and border; draw those first or
        # a styled label loses them.
        self.style().drawPrimitive(
            QStyle.PrimitiveElement.PE_Widget, option, painter, self
        )
        rect = self.contentsRect()
        elided = self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, rect.width()
        )
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, int(self.alignment()), elided)
        painter.end()


class RecommendationCard(QFrame):
    cover_requested = Signal(str)
    details_requested = Signal(object)
    selection_requested = Signal(object)
    hide_requested = Signal(object)
    watch_later_requested = Signal(object)
    liked_requested = Signal(object)
    disliked_requested = Signal(object)

    def __init__(
        self,
        model: RecommendationViewModel,
        parent: QWidget | None = None,
        *,
        mal_opener: Callable[[QUrl], bool] = QDesktopServices.openUrl,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self._mal_opener = mal_opener
        self.setObjectName("recommendationCard")
        self.setProperty("recommendationCard", True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Anime recommendation: {model.display_title}")
        # CHANGE [BUG2]: was a fixed 224px, so the card kept one size while the
        # logical window shrank at higher DPI and took a larger share of it.
        self.setFixedWidth(scaled(CARD_WIDTH))
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)

        layout = QVBoxLayout(self)
        # CHANGE [BUG2]: margins and spacing scale too, or the card's proportions
        # change as it grows.
        layout.setContentsMargins(
            scaled(SPACE['md']), scaled(SPACE['sm']),
            scaled(SPACE['md']), scaled(SPACE['md']),
        )
        # CHANGE [BUG7]: 4px between eleven stacked items left every label
        # touching the control above it, so the buttons read as part of the
        # text rather than as separate things to press.
        #
        # The separation is carried by this one value rather than by extra
        # spacers between groups. addSpacing inserts a layout item, so a 4px
        # spacer actually costs 4px plus another full spacing gap beside it,
        # and three of them pushed the feedback buttons past the point where
        # the review loop still fits the default window.
        layout.setSpacing(scaled(SPACE['sm']))
        self.cover_label = QLabel()
        self.cover_label.setObjectName("recommendationCover")
        # CHANGE [BUG2]: scale the portrait with the rest of the card.
        self.cover_label.setFixedSize(scaled(COVER_WIDTH), scaled(COVER_HEIGHT))
        self.cover_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # CHANGE [BUG7]: the portrait must not absorb any of the slack created
        # by equalising card heights. Without this the leftover pixels were
        # shared into the cells above the text and each card put its first
        # line in a slightly different place.
        self.cover_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.cover_label.setAccessibleName(f"Cover for {model.display_title}")
        self.cover_label.setToolTip(f"Cover for {model.display_title}")
        self._show_placeholder()

        # CHANGE [FEAT2]: match percentage stamped over the bottom of the
        # portrait. Parented to the cover so it overlays the artwork, and
        # omitted entirely when there is no score to show.
        self.match_badge = None
        if should_show_badge(model):
            self.match_badge = MatchBadge(model.personal_match, self.cover_label)
            self._position_badge()

        self.match_label = self._label(model.personal_match_text, "personalMatchLabel")
        # CHANGE [FEAT2]: do not print the score twice. The bar across the
        # portrait already states it, so this line only repeated it in words
        # and cost a row of vertical space on every card. It stays as the
        # fallback for a recommendation that carries no score at all, where
        # there is no bar to read it from, and it keeps its text either way so
        # nothing that reports the card's contents loses the figure.
        self.match_label.setVisible(self.match_badge is None)
        self.title_label = self._label(model.display_title, "recommendationTitle")
        self.title_label.setWordWrap(True)
        # CHANGE [BUG7]: these two run past the card edge on long values and
        # were being cut off mid-word with no ellipsis.
        self.secondary_title_label = self._label(
            model.secondary_title or "", "recommendationSecondaryTitle", eliding=True
        )
        # CHANGE [BUG7]: keep the line even when there is no English title.
        # Hiding it removed a row of height from that card alone, so every
        # element below it sat higher than on its neighbours and nothing in
        # the grid lined up across a row. An empty label still reserves one
        # line, which is exactly the reservation needed.
        self.secondary_title_label.setVisible(True)
        self.mal_score_label = self._label(
            model.mal_score_text, "malScoreLabel", eliding=True
        )
        self.meta_label = self._label(
            f"{model.year_text} · {model.status} · {model.episodes_text}",
            "recommendationMeta",
        )
        self.meta_label.setWordWrap(True)
        self.genres_label = self._label(model.genres_text, "recommendationGenres")
        self.genres_label.setWordWrap(True)
        self.reason_label = self._label(model.reason, "recommendationReason")
        self.reason_label.setWordWrap(True)
        # CHANGE [BUG7]: fixed line budgets for every label that wraps.
        #
        # This is what actually makes the grid a grid. Equalising the outer
        # card height only squares off the boxes; inside them a title that
        # wrapped to two lines, or a fourth genre, still pushed everything
        # below it down, so no two cards agreed on where the buttons sat. With
        # each wrapped label reserving a set number of lines, every card has
        # the same natural height and there is no slack left to distribute.
        self._reserve_lines(self.title_label, TITLE_LINES)
        # An empty secondary title does not measure the same as a filled one,
        # so reserve its line explicitly rather than trusting the sizeHint.
        self._reserve_lines(self.secondary_title_label, SECONDARY_TITLE_LINES)
        self._reserve_lines(self.meta_label, META_LINES)
        self._reserve_lines(self.genres_label, GENRE_LINES)
        self._reserve_lines(self.reason_label, REASON_LINES)
        # CHANGE [BUG7]: the single-line labels were cut off mid-word at the
        # card edge with no ellipsis, which reads as text running into the
        # border rather than as text that continues elsewhere.
        self.like_button = QPushButton("Like")
        self.like_button.setObjectName("recommendationLikeButton")
        self.like_button.setProperty("feedback", "liked")
        self.like_button.setCheckable(True)
        self.like_button.clicked.connect(lambda: self.liked_requested.emit(self.model))
        self.dislike_button = QPushButton("Not for me")
        self.dislike_button.setObjectName("recommendationDislikeButton")
        self.dislike_button.setProperty("feedback", "disliked")
        self.dislike_button.setCheckable(True)
        self.dislike_button.clicked.connect(
            lambda: self.disliked_requested.emit(self.model)
        )
        # CHANGE [BUG2]: shorter labels. At 75% GUI scale the card is 168px
        # wide and the previous wording clipped mid-word ("iew Detail").
        self.details_button = QPushButton("Details")
        self.details_button.setProperty("buttonRole", "secondary")
        self.details_button.setAccessibleName("View full details for this anime")
        self.details_button.clicked.connect(lambda: self.details_requested.emit(self.model))
        self.hide_button = QPushButton("Hide")
        self.hide_button.setObjectName("recommendationHideButton")
        self.hide_button.clicked.connect(lambda: self.hide_requested.emit(self.model))
        self.watch_later_button = QPushButton("Later")
        self.watch_later_button.setObjectName("recommendationWatchLaterButton")
        self.watch_later_button.setProperty("savedAction", True)
        self.watch_later_button.setAccessibleName("Save this anime to Watch Later")
        self.watch_later_button.setCheckable(True)
        self.watch_later_button.clicked.connect(
            lambda: self.watch_later_requested.emit(self.model)
        )
        self.mal_button = QPushButton("MyAnimeList")
        self.mal_button.setProperty("buttonRole", "link")
        self.mal_button.setAccessibleName("Open this anime on MyAnimeList")
        self.mal_button.setEnabled(bool(model.mal_url))
        self.mal_button.clicked.connect(
            lambda: open_mal_url(self.model.mal_url, opener=self._mal_opener)
        )
        # Identity first, then the decision, then the supporting detail.
        #
        # A 2:3 poster plus six buttons cannot fit the default window: a whole
        # card measures around 565px against roughly 448px of visible feed, and
        # shrinking the cover far enough to close that gap would leave artwork
        # too small to recognise. So the ordering decides what falls below the
        # fold. Reviewing a pick is the core loop, so Like and Not for me sit
        # directly under the title where the eye already is, and the metadata
        # a user reads only when undecided moves beneath them.
        # CHANGE [BUG2]: the cover is narrower than the card, and adding it
        # without an alignment left it against the left margin. Centre it.
        layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)
        for widget in (
            self.match_label,
            self.title_label,
            self.secondary_title_label,
        ):
            layout.addWidget(widget)
        # CHANGE [BUG7]: the gaps inside these rows were raw pixels that
        # stayed put while everything around them grew with the GUI scale.
        feedback_row = QHBoxLayout()
        feedback_row.setSpacing(scaled(SPACE['sm']))
        feedback_row.addWidget(self.like_button, 1)
        feedback_row.addWidget(self.dislike_button, 1)
        layout.addLayout(feedback_row)
        for widget in (
            self.mal_score_label,
            self.meta_label,
            self.genres_label,
            self.reason_label,
        ):
            layout.addWidget(widget)
        # CHANGE [BUG7]: collect the slack from equalised heights in one
        # place. Without this Qt shares the extra pixels out between the
        # stretchable labels, so identical cards still disagreed about where
        # each line sat. Pooling it here pins the action rows to the bottom of
        # every card and lets the text above align from the top.
        layout.addStretch(1)
        action_row = QHBoxLayout()
        action_row.setSpacing(scaled(SPACE['sm']))
        action_row.addWidget(self.details_button, 1)
        action_row.addWidget(self.watch_later_button, 1)
        layout.addLayout(action_row)
        utility_row = QHBoxLayout()
        utility_row.setSpacing(scaled(SPACE['xs']))
        utility_row.addWidget(self.mal_button, 1)
        utility_row.addWidget(self.hide_button)
        layout.addLayout(utility_row)

    def apply_scale(self) -> None:
        """Re-apply every fixed dimension for the current GUI scale.

        CHANGE [BUG2]: cards are reused rather than rebuilt, which is what
        keeps a vote from tearing down the feed. The cost is that a size fixed
        at construction never changes on its own, so a scale change left every
        card at whatever size it was first built with. Re-applying here means
        both properties hold: no teardown, and the card still resizes.
        """
        self.setFixedWidth(scaled(CARD_WIDTH))
        self.cover_label.setFixedSize(scaled(COVER_WIDTH), scaled(COVER_HEIGHT))
        layout = self.layout()
        if layout is not None:
            # CHANGE [BUG7]: these had drifted from the values used when the
            # card is built, so a scale change quietly restored the cramped
            # spacing the constructor no longer uses.
            layout.setContentsMargins(
                scaled(SPACE["md"]), scaled(SPACE["sm"]),
                scaled(SPACE["md"]), scaled(SPACE["md"]),
            )
            layout.setSpacing(scaled(SPACE["sm"]))
        # CHANGE [BUG7]: the line budgets are in font pixels, so they have to
        # be measured again whenever the scale, and with it the font, changes.
        self._reserve_lines(self.title_label, TITLE_LINES)
        # An empty secondary title does not measure the same as a filled one,
        # so reserve its line explicitly rather than trusting the sizeHint.
        self._reserve_lines(self.secondary_title_label, SECONDARY_TITLE_LINES)
        self._reserve_lines(self.meta_label, META_LINES)
        self._reserve_lines(self.genres_label, GENRE_LINES)
        self._reserve_lines(self.reason_label, REASON_LINES)
        self._rescale_cover()
        self._position_badge()

    def _position_badge(self) -> None:
        """CHANGE [FEAT2]: span the portrait's lower edge, inset from the corners."""
        if self.match_badge is None:
            return
        self.match_badge.apply_scale()
        cover = self.cover_label
        badge = self.match_badge
        inset = scaled(BAR_SIDE_INSET)
        badge.setFixedWidth(max(1, cover.width() - inset * 2))
        badge.move(
            inset,
            cover.height() - badge.height() - scaled(BADGE_BOTTOM_INSET),
        )
        badge.raise_()

    def set_badge_colours(self, track, fill, text) -> None:
        """CHANGE [FEAT2]: let the theme decide the bar's colours."""
        if self.match_badge is not None:
            self.match_badge.set_colours(track, fill, text)

    @staticmethod
    def _reserve_lines(label: QLabel, lines: int) -> None:
        """Pin a wrapped label to a fixed number of lines.

        The single-line height is measured rather than computed, because the
        stylesheet contributes padding that varies by object name and is not
        knowable here. Measuring it with a one-character string and adding
        whole line spacings for the rest keeps it correct under any font or
        GUI scale.
        """
        # Clear any previous reservation first: sizeHint on a widget with a
        # fixed height reports that height, so re-measuring without this would
        # simply return the old value and the labels would never rescale.
        label.setMinimumHeight(0)
        label.setMaximumHeight(16777215)
        original = label.text()
        label.setText("X")
        single = label.sizeHint().height()
        label.setText(original)
        height = single + max(0, lines - 1) * label.fontMetrics().lineSpacing()
        label.setFixedHeight(height)

    def _label(
        self, text: str, object_name: str, *, eliding: bool = False
    ) -> QLabel:
        """CHANGE [BUG1]: parent the label to the card at creation.

        A QWidget with no parent *is* a top-level window. These labels were
        created parentless and only adopted later by the layout, so any
        setVisible(True) in between, such as the one for the secondary title,
        made Qt open a real window: a blank frame with its own title bar that
        vanished the moment the layout took the widget. That is the flashing
        the user reported on almost every interaction, because a card is built
        for every title whose English name differs from its romaji one.

        Parenting on creation costs nothing, the layout reparents to the same
        widget anyway, and it makes the ordering irrelevant.
        """
        label = ElidingLabel(text, self) if eliding else QLabel(text, self)
        label.setObjectName(object_name)
        if eliding and text:
            # The full string stays reachable for anyone who wants it.
            label.setToolTip(text)
        # CHANGE [BUG7]: natural height only. A label left free to grow soaks
        # up part of the equalisation slack, which is what made otherwise
        # identical cards disagree about where each row sat.
        label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        return label

    def request_cover(self) -> None:
        if not self.model.cover_url:
            return
        cached = MEMORY_COVER_CACHE.get(self.model.cover_url)
        if cached is not None:
            self.cover_label.setPixmap(cached)
            return
        self.cover_requested.emit(self.model.cover_url)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def set_local_state(
        self,
        *,
        hidden: bool,
        watch_later: bool,
        actions_enabled: bool,
        liked: bool = False,
        disliked: bool = False,
    ) -> None:
        self.hide_button.setText("Unhide" if hidden else "Hide")
        self.watch_later_button.setText(
            "Saved" if watch_later else "Later"
        )
        self.watch_later_button.setChecked(watch_later)
        self.like_button.setChecked(liked)
        self.dislike_button.setChecked(disliked)
        self.like_button.setText(
            "Remove like" if liked else "Move to Liked" if disliked else "Like"
        )
        self.dislike_button.setText(
            "Remove dislike"
            if disliked
            else "Move to Disliked"
            if liked
            else "Not for me"
        )
        taste_state = "liked" if liked else "disliked" if disliked else "unreviewed"
        self.setProperty("tasteState", taste_state)
        self.style().unpolish(self)
        self.style().polish(self)
        self.hide_button.setEnabled(actions_enabled)
        self.watch_later_button.setEnabled(actions_enabled)
        self.like_button.setEnabled(actions_enabled)
        self.dislike_button.setEnabled(actions_enabled)
        reason = "Connect or select a profile to manage local recommendation lists."
        self.hide_button.setToolTip("" if actions_enabled else reason)
        self.watch_later_button.setToolTip("" if actions_enabled else reason)
        self.like_button.setToolTip(
            (
                "Remove this like and return the anime to For You."
                if liked
                else "Move this anime to Liked and update the taste model."
            )
            if actions_enabled
            else reason
        )
        self.dislike_button.setToolTip(
            (
                "Remove this dislike and return the anime to For You."
                if disliked
                else "Move this anime to Disliked and update the taste model."
            )
            if actions_enabled
            else reason
        )

    def set_cover_visible(self, visible: bool) -> None:
        self.cover_label.setVisible(visible)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.selection_requested.emit(self.model)
        super().mousePressEvent(event)

    def focusInEvent(self, event: QFocusEvent) -> None:
        self.selection_requested.emit(self.model)
        super().focusInEvent(event)

    def set_cover_data(self, data: bytes) -> bool:
        source = QPixmap()
        if not source.loadFromData(data):
            self._show_placeholder()
            return False
        # CHANGE [BUG6]: keep the artwork at full resolution. The downscaled
        # copy used to be what was cached, so every later resize enlarged an
        # already shrunken image and the portraits looked soft. The original is
        # cached and each display size is derived from it.
        self._source_cover = source
        self.cover_label.setPixmap(_fit_cover(source))
        if self.model.cover_url:
            MEMORY_COVER_CACHE.put(self.model.cover_url, source)
        return True

    def _show_placeholder(self) -> None:
        source = cover_placeholder_pixmap()
        if source.isNull():
            source = QPixmap(scaled(COVER_WIDTH), scaled(COVER_HEIGHT))
            source.fill(Qt.GlobalColor.transparent)
        self._source_cover = source
        self.cover_label.setPixmap(_fit_cover(source))

    def _rescale_cover(self) -> None:
        """CHANGE [BUG6]: re-fit from the original after a scale change."""
        source = getattr(self, "_source_cover", None)
        if source is None or source.isNull():
            self._show_placeholder()
            return
        self.cover_label.setPixmap(_fit_cover(source))


def _fit_cover(source: QPixmap) -> QPixmap:
    # CHANGE [BUG6]: fit to the size actually on screen. This used to fit to the
    # unscaled constants, so at 150% a 176x264 image was stretched into a
    # 264x396 label and looked blurry.
    # CHANGE [BUG7]: rounded, because a stylesheet radius does not clip a
    # QLabel's pixmap and every portrait stayed a hard rectangle.
    return rounded_cover(
        source,
        scaled(COVER_WIDTH),
        scaled(COVER_HEIGHT),
        scaled(COVER_RADIUS),
    )
