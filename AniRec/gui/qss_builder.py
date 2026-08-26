"""Render the application stylesheet from design tokens.

There is one template. Both themes are produced from it against different
colour maps, which is what guarantees that every selector styled in one mode is
styled in the other. The two stylesheets were previously written by hand and
had drifted: context menus and the progress dialog were styled only in dark and
fell back to unthemed platform defaults in light.

Font sizes are emitted in points, computed from the application's base font and
the user's scale setting, so every level of the hierarchy moves together. The
fixed pixel sizes used before did not participate in scaling at all, so body
text grew while headings stayed put.
"""

from __future__ import annotations

from string import Template

try:
    from .design_tokens import (
        FONT_STACK,
        FONT_STACK_DISPLAY,
        FONT_STACK_MONO,
        RADIUS,
        TYPE_SCALE,
        palette,
    )
except ImportError:  # Compatibility with the sibling import path used by tests.
    from design_tokens import (  # type: ignore[no-redef]
        FONT_STACK,
        FONT_STACK_DISPLAY,
        FONT_STACK_MONO,
        RADIUS,
        TYPE_SCALE,
        palette,
    )


DEFAULT_BASE_POINT_SIZE = 9.0
MINIMUM_POINT_SIZE = 6.0


# ``string.Template`` uses ``$name``. QSS never contains a dollar sign, so the
# placeholders cannot collide with the stylesheet's own braces.
_TEMPLATE = Template(
    """/* AniRec $theme_name theme, generated from design tokens. Do not edit by hand. */
QWidget {
    background-color: $bg;
    color: $text;
    font-family: $font_stack;
    font-size: $font_md;
}
QLabel { background: transparent; }
QWidget#contentArea { background: $gradient_page; }
QToolTip {
    background: $surface_raised; color: $text; border: 1px solid $border_strong;
    border-radius: ${radius_sm}px; padding: 6px;
}

QFrame#sidebar {
    background: $sidebar;
    border-right: 1px solid $border_subtle;
}
/* CHANGE [HIERARCHY]: the selected page was a solid accent slab the size of a
   button, which put a fourth accent-filled block on a screen that already had
   three. Selection is now carried by a rail and the text colour, which is how
   you can tell where you are without the navigation shouting about it. The
   rail is present but transparent on every item, so nothing shifts by 3px
   when the selection moves. */
QFrame#sidebar QPushButton {
    text-align: left; padding: 10px 13px;
    background: transparent; color: $text_muted;
    border: 1px solid transparent; border-left: 3px solid transparent;
    border-radius: ${radius_md}px; font-weight: 600;
}
QFrame#sidebar QPushButton:hover { background: $surface; color: $text; }
QFrame#sidebar QPushButton:checked {
    background: $surface; color: $accent_soft;
    border-left-color: $accent;
}
/* Focus and selection have to stay tellable apart. An unselected item takes
   the rail in the system colour; the selected one keeps its brass rail and
   gains a hairline ring instead, so two items never look equally current. */
QFrame#sidebar QPushButton:focus:!checked {
    background: $surface; border-left-color: $focus;
}
QFrame#sidebar QPushButton:focus:checked {
    border-color: $focus; border-left-color: $accent;
}
QLabel#sidebarTitle, QLabel#pageTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_2xl; font-weight: 700;
}
QLabel#pageDescription, QLabel#sidebarFooter { color: $text_muted; }
/* CHANGE [CHROME]: the profile and connection states were two bordered pills
   on a row of their own, above a second full-width banner. Between them they
   took roughly a sixth of the window height on every page, to display two
   facts that change once a session. They are now quiet inline text on a
   single strip that the sample-data notice shares. */
QFrame#connectionStatusBar { background: transparent; border: none; }
QFrame#demoBanner { background: transparent; border: none; }
QLabel#activeProfileLabel {
    background: transparent; color: $text_muted; border: none;
    padding: 0; font-weight: 600;
}
QLabel#malConnectionLabel {
    background: transparent; color: $danger_text; border: none;
    padding: 0; font-weight: 600;
}
QLabel#malConnectionLabel[connected="true"] {
    background: transparent; color: $success_text; border: none;
}
QLabel#demoBannerText { color: $accent_soft; font-weight: 600; }
QFrame#demoBanner QPushButton { padding: 5px 12px; min-height: 16px; }

QPushButton {
    background: $surface_raised;
    border: 1px solid $border_strong;
    border-radius: ${radius_md}px;
    color: $text;
    /* CHANGE [BUG8]: one padding and one minimum height for every button, so
       controls sitting in a row share a baseline instead of each sizing to its
       own label. */
    padding: 7px 12px;
    min-height: 20px;
    text-align: center;
    font-weight: 600;
}
/* CHANGE [HIERARCHY]: hovering any button used to turn its border the accent
   colour, so a row of five neutral buttons all promised to be the important
   one. Neutral buttons now lift by tone; only the accent-bearing roles below
   use the accent. */
QPushButton:hover { background: $surface_raised; border-color: $border_strong; }
QPushButton:pressed { background: $surface_sunken; }
QPushButton:focus { border: 2px solid $focus; }
QPushButton:checked { background: $accent; border-color: $accent_hover; color: $accent_contrast; }
QPushButton[buttonRole="primary"] {
    background: $accent; border-color: $accent_hover; color: $accent_contrast;
}
QPushButton[buttonRole="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[buttonRole="secondary"] { background: $surface; border-color: $border_strong; }
QPushButton[buttonRole="ghost"] { background: transparent; border-color: $border; color: $text_muted; }
QPushButton[buttonRole="link"] {
    background: transparent; border-color: transparent; color: $accent_soft;
    /* CHANGE [BUG8]: matches the height and centring of the buttons beside it. */
    padding: 7px 8px; min-height: 20px; text-align: center;
}
QPushButton[buttonRole="link"]:hover { color: $accent_hover; background: transparent; }
QPushButton[buttonRole="danger"] { background: $danger_bg; border-color: $danger_border; color: $danger_text; }
/* CHANGE [DISABLED]: last, so it beats every role above it. A disabled
   control that still looks pressable is a control people click twice. */
QPushButton:disabled, QPushButton[buttonRole="primary"]:disabled,
QPushButton[buttonRole="secondary"]:disabled, QPushButton[buttonRole="ghost"]:disabled,
QPushButton[buttonRole="link"]:disabled, QPushButton[buttonRole="danger"]:disabled {
    background: $surface_sunken; color: $text_disabled;
    border-color: $border_subtle;
}
/* CHANGE [BUG7]: the feedback actions carried no colour of their own, so a
   Like and a Not for me looked identical until after they were pressed. They
   now preview their meaning on hover, in the greens and reds the active theme
   already defines, so the colour follows light, dark, OLED and gradient
   without a second palette. */
QPushButton[feedback="liked"]:hover {
    background: $success_bg; border-color: $success_border; color: $success_text;
}
QPushButton[feedback="liked"]:checked {
    background: $success_bg; border-color: $success_border; color: $success_text;
}
QPushButton[feedback="liked"]:checked:hover { border-color: $success_text; }
QPushButton[feedback="disliked"]:hover {
    background: $danger_bg; border-color: $danger_border; color: $danger_text;
}
QPushButton[feedback="disliked"]:checked {
    background: $danger_bg; border-color: $danger_border; color: $danger_text;
}
QPushButton[feedback="disliked"]:checked:hover { border-color: $danger_text; }
QPushButton[savedAction="true"]:hover {
    background: $saved_bg; border-color: $saved_border; color: $saved_text;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: $surface_sunken;
    color: $text;
    border: 1px solid $border;
    border-radius: ${radius_md}px;
    padding: 7px 9px;
    min-height: 22px;
    selection-background-color: $selection;
}
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: $border_strong; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 2px solid $focus; }
QLineEdit:read-only { background: $well; color: $text_muted; }
QComboBox::drop-down { border: none; width: 28px; }
QComboBox QAbstractItemView {
    background: $surface_raised; color: $text; border: 1px solid $border_strong;
    selection-background-color: $selection; padding: 4px;
    /* CHANGE [BUG-CORNERS]: the dropdown was a hard rectangle. */
    border-radius: ${radius_md}px;
}
QMenu {
    background: $surface_raised; color: $text; border: 1px solid $border;
    border-radius: ${radius_md}px; padding: 6px;
}
QMenu::item { padding: 8px 28px 8px 12px; border-radius: ${radius_sm}px; }
QMenu::item:selected { background: $accent; color: $accent_contrast; }
QCheckBox { spacing: 8px; color: $text; }
QCheckBox::indicator {
    width: 17px; height: 17px; border: 1px solid $border_strong;
    border-radius: ${radius_sm}px; background: $surface_sunken;
}
QCheckBox::indicator:hover { border-color: $focus; }
QCheckBox::indicator:checked { background: $accent; border-color: $accent_hover; }
QRadioButton { spacing: 8px; color: $text; }
QRadioButton::indicator {
    width: 15px; height: 15px; border: 1px solid $border_strong;
    /* A radio is a circle: half of 15px plus the 1px border. */
    border-radius: 9px; background: $surface_sunken;
}
QRadioButton::indicator:checked { background: $accent; border-color: $accent_hover; }

/* CHANGE [NATIVE-BLUE]: the slider was never styled, so Windows drew it in
   the system highlight colour - a bright blue that belonged to no theme and
   was the single most off-palette element in the whole application. */
QSlider::groove:horizontal {
    height: 4px; background: $surface_sunken;
    border: 1px solid $border; border-radius: 3px;
}
QSlider::sub-page:horizontal { background: $accent; border-radius: 3px; }
QSlider::add-page:horizontal { background: $surface_sunken; border-radius: 3px; }
QSlider::handle:horizontal {
    width: 14px; height: 14px; margin: -6px 0;
    /* Half of 14px plus the 2px border, so the knob stays round. */
    background: $accent; border: 2px solid $bg; border-radius: 9px;
}
QSlider::handle:horizontal:hover { background: $accent_hover; }
QSlider::handle:horizontal:focus { border-color: $focus; }
QSlider::groove:vertical {
    width: 4px; background: $surface_sunken;
    border: 1px solid $border; border-radius: 3px;
}
QSlider::handle:vertical {
    width: 14px; height: 14px; margin: 0 -6px;
    background: $accent; border: 2px solid $bg; border-radius: 9px;
}

/* The spin box steppers are deliberately left unstyled. Qt stops drawing its
   own arrow as soon as the sub-control is restyled, so giving these a
   background produced two blank blocks where the chevrons had been. Drawing
   real ones means shipping a light and a dark icon for a control this small,
   which is not a trade worth making: the platform steppers are plain, but
   they are steppers. */

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: ${radius_sm}px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $text_subtle; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: $border_strong; border-radius: ${radius_sm}px; min-width: 30px; }

QProgressBar {
    background: $surface_sunken; border: 1px solid $border; border-radius: ${radius_sm}px;
    color: $text; min-height: 12px; text-align: center;
}
QProgressBar::chunk { background: $accent; border-radius: ${radius_sm}px; }
QDialog#operationProgressDialog {
    background: $surface; border: 1px solid $border; border-radius: ${radius_xl}px;
}
QLabel#progressStepLabel {
    color: $text_strong; font-family: $font_display;
    font-size: $font_lg; font-weight: 700;
}
QLabel#progressCounterLabel { color: $text_muted; font-weight: 600; }
QDialog#operationProgressDialog[operationState="success"] QLabel#progressStepLabel,
QDialog#operationProgressDialog[operationState="success"] QLabel#progressCounterLabel {
    color: $success_text;
}

QDialog#errorDialog, QDialog#setupWizard { background: $bg; }
QLabel#wizardStepIndicator { color: $text_muted; font-weight: 700; }
QLabel#wizardRequiredHint, QLabel#wizardFieldHint { color: $text_muted; font-size: $font_sm; }
QLabel#wizardIntro { color: $text; font-size: $font_md; }
QLabel#wizardSteps { color: $text_muted; font-size: $font_sm; }
QLabel#wizardApiLink { color: $accent_soft; font-weight: 600; }
QLabel#apiTestStatus, QLabel#oauthStatusLabel, QLabel#analysisStatusLabel { color: $text_muted; }

QFrame#dashboardMetricCard, QFrame[metricCard="true"] {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QFrame#dashboardPanel {
    background: transparent; border: none;
    border-bottom: 1px solid $border_subtle; border-radius: 0;
}
QLabel#dashboardMetricLabel, QLabel#dashboardActionReason { color: $text_muted; }
QLabel#dashboardMetricValue {
    color: $text_strong; font-family: $font_mono;
    font-size: $font_xl; font-weight: 700;
}
QLabel#dashboardSectionTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_lg; font-weight: 700;
}
QLabel#dashboardEmptyState {
    background: $warning_bg; border: 1px solid $warning_border; border-radius: ${radius_md}px;
    color: $warning_text; padding: 10px 12px;
}
QLabel#dashboardActivity {
    background: $surface_raised; border: 1px solid $border; border-radius: ${radius_md}px;
    color: $text_muted; padding: 6px 11px; font-weight: 600;
}
QLabel#dashboardActivity[tone="success"] { background: $success_bg; border-color: $success_border; color: $success_text; }
QLabel#dashboardActivity[tone="busy"] { background: $busy_bg; border-color: $busy_border; color: $busy_text; }
QLabel#dashboardActivity[tone="error"] { background: $danger_bg; border-color: $danger_border; color: $danger_text; }
QLabel#dashboardGenreName { color: $text; font-weight: 600; }
QLabel#dashboardGenreScore {
    color: $accent_soft; font-family: $font_mono; font-weight: 700;
}
/* CHANGE [BUG-CORNERS]: the genre bars were square-ended. */
QProgressBar#dashboardGenreBar {
    min-height: 9px; max-height: 9px; border: none;
    background: $surface_sunken; border-radius: ${radius_sm}px;
}
QFrame[homeRecommendationCard="true"] {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QFrame[homeRecommendationCard="true"]:hover { border-color: $accent; background: $surface_raised; }
QLabel#homeRecommendationCover { background: $well; border-radius: ${radius_md}px; }
QLabel#homeRecommendationTitle { color: $text_strong; font-size: $font_sm; font-weight: 700; }
QLabel#homeRecommendationScore {
    color: $accent_soft; font-family: $font_mono; font-weight: 700;
}
QLabel#homeRecommendationMeta, QLabel#dashboardNoRecommendations { color: $text_muted; }
QPushButton[dashboardAction="true"] { text-align: left; }

QFrame[recommendationCard="true"] {
    background: $gradient_card;
    border: 1px solid $border; border-radius: ${radius_lg}px;
}
QFrame[recommendationCard="true"]:hover { background: $surface_raised; border-color: $accent; }
QFrame[recommendationCard="true"][tasteState="liked"] { border-color: $success_border; }
QFrame[recommendationCard="true"][tasteState="disliked"] { border-color: $danger_border; }
QFrame[recommendationCard="true"]:focus, QFrame[recommendationCard="true"][selected="true"] {
    border: 2px solid $focus;
}
QWidget#page-recommendations { background: $gradient_page; }
/* CHANGE [NESTING]: the feed header was a rounded, bordered card holding
   a bordered summary box and a bordered control box - three frames deep
   before any anime. It is a band now: tone separates it from the page, and
   nothing inside it needs its own outline. */
QFrame#recommendationHero {
    background: $gradient_hero;
    border: none; border-radius: ${radius_lg}px;
}
QLabel#recommendationEyebrow {
    color: $accent; font-size: $font_xs; font-weight: 800;
}
QLabel#recommendationActionCaption {
    color: $text_subtle; font-size: $font_xs; font-weight: 800;
}
/* Kept on one line with colour and size adjacent: the font-scale test reads
   this rule out of the generated sheet by pattern. */
QLabel#recommendationHeroTitle { color: $text_strong; font-size: $font_4xl; font-weight: 800; font-family: $font_display; }
QLabel#recommendationHeroDescription { color: $text_muted; font-size: $font_sm; }
QTableWidget {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QFrame#recommendationControls {
    background: transparent; border: none;
    border-top: 1px solid $border_subtle; border-radius: 0;
}
QFrame#recommendationControls { padding: 4px; }
QLabel#recommendationFeedbackSummary {
    background: transparent; border: none; padding: 0;
    color: $text_muted; font-weight: 600;
}
QFrame#recommendationLibraryBar {
    background: $surface_sunken; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QPushButton[libraryTab="true"] {
    background: transparent; border: 1px solid transparent; border-radius: ${radius_md}px;
    color: $text_muted; padding: 9px 15px; font-weight: 700;
}
QPushButton[libraryTab="true"]:hover { background: $surface_raised; color: $text_strong; }
QPushButton[libraryTab="true"]:checked {
    background: $accent_muted; border-color: $accent; color: $text_strong;
}
QPushButton[viewToggle="true"] { padding: 8px 11px; }
QFrame#recommendationSelectedActions {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QLabel#recommendationSelectedLabel { color: $text; font-weight: 700; }
QLabel#recommendationFilterLabel, QLabel#recommendationResultCount { color: $text_muted; }
QFrame#recommendationEmptyPanel {
    background: $gradient_hero;
    border: 1px solid $border; border-radius: ${radius_xl}px;
}
QLabel#recommendationEmptyIcon {
    background: $accent; color: $accent_contrast; border: 1px solid $accent_hover;
    border-radius: 28px; font-size: $font_3xl; font-weight: 800;
}
QLabel#recommendationEmptyTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_2xl; font-weight: 800;
}
QLabel#recommendationEmptyState { color: $text_muted; font-size: $font_md; }
QLabel#personalMatchLabel {
    color: $accent_soft; font-family: $font_mono;
    font-size: $font_lg; font-weight: 700;
}
QLabel#recommendationTitle { color: $text_strong; font-size: $font_md; font-weight: 700; }
QLabel#recommendationSecondaryTitle, QLabel#recommendationMeta { color: $text_muted; }
QLabel#recommendationGenres { color: $text; }
QLabel#recommendationReason { color: $text_muted; }
QLabel#recommendationCover { background: $well; border-radius: ${radius_md}px; }
QPushButton[savedAction="true"]:checked {
    background: $saved_bg; border-color: $saved_border; color: $saved_text;
}
QFrame[recommendationRow="true"] {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QFrame[recommendationRow="true"]:hover { background: $surface_raised; border-color: $accent; }
QFrame[recommendationRow="true"][tasteState="liked"] { border-color: $success_border; }
QFrame[recommendationRow="true"][tasteState="disliked"] { border-color: $danger_border; }
QFrame[recommendationRow="true"]:focus,
QFrame[recommendationRow="true"][selected="true"] { border: 2px solid $focus; }
QLabel#recommendationRowCover { background: $well; border-radius: ${radius_md}px; }
QLabel#recommendationRowTitle { color: $text_strong; font-size: $font_md; font-weight: 700; }
QLabel#recommendationRowReason { color: $text_muted; font-size: $font_sm; }
QLabel#recommendationRowMatchTag {
    font-family: $font_mono;
    background: $accent_muted; color: $accent_soft; border: 1px solid $accent;
    border-radius: ${radius_md}px; padding: 5px 11px; font-weight: 700;
    min-height: 15px;
}
QLabel#recommendationRowGenreTag {
    background: $surface_sunken; color: $text_muted; border: 1px solid $border;
    border-radius: ${radius_md}px; padding: 5px 11px; min-height: 15px;
}
QWidget#gradientPreview { border-radius: ${radius_md}px; }
QHeaderView::section {
    background: $surface_sunken; color: $text_muted; border: none;
    border-bottom: 1px solid $border; padding: 8px; font-weight: 600;
    /* CHANGE [BUG-CORNERS]: softened to match every other surface. */
    border-radius: ${radius_sm}px;
}
QTableWidget { gridline-color: $border; selection-background-color: $selection; }

/* CHANGE [TITLE-COLLISION]: the group title sat on the margin, so the card's
   own border ran straight through the middle of the words. Moving it inside
   the padding box makes it a section label rather than a notch cut into a
   frame, and nothing has to be painted over the border to hide the join. */
QGroupBox[settingsCard="true"] {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
    margin-top: 0; padding: 38px 18px 18px 18px; font-weight: 700;
}
QGroupBox[settingsCard="true"]::title {
    subcontrol-origin: padding; subcontrol-position: top left;
    left: 18px; top: 14px; padding: 0;
    color: $text_muted; font-family: $font_display;
    font-size: $font_sm; font-weight: 700;
}
QLabel#settingsStatus, QLabel#settingsApiStatus, QLabel#settingsDataScopeHint { color: $text_muted; }
QLabel#settingsStatus[error="true"] { color: $danger_text; }

QLabel#recommendationDetailTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_2xl; font-weight: 700;
}
QLabel#recommendationDetailSecondaryTitle, QLabel#recommendationDetailAlternatives { color: $text_muted; }
QLabel#recommendationDetailSectionTitle { color: $text_strong; font-size: $font_md; font-weight: 700; }
QFrame#genreBarsFrame, QTableWidget#genreAnalysisTable, QFrame[advancedOperation="true"] {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QLabel#genreAnalysisEmptyState, QLabel#genreImportanceExactScore,
QLabel#advancedOperationDescription, QLabel#advancedOperationPrerequisite,
QLabel#advancedOperationLastRun { color: $text_muted; }
QLabel#advancedOperationTitle { color: $text_strong; font-size: $font_md; font-weight: 700; }
QLabel#errorDialogTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_xl; font-weight: 700;
}
QLabel#errorDialogDescription { color: $text; }
QLabel#errorDialogSectionTitle { color: $text_strong; font-weight: 700; }
QPlainTextEdit#errorDialogTechnicalDetails {
    background: $well; border-color: $border; color: $text_muted;
}
"""
)


