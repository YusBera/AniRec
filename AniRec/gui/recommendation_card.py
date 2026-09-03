"""Addresses: BUG2 (DPI and GUI scale, portrait centring), FEAT2 (match badge).

Every hand-chosen pixel dimension here goes through ``scaled()`` so the whole
card grows and shrinks with the GUI Scale setting. Qt stylesheets have no
relative units to use instead.
Reference-aligned recommendation card with safe cover and MAL actions.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable

from PySide6.QtCore import QEvent, QRect, Qt, QUrl, Signal
from PySide6.QtGui import (
    QDesktopServices,
    QFocusEvent,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPixmap,
    QTextLayout,
)
from PySide6.QtWidgets import (
    QFrame,
    QStyle,
    QStyleOption,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .cover_art import CoverLabel, rounded_cover
from .discover_filters import FilterKind
from .instrument_widgets import keep_crisp
from .metadata_tags import MetadataTagStrip
from .design_tokens import RADIUS, SPACE
from .match_badge import (
    BADGE_BOTTOM_INSET,
    BAR_SIDE_INSET,
    MatchBadge,
    should_show_badge,
)
from .scaling import scaled
from .recommendation_view_model import RecommendationViewModel
from .resources import (
    cover_placeholder_pixmap,
    themed_ui_icon,
    title_placeholder_pixmap,
)


CARD_WIDTH = 208

# Cards fill the row rather than sitting at one pinned width with the
# leftover space dumped past the last column. CARD_WIDTH is the minimum a
# card may shrink to; the cap stops a half-empty final row from stretching
# two cards across the whole feed.
CARD_MAX_WIDTH = 300

# Square side of the icon-only card actions.
# CHANGE [TARGET-SIZE]: WCAG 2.1 AA (2.5.8) puts the floor for a pointer
# target at 24x24 CSS pixels. At 26 these cleared it only on the axis that
# was pinned, and only before the GUI scale went below 1.0 - three unlabelled
# glyph controls, side by side, at the smallest size in the interface. 32
# leaves margin on both axes at every scale the settings offer.
ICON_ACTION_SIZE = 32
# A 2:3 poster, the standard shape for anime cover art. Sized so that a whole
# card, including the review actions, fits the default window without
# scrolling; at the previous size the buttons sat below the fold.
# 2:3 exactly (172*3 == 258*2). Trimmed a little from 176x264 to buy back the
# height the extra spacing cost, so the review loop still fits the default
# window with room to spare.
# CHANGE [BIGGER-ART]: 132 -> 152, which is 228 * 2/3. Anime cover art is
# 2:3 and these two constants have to move together; raising the height
# alone would squash every poster, which is the mistake the note below the
# height was written to prevent.
COVER_WIDTH = 152
# Trimmed from 156x234. The portrait was tall enough to push the reason
# line and the whole action row past the bottom of the feed at the minimum
# window size. Both dimensions come down together: anime cover art is 2:3,
# and shrinking only the height would have squashed every poster.
# CHANGE [BIGGER-ART]: 198 -> 228. The portrait had been trimmed twice to
# buy vertical room for a two-row action block; consolidating those rows
# gives the room back, and it belongs to the artwork. Cover art is the
# highest-information element on a card and was the smallest thing competing
# for the space.
COVER_HEIGHT = 228
# CHANGE [ASPECT]: the height is the constant; the width follows the artwork.
#
# A fixed 2:3 frame has to do something with a cover that is not 2:3, and both
# answers were wrong: crop it and the top of a title lockup goes, contain it
# and there are bands down the sides. Anime key art is not one shape - it runs
# roughly 0.64 to 0.71 wide-over-tall - so at a fixed 198 height every real
# cover wants to be between 127 and 140 across. Letting it be exactly that
# means nothing is cropped and nothing is padded, and because the height never
# moves the grid rows still line up.
#
# The bounds below are wider than any cover MyAnimeList actually serves. They
# exist for the pathological source - a square promo, a wide banner - where
# the artwork is contained and the backdrop fills the remainder, which is the
# old behaviour kept as the exception rather than the rule.
# CHANGE [BIGGER-ART]: scaled with the height, 198 -> 228. Real key art runs
# roughly 0.64 to 0.71 wide-over-tall, so at 228 every genuine cover wants to
# be between 146 and 162 across; these bounds stay wider than that, for the
# pathological source the note above describes.
COVER_MIN_WIDTH = 124
COVER_MAX_WIDTH = 202

# Matches the card's own corner radius so the portrait sits inside it rather
# than cutting across it.
COVER_RADIUS = RADIUS["md"]


def cover_size_for(source) -> tuple[int, int]:
    """The frame this particular artwork should be shown in.

    Height is always ``COVER_HEIGHT``: it is what keeps every card the same
    height and every row of the grid aligned. Width is whatever that height
    implies for the source's own proportions, bounded so one odd image cannot
    stretch a card out of shape.
    """
    height = scaled(COVER_HEIGHT)
    default = scaled(COVER_WIDTH)
    if source is None or source.isNull() or source.height() <= 0:
        return default, height
    natural = round(height * source.width() / source.height())
    return max(scaled(COVER_MIN_WIDTH), min(scaled(COVER_MAX_WIDTH), natural)), height

# Line budgets for the wrapped labels. Generous enough that clipping is rare,
# and identical for every card so the rows line up across the grid.
TITLE_LINES = 2
SECONDARY_TITLE_LINES = 1
META_LINES = 2
# Three, not two: the genres are what the recommendation is about, and a
# title with five of them was being cut mid-list.
GENRE_LINES = 3
# Two is enough for the one sentence this holds at card width, and it
# buys the third genre line above.
REASON_LINES = 2


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
        # CHANGE [SCROLL-COST]: the elision is cached against the inputs that
        # decide it. Measured over one scroll of a 120-card feed this ran 520
        # times, re-measuring the same string at the same width on every
        # exposure - scrolling repaints a widget many times without changing
        # anything about it. Recomputed only when the text, the width or the
        # font actually differ.
        key = (self.text(), rect.width(), self.font().key())
        if getattr(self, "_elide_key", None) != key:
            self._elide_key = key
            self._elided = self.fontMetrics().elidedText(
                self.text(), Qt.TextElideMode.ElideRight, rect.width()
            )
        painter.setPen(self.palette().color(self.foregroundRole()))
        painter.drawText(rect, int(self.alignment()), self._elided)
        painter.end()


class ClampedLabel(QLabel):
    """A wrapped label whose overflow ends in an ellipsis, not mid-word.

    CHANGE [DEFECT-CLIP]: every wrapped label on the card is pinned to a line
    budget by ``_reserve_lines``, which is what makes the grid a grid. Qt
    honours that height by simply not painting the rest, so a reason that
    wrapped to three lines inside a two-line reservation lost its last line
    with no mark at all - measured at 24 lines of explanation dropped across
    a nine-card feed, every one of them cut mid-word. The reservation is
    right; the silence was the fault. This lays the text out exactly as Qt
    would, stops at the last line that fits, and elides that one, so a
    truncation always looks like a truncation.

    Like ``ElidingLabel`` it paints rather than rewriting ``text()``, so
    anything reading the card still sees the whole string, and it re-fits by
    itself after a resize, a font change or a GUI scale change.
    """

    def _line_budget(self, height: int) -> int:
        """How many lines the reserved height holds.

        Derived from the same arithmetic ``_reserve_lines`` used to produce
        that height - one full line plus a line spacing for every line after
        it - rather than dividing by the spacing, which miscounts whenever a
        font's height and its line spacing differ.
        """
        metrics = self.fontMetrics()
        spacing = metrics.lineSpacing()
        if spacing <= 0:
            return 1
        return 1 + max(0, round((height - metrics.height()) / spacing))

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
        text = self.text()
        if not text or rect.width() <= 0:
            painter.end()
            self.setToolTip("")
            return

        metrics = self.fontMetrics()
        spacing = metrics.lineSpacing()
        allowed = self._line_budget(rect.height())

        layout = QTextLayout(text, self.font())
        layout.beginLayout()
        lines = []
        while len(lines) < allowed:
            line = layout.createLine()
            if not line.isValid():
                break
            line.setLineWidth(rect.width())
            lines.append((line.textStart(), line.textLength()))
        layout.endLayout()
        if not lines:
            painter.end()
            self.setToolTip("")
            return

        consumed = lines[-1][0] + lines[-1][1]
        clipped = consumed < len(text)
        # A short string in a taller reservation stays where QLabel put it.
        alignment = self.alignment()
        top = rect.top()
        block = len(lines) * spacing
        if alignment & Qt.AlignmentFlag.AlignVCenter:
            top += max(0, (rect.height() - block) // 2)
        elif alignment & Qt.AlignmentFlag.AlignBottom:
            top += max(0, rect.height() - block)
        horizontal = alignment & Qt.AlignmentFlag.AlignHorizontal_Mask

        painter.setPen(self.palette().color(self.foregroundRole()))
        for index, (start, length) in enumerate(lines):
            chunk = text[start : start + length]
            if clipped and index == len(lines) - 1:
                # Elide from here to the end of the string rather than from
                # the part that fit: the ellipsis stands for everything the
                # reservation dropped, not just this line's remainder.
                chunk = metrics.elidedText(
                    text[start:], Qt.TextElideMode.ElideRight, rect.width()
                )
            painter.drawText(
                QRect(rect.left(), top + index * spacing, rect.width(), spacing),
                int(horizontal | Qt.AlignmentFlag.AlignVCenter),
                chunk.rstrip(),
            )
        painter.end()
        # The full sentence stays reachable, and only while it is really cut.
        self.setToolTip(text if clipped else "")


class RecommendationCard(QFrame):
    # CHANGE [FILTER]: the card reports what was clicked; it does not decide
    # what happens next. Filtering belongs to one state object shared by every
    # entry point, so a genre clicked here and the same genre chosen from the
    # search box are one value rather than two code paths that agree by
    # inspection.
    metadata_filter_requested = Signal(object, str)
    cover_requested = Signal(str)
    details_requested = Signal(object)
    selection_requested = Signal(object)
    not_interested_requested = Signal(object)
    watch_later_requested = Signal(object)

    def __init__(
        self,
        model: RecommendationViewModel,
        parent: QWidget | None = None,
        *,
        mal_opener: Callable[[QUrl], bool] = QDesktopServices.openUrl,
        comparison=None,
    ) -> None:
        super().__init__(parent)
        self.model = model
        self._mal_opener = mal_opener
        # CHANGE [COMPARE]: the comparison surface shows the same object -
        # a poster, a title, its metadata - plus two people's opinions of it.
        # That is a variant of this card, not a second card: writing a
        # lookalike would mean maintaining the cover fitting, the line
        # budgets, the eliding and the match plate in two places, and they
        # would drift the first time one of them changed.
        self.comparison = comparison
        self.setObjectName("recommendationCard")
        self.setProperty("recommendationCard", True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(f"Anime recommendation: {model.display_title}")
        # CHANGE [BUG2]: was a fixed 224px, so the card kept one size while the
        # logical window shrank at higher DPI and took a larger share of it.
        self.setMinimumWidth(scaled(CARD_WIDTH))
        self.setMaximumWidth(scaled(CARD_MAX_WIDTH))
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)

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
        self.cover_label = CoverLabel()
        self.cover_label.setObjectName("recommendationCover")
        # Artwork is never rastered; see keep_crisp.
        keep_crisp(self.cover_label)
        # CHANGE [BUG2]: scale the portrait with the rest of the card.
        # CHANGE [ASPECT]: re-derive from the artwork rather than pinning the
        # 2:3 default, which would have squeezed every non-2:3 cover back into
        # the old frame on any scale change.
        self.cover_label.setFixedSize(*cover_size_for(getattr(self, "_source_cover", None)))
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
        # CHANGE [COMPARE-BADGE]: never on a comparison card. "Personal
        # match" is a Discover quantity and the compatibility payload does
        # not carry one, so Recommendation coerced the missing value to 0.0
        # and every card under "Most different ratings" wore a red 0% plate -
        # a confident, meaningless number, in the one place on the surface
        # where the reader is being asked to trust a comparison. The card
        # already states the two scores that do mean something, in the strip
        # underneath.
        self.match_badge = None
        if self.comparison is None and should_show_badge(model):
            self.match_badge = MatchBadge(model.personal_match, self.cover_label)
            self._make_detail_target(self.match_badge)
            self.match_badge.set_contributions(
                getattr(model, "genre_contributions", ()),
                genres=getattr(model, "genres", ()),
                studios=getattr(model, "studios", ()),
            )
            # Hovering a block on the rail lights the tag that produced it.
            self.match_badge.contributor_hovered.connect(
                self._on_contributor_hovered
            )
            self._position_badge()

        self.match_label = self._label(model.personal_match_text, "personalMatchLabel")
        # CHANGE [FEAT2]: do not print the score twice. The bar across the
        # portrait already states it, so this line only repeated it in words
        # and cost a row of vertical space on every card. It stays as the
        # fallback for a recommendation that carries no score at all, where
        # there is no bar to read it from, and it keeps its text either way so
        # nothing that reports the card's contents loses the figure.
        self.match_label.setVisible(self.match_badge is None and self.comparison is None)
        self.title_label = self._label(
            model.display_title, "recommendationTitle", clamped=True
        )
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
            clamped=True,
        )
        self.meta_label.setWordWrap(True)
        # CHANGE [FILTER]: the genre line becomes a strip of real controls.
        # The label stays, hidden, because it is what the height reservation
        # is measured from and because anything reading the card's contents
        # still finds the whole list as text.
        self.genres_label = self._label(
            model.genres_text, "recommendationGenres", clamped=True
        )
        self.genres_label.setWordWrap(True)
        self.tag_strip = MetadataTagStrip(self)
        self.tag_strip.tag_activated.connect(self.metadata_filter_requested.emit)
        self.tag_strip.overflow_activated.connect(
            lambda _values: self.details_requested.emit(self.model)
        )
        self._apply_tags()
        self.reason_label = self._label(
            model.reason, "recommendationReason", clamped=True
        )
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
        # The strip takes exactly the height the genre line used to occupy, so
        # turning a sentence into controls costs the grid nothing.
        self.tag_strip.reserve_height(self.genres_label.height())
        self.genres_label.setVisible(False)
        # CHANGE [BUG7]: the single-line labels were cut off mid-word at the
        # card edge with no ellipsis, which reads as text running into the
        # border rather than as text that continues elsewhere.
        # CHANGE [NO-VERDICTS]: Like is gone and Dislike is now Not
        # interested. A card is read before the anime is watched, so the only
        # opinion available at this moment is about the pitch - the poster,
        # the title, the genres - and not about the show. Like asked for a
        # verdict nobody was in a position to give, then spent it as though
        # it were one, and nothing could ever take it back.
        #
        # What remains is the judgement a card can actually support: not
        # this, do not offer it again. It is a filter, not a rating, and it
        # says nothing to the taste model.
        self.not_interested_button = QPushButton("Not interested")
        self.not_interested_button.setObjectName("recommendationNotInterestedButton")
        self.not_interested_button.setProperty("feedback", "not-interested")
        self.not_interested_button.setCheckable(True)
        self.not_interested_button.clicked.connect(
            lambda: self.not_interested_requested.emit(self.model)
        )
        # CHANGE [BUG2]: shorter labels. At 75% GUI scale the card is 168px
        # wide and the previous wording clipped mid-word ("iew Detail").
        self.details_button = QPushButton("Details")
        self.details_button.setProperty("buttonRole", "ghost")
        self.details_button.setAccessibleName("View full details for this anime")
        self.details_button.clicked.connect(lambda: self.details_requested.emit(self.model))
        # CHANGE [NO-VERDICTS]: the separate Hide control is gone. It
        # excluded a title from future recommendations, which is precisely
        # what Not interested now says out loud, and two controls that do the
        # same thing on one small card is worse than one that says what it
        # means.
        self._hidden_state = False
        self.watch_later_button = QPushButton("Later")
        self.watch_later_button.setObjectName("recommendationWatchLaterButton")
        self.watch_later_button.setProperty("savedAction", True)
        self.watch_later_button.setAccessibleName("Save this anime to Watch Later")
        self.watch_later_button.setCheckable(True)
        self.watch_later_button.clicked.connect(
            lambda: self.watch_later_requested.emit(self.model)
        )
        self.mal_button = QPushButton("MyAnimeList")
        self.mal_button.setProperty("buttonRole", "ghost")
        self.mal_button.setAccessibleName("Open this anime on MyAnimeList")
        self.mal_button.setEnabled(bool(model.mal_url))
        self.mal_button.clicked.connect(
            lambda: open_mal_url(self.model.mal_url, opener=self._mal_opener)
        )
        # Identity first, then the decision, then the supporting detail.
        #
        # A 2:3 poster plus the buttons cannot fit the default window: a whole
        # card measures around 565px against roughly 448px of visible feed, and
        # shrinking the cover far enough to close that gap would leave artwork
        # too small to recognise. So the ordering decides what falls below the
        # fold. Deciding on a pick is the core loop, so Watch Later and Not
        # interested sit directly under the title where the eye already is,
        # and the metadata a user reads only when undecided moves beneath
        # them.
        # CHANGE [BUG2]: the cover is narrower than the card, and adding it
        # without an alignment left it against the left margin. Centre it.
        layout.addWidget(self.cover_label, 0, Qt.AlignmentFlag.AlignHCenter)
        self._make_detail_target(self.cover_label)
        self._make_detail_target(self.title_label)
        for widget in (
            self.match_label,
            self.title_label,
            self.secondary_title_label,
        ):
            layout.addWidget(widget)
        # CHANGE [BUG7]: the gaps inside these rows were raw pixels that
        # stayed put while everything around them grew with the GUI scale.
        # CHANGE [ALIGNMENT]: the six actions were three independent rows,
        # each dividing the width by its own labels' minimum widths. Measured
        # on one card that gave splits of 79/95, 87/87 and 132/46 - three
        # different column edges stacked on top of each other. They share one
        # two-column grid now, with buttons allowed to shrink below their text
        # width, so every edge lines up whatever the labels say.
        feedback_row = QGridLayout()
        feedback_row.setContentsMargins(0, 0, 0, 0)
        feedback_row.setHorizontalSpacing(scaled(SPACE['sm']))
        feedback_row.setColumnStretch(0, 1)
        feedback_row.setColumnStretch(1, 1)
        # CHANGE [ACTION-ROW]: Watch Later belongs beside the other decision,
        # not two rows below it with unrelated controls in between - which is
        # where the likelier of the two used to sit. They read left to right
        # in the order somebody actually reaches them.
        # CHANGE [ICON-VERDICTS]: glyphs, not words. "Watch Later" needs 63px
        # of text and the row gave about 62px at the widest card and 32px at
        # the narrowest, so the label could not fit at any size - it was
        # shipping as "Later", the one abbreviation here that damages the
        # meaning of what it labels.
        #
        # CHANGE [NO-VERDICTS]: two controls, not three. With Like gone the
        # row is no longer a verdict at all - it is "keep this" and "stop
        # showing me this", which is the whole of what a reader can decide
        # from a card. Each still carries its own colour, a real accessible
        # name and a tooltip, and the checked state still swaps to the filled
        # variant of the glyph so state never rests on colour alone.
        for column, button, icon, tip in (
            (0, self.watch_later_button, "watch-later", "Save for later"),
            (1, self.not_interested_button, "not-interested", "Not interested"),
        ):
            self._make_grid_cell(button)
            button.setProperty("verdictIcon", icon)
            button.setText("")
            button.setToolTip(tip)
            if not button.accessibleName():
                button.setAccessibleName(tip)
            feedback_row.addWidget(button, 0, column)
        self._refresh_verdict_icons()
        layout.addLayout(feedback_row)
        # CHANGE [HIERARCHY]: the MyAnimeList score sat above the genres at
        # the same size, so a third party's average outranked the thing the
        # recommendation is actually about. Genres lead now; the external
        # score joins the other metadata below them.
        for widget in (
            self.tag_strip,
            self.meta_label,
            self.mal_score_label,
            self.reason_label,
        ):
            layout.addWidget(widget)
        # CHANGE [COMPARE]: two people's scores, in the readout vocabulary the
        # rail and the score bench already use, and only on a card that has
        # them. A feed card is not given an empty comparison row.
        self.comparison_strip = self._build_comparison_strip()
        if self.comparison_strip is not None:
            layout.addWidget(self.comparison_strip)
        # CHANGE [BUG7]: collect the slack from equalised heights in one
        # place. Without this Qt shares the extra pixels out between the
        # stretchable labels, so identical cards still disagreed about where
        # each line sat. Pooling it here pins the action rows to the bottom of
        # every card and lets the text above align from the top.
        layout.addStretch(1)
        # CHANGE [ACTIONS]: Details, MyAnimeList and Hide are square icon
        # controls rather than three more labelled boxes. They are the
        # utilities, not the verdicts: the row above is what the card is
        # asking, this row is what else you can do about it.
        #
        # CHANGE [ACTION-ROW]: Watch Later has left this row for the verdicts
        # above, so the three glyphs are pushed to the trailing edge instead
        # of hanging off the left where a label used to anchor them.
        utility_row = QHBoxLayout()
        utility_row.setContentsMargins(0, 0, 0, 0)
        utility_row.setSpacing(scaled(SPACE['xs']))
        utility_row.addStretch(1)
        for button, icon, tip in (
            (self.details_button, "details-inspector", "Open the full breakdown"),
            (self.mal_button, "external-mal", "Open on MyAnimeList"),
        ):
            button.setText("")
            button.setIcon(themed_ui_icon(icon))
            button.setToolTip(tip)
            # A tooltip is not an accessible name: it is not announced on
            # focus and never reaches a keyboard user. These three lost their
            # only label the moment setText("") stripped it, so the name is
            # restated here from the same sentence the tooltip carries.
            if not button.accessibleName():
                button.setAccessibleName(tip)
            # Width is pinned, height is not: the stylesheet's min-height
            # wins over setFixedSize, so pinning both left these 10px shorter
            # than the labelled button beside them and vertically centred
            # against it - four controls on one row at two different heights.
            button.setFixedWidth(scaled(ICON_ACTION_SIZE))
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
            utility_row.addWidget(button)
        layout.addLayout(utility_row)

    def _on_contributor_hovered(self, name: str) -> None:
        """Link the rail to the tag strip.

        The rail says how much each term contributed; the strip says which
        terms exist. Neither says which block is which, and a colour key
        would need a legend the card has no room for. Lighting the tag while
        its block is under the pointer answers it without adding anything to
        the resting state.
        """
        strip = getattr(self, "tag_strip", None)
        if strip is not None:
            strip.highlight(name)

    def _apply_tags(self) -> None:
        """Fill the strip: the studio first, then the genres.

        Studio leads because it is the stronger handle. "Another one by Kyoto
        Animation" narrows a catalogue far further than "another drama", and
        putting it first means it survives the narrow card, where it is the
        tail of a long genre list that collapses into the counter.

        Only the first studio is offered. Co-productions list three or four
        and none of them is the answer to "who made this"; the rest stay
        reachable in the breakdown.
        """
        values = []
        studios = getattr(self.model, "studios", ()) or ()
        if studios:
            values.append((FilterKind.STUDIO, studios[0]))
        values.extend((FilterKind.GENRE, genre) for genre in self.model.genres)
        self.tag_strip.set_values(values)

    def _build_comparison_strip(self) -> QWidget | None:
        """The two scores and the gap, or nothing at all.

        Four fields in the machine face on one line: yours, theirs, the
        difference, and what everyone else thinks. Deliberately not a pair of
        coloured deltas - a red and a green number beside each other is a
        price ticker, and this is two people disagreeing about a cartoon. The
        gap carries a band ("close", "apart", "opposed") that the stylesheet
        renders as a border tone, so the strength of a disagreement is visible
        without the interface shouting about it.
        """
        scores = self.comparison
        if scores is None:
            return None
        strip = QFrame(self)
        strip.setObjectName("comparisonScoreStrip")
        strip.setProperty("agreement", scores.agreement)
        row = QHBoxLayout(strip)
        row.setContentsMargins(
            scaled(SPACE["sm"]), scaled(SPACE["xs"]),
            scaled(SPACE["sm"]), scaled(SPACE["xs"]),
        )
        row.setSpacing(scaled(SPACE["sm"]))
        self.comparison_fields: dict[str, QLabel] = {}
        fields = (
            ("YOU", scores.your_score_text, "Your score"),
            ("THEM", scores.friend_score_text, "Their score"),
            ("GAP", scores.difference_text, "Difference between the two scores"),
            ("MAL", scores.mal_score_text, "MyAnimeList community score"),
        )
        for index, (caption, value, description) in enumerate(fields):
            if index:
                divider = QFrame(strip)
                divider.setObjectName("stripDivider")
                divider.setFixedWidth(1)
                divider.setFixedHeight(scaled(12))
                row.addWidget(divider)
            cell = QVBoxLayout()
            cell.setContentsMargins(0, 0, 0, 0)
            cell.setSpacing(0)
            caption_label = QLabel(caption, strip)
            caption_label.setObjectName("comparisonScoreCaption")
            value_label = QLabel(value, strip)
            value_label.setObjectName("comparisonScoreValue")
            value_label.setProperty("field", caption.casefold())
            # The caption is two or three letters; the sentence a screen
            # reader needs is not, and it is not the reader's job to expand
            # "GAP" into what it means.
            value_label.setAccessibleName(f"{description}: {value}")
            cell.addWidget(caption_label)
            cell.addWidget(value_label)
            row.addLayout(cell)
            self.comparison_fields[caption.casefold()] = value_label
        row.addStretch(1)
        return strip

    def apply_scale(self) -> None:
        """Re-apply every fixed dimension for the current GUI scale.

        CHANGE [BUG2]: cards are reused rather than rebuilt, which is what
        keeps a vote from tearing down the feed. The cost is that a size fixed
        at construction never changes on its own, so a scale change left every
        card at whatever size it was first built with. Re-applying here means
        both properties hold: no teardown, and the card still resizes.
        """
        self.setMinimumWidth(scaled(CARD_WIDTH))
        self.setMaximumWidth(scaled(CARD_MAX_WIDTH))
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
        self.tag_strip.reserve_height(self.genres_label.height())
        self._rescale_cover()
        self._position_badge()

    def _position_badge(self) -> None:
        """CHANGE [FEAT2]: span the portrait's lower edge, inset from the corners."""
        # CHANGE [ASPECT]: tolerant of being called before the badge exists.
        # The cover is sized and shown from __init__, which now positions the
        # plate as part of that - and at construction the placeholder is drawn
        # before the badge has been built. It is positioned explicitly once it
        # has been, so there is nothing to do here yet.
        badge = getattr(self, "match_badge", None)
        if badge is None:
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

    def set_badge_colours(self, track, fill, text, signal=None) -> None:
        """CHANGE [FEAT2]: let the theme decide the bar's colours."""
        if self.match_badge is not None:
            self.match_badge.set_colours(track, fill, text, signal)

    @staticmethod
    def _make_grid_cell(button: QPushButton) -> None:
        """Let the grid decide a button's width, not its label.

        Qt honours a push button's text-derived minimum width even under an
        equal stretch, which is what made three rows of paired actions settle
        on three different column edges.
        """
        button.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        button.setMinimumWidth(0)

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
        # Top-align inside the reservation. Qt centres by default, so a
        # one-line title in a box reserved for two sat half a line lower than
        # a two-line title beside it - the boxes aligned perfectly and the
        # words in them did not.
        label.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop
        )

    def _label(
        self,
        text: str,
        object_name: str,
        *,
        eliding: bool = False,
        clamped: bool = False,
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
        if eliding:
            label = ElidingLabel(text, self)
        elif clamped:
            label = ClampedLabel(text, self)
        else:
            label = QLabel(text, self)
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
            # CHANGE [CROP]: fit the cached image, do not hand it straight to
            # the label.
            #
            # What the cache holds is the *original* - full resolution, by
            # design, so that a scale change can re-fit from it rather than
            # enlarging an already-shrunken copy. This path set that original
            # as the label's pixmap directly. The label is a fixed 132x198
            # with no scaledContents, so Qt drew a 450x700 image at full size
            # and clipped it to the label: a centre crop, which is why the top
            # of the title lockup and both edges were missing. It also lost
            # the rounded corners, and left ``_source_cover`` unset, so a
            # later scale change fell back to the placeholder.
            #
            # Only the card had this. The list row already routes its cached
            # hit through the same fit as a fresh one, which is why the crop
            # showed in the grid and not in the list.
            self._source_cover = cached
            self._show_cover(cached)
            return
        self.cover_requested.emit(self.model.cover_url)

    # Which palette role each control is drawn in. Not interested keeps the
    # danger colour because it is the one action here that changes what the
    # feed will offer again; Watch Later stays neutral, since "keep this for
    # now" decides nothing and should not compete with it.
    _VERDICT_ROLES = {
        "not-interested": "resolvedDanger",
        "watch-later": "resolvedTextSubtle",
    }


    def _refresh_verdict_icons(self) -> None:
        """Draw each verdict in its own colour, filled when it is the answer.

        The checked state swaps to the ``-active`` variant of the same glyph,
        so which one is chosen does not rest on colour alone - the shape
        changes too, which is what makes it readable without colour vision.
        """
        for button in (self.watch_later_button, self.not_interested_button):
            name = button.property("verdictIcon")
            if not name:
                continue
            role = self._VERDICT_ROLES.get(name, "resolvedTextSubtle")
            variant = f"{name}-active" if button.isChecked() else name
            button.setIcon(themed_ui_icon(variant, role))
            button.setToolTip(button.accessibleName())

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
    ) -> None:
        # CHANGE [NO-VERDICTS]: "hidden" and "not interested" are one state
        # now, so the button reports it directly instead of a second control
        # shadowing it.
        self._hidden_state = bool(hidden)
        self.watch_later_button.setChecked(watch_later)
        self.not_interested_button.setChecked(self._hidden_state)
        # CHANGE [ICON-VERDICTS]: what the labels used to say now lives in the
        # accessible name, which is the only place a glyph can carry it. These
        # are the strings a screen reader reads and the tooltip shows, so the
        # state a word used to spell out is still stated, just not drawn.
        self.watch_later_button.setAccessibleName(
            "Remove from Watch Later" if watch_later else "Save for later"
        )
        self.not_interested_button.setAccessibleName(
            "Show this recommendation again"
            if self._hidden_state
            else "Not interested"
        )
        self._refresh_verdict_icons()
        self.setProperty(
            "tasteState", "not-interested" if self._hidden_state else "unreviewed"
        )
        self.style().unpolish(self)
        self.style().polish(self)
        self.watch_later_button.setEnabled(actions_enabled)
        self.not_interested_button.setEnabled(actions_enabled)
        reason = "Connect or select a profile to manage local recommendation lists."
        self.watch_later_button.setToolTip("" if actions_enabled else reason)
        self.not_interested_button.setToolTip(
            (
                "Show this anime in For You again."
                if self._hidden_state
                else "Stop recommending this anime. It stays in Not interested."
            )
            if actions_enabled
            else reason
        )

    def set_cover_visible(self, visible: bool) -> None:
        self.cover_label.setVisible(visible)

    def set_actions_visible(self, visible: bool) -> None:
        """Show or hide every control on the card.

        CHANGE [BUNDLE]: inside an opened series bundle the entries are the
        evidence and the bundle's own panel is where anything gets decided.
        Repeating the actions on five entry cards fills one panel with
        controls and leaves the eye nowhere to rest.

        The card is reused rather than a second, simpler card being written
        for the purpose: the cover fitting, the match plate, the line budgets
        and the eliding all took work to get right, and a lookalike would
        drift away from them the first time one of them changed.
        """
        for button in (
            self.not_interested_button,
            self.watch_later_button,
            self.details_button,
            self.mal_button,
        ):
            button.setVisible(visible)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        self.selection_requested.emit(self.model)
        super().mousePressEvent(event)

    def eventFilter(self, watched, event) -> bool:
        """Open the breakdown from the parts of the card that look like it.

        The portrait, the title and the match plate are what a reader points
        at when they want to know more about a recommendation. Only the small
        Details button did anything, which left the three largest targets on
        the card inert.
        """
        if event.type() == QEvent.Type.MouseButtonRelease:
            button = getattr(event, "button", None)
            if button is None or button() == Qt.MouseButton.LeftButton:
                self.selection_requested.emit(self.model)
                self.details_requested.emit(self.model)
                return True
        return super().eventFilter(watched, event)

    def _make_detail_target(self, widget) -> None:
        """Route a passive widget's clicks into the breakdown."""
        widget.installEventFilter(self)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self.details_requested.emit(self.model)
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.details_requested.emit(self.model)
            return
        super().keyPressEvent(event)

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
        # A real arrival, so dissolve into it. Re-fits after a resize or a
        # scale change go through _show_cover without arming anything.
        self.cover_label.arm_fade()
        self._show_cover(source)
        if self.model.cover_url:
            MEMORY_COVER_CACHE.put(self.model.cover_url, source)
        return True

    def _show_cover(self, source: QPixmap) -> None:
        """Size the frame to this artwork, then fill it.

        CHANGE [ASPECT]: the label is re-sized per image, so the match plate -
        which spans the portrait and is parented to it - has to be placed
        again afterwards or it keeps the previous cover's width.
        """
        width, height = cover_size_for(source)
        if (self.cover_label.width(), self.cover_label.height()) != (width, height):
            self.cover_label.setFixedSize(width, height)
        self.cover_label.setPixmap(_fit_cover(source))
        self._position_badge()

    def _show_placeholder(self) -> None:
        # A plate carrying this title's own initials and hue, so a feed with
        # no artwork reads as eight distinct entries rather than as eight
        # copies of a missing image.
        # At the size it is drawn; see the note in recommendation_row.
        source = title_placeholder_pixmap(
            self.model.display_title,
            (scaled(COVER_WIDTH), scaled(COVER_HEIGHT)),
        )
        if source.isNull():
            source = cover_placeholder_pixmap()
        if source.isNull():
            source = QPixmap(scaled(COVER_WIDTH), scaled(COVER_HEIGHT))
            source.fill(Qt.GlobalColor.transparent)
        self._source_cover = source
        self.cover_label.mark_placeholder()
        self._show_cover(source)

    def _rescale_cover(self) -> None:
        """CHANGE [BUG6]: re-fit from the original after a scale change."""
        source = getattr(self, "_source_cover", None)
        if source is None or source.isNull():
            self._show_placeholder()
            return
        self._show_cover(source)


def _fit_cover(source: QPixmap) -> QPixmap:
    # CHANGE [BUG6]: fit to the size actually on screen. This used to fit to the
    # unscaled constants, so at 150% a 176x264 image was stretched into a
    # 264x396 label and looked blurry.
    # CHANGE [BUG7]: rounded, because a stylesheet radius does not clip a
    # QLabel's pixmap and every portrait stayed a hard rectangle.
    # CHANGE [ASPECT]: the frame is derived from the artwork rather than fixed,
    # so for anything in the range covers actually ship in there is nothing
    # left for rounded_cover to pad or trim.
    width, height = cover_size_for(source)
    return rounded_cover(source, width, height, scaled(COVER_RADIUS))