def _point_size(ratio: float, base_point_size: float, font_scale: float) -> str:
    size = max(MINIMUM_POINT_SIZE, base_point_size * ratio * font_scale)
    return f"{size:.1f}pt"


def build_stylesheet(
    theme: str,
    *,
    base_point_size: float = DEFAULT_BASE_POINT_SIZE,
    font_scale: float = 1.0,
    gradient_start: str | None = None,
    gradient_end: str | None = None,
) -> str:
    """Render the stylesheet for a theme at a given font scale."""
    colours = palette(
        theme, gradient_start=gradient_start, gradient_end=gradient_end
    )
    base = base_point_size if base_point_size > 0 else DEFAULT_BASE_POINT_SIZE
    values = dict(colours)
    values["theme_name"] = str(theme).strip().casefold()
    values["font_stack"] = FONT_STACK
    values["font_display"] = FONT_STACK_DISPLAY
    values["font_mono"] = FONT_STACK_MONO
    for name, ratio in TYPE_SCALE.items():
        values[f"font_{name}"] = _point_size(ratio, base, font_scale)
    for name, size in RADIUS.items():
        values[f"radius_{name}"] = size
    return _TEMPLATE.substitute(values)


def selectors(stylesheet: str) -> set[str]:
    """The set of selectors a stylesheet styles, used to prove parity."""
    import re

    text = re.sub(r"/\*.*?\*/", "", stylesheet, flags=re.DOTALL)
    found: set[str] = set()
    for block in re.findall(r"([^{}]+)\{[^{}]*\}", text, re.MULTILINE):
        for selector in block.split(","):
            cleaned = " ".join(selector.split())
            if cleaned:
                found.add(cleaned)
    return found
