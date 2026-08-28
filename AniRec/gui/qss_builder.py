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
/* CHANGE [RAIL]: three destinations did not need three large pill buttons.
   The rail is now an indexed front panel - a number, a selection mark, and
   the space that buys back for a live system readout underneath. */
QWidget#sidebarPlate { background: $surface_sunken; }
QLabel#sidebarKana {
    color: $text_subtle; font-size: $font_xs; letter-spacing: 3px;
}
QFrame#railRule { background: $border; border: none; max-height: 1px; }
QFrame#sidebar QPushButton[navItem="true"] {
    text-align: left; padding: 8px 13px;
    background: transparent; color: $text_muted;
    border: none; border-left: 3px solid transparent;
    border-radius: 0;
    font-family: $font_mono; font-size: $font_sm; font-weight: 600;
}
QFrame#sidebar QPushButton[navItem="true"]:hover {
    background: $surface; color: $text;
}
/* CHANGE [RAIL-MARK]: the selection mark is a widget (NavMarker) that
   travels between rows, not a border colour that teleports. The 3px
   transparent border-left stays on every row so the mark occupies reserved
   space rather than shifting the labels when it arrives. Focus keeps its own
   rail colour: an unselected focused row must still be tellable apart. */
QFrame#sidebar QPushButton[navItem="true"]:checked {
    background: $surface; color: $accent_soft;
}
/* Focus and selection must stay tellable apart: an unselected item takes the
   rail in the system colour, the selected one keeps brass and gains a ring. */
QFrame#sidebar QPushButton[navItem="true"]:focus:!checked {
    background: $surface; border-left-color: $focus;
}
QFrame#sidebar QPushButton[navItem="true"]:focus:checked {
    color: $text_strong;
}

/* The system readout. Keys recede, values carry a state tone. */
QFrame#systemReadout { background: transparent; border: none; }
/* The activity console. A recessed instrument, not a text editor. */
QFrame#systemLog { background: transparent; border: none; }
QPlainTextEdit#systemLogView {
    background: $well; border: 1px solid $border; border-radius: 0;
    color: $text_muted; font-family: $font_mono; font-size: $font_xs;
    padding: 5px 6px; selection-background-color: $selection;
}
QLabel#railCaption {
    color: $text_subtle; font-family: $font_display;
    font-size: $font_xs; font-weight: 700; letter-spacing: 2px;
}
QLabel#readoutKey {
    color: $text_subtle; font-family: $font_mono; font-size: $font_xs;
    letter-spacing: 1px;
}
QLabel#readoutValue {
    color: $text_muted; font-family: $font_mono; font-size: $font_xs;
    font-weight: 600; letter-spacing: 1px;
}
/* "ok" here means the system is fine, which is cyan's job. This was
   $success_text - a green that appears nowhere else in the design and left
   the ENGINE lamp cyan with the word beside it green. */
QLabel#readoutValue[tone="ok"]   { color: $focus; }
QLabel#readoutValue[tone="warn"] { color: $accent_soft; }
QLabel#readoutValue[tone="busy"] { color: $busy_text; }
/* $text_muted, not $text_disabled: idle measured 2.57:1 on dark and
   2.01:1 on light against AA's 4.5:1, and the rows rendered that way are
   PROFILE and MAL - the two facts a new user most needs to see. */
QLabel#readoutValue[tone="idle"] { color: $text_muted; }

QLabel#sidebarTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_xl; font-weight: 800; letter-spacing: 2px;
}
QLabel#pageTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_2xl; font-weight: 700;
}
QLabel#pageDescription { color: $text_muted; }
QLabel#sidebarFooter {
    color: $text_disabled; font-family: $font_mono;
    font-size: $font_xs; letter-spacing: 1px;
}
/* CHANGE [CHROME]: the profile and connection states were two bordered pills
   on a row of their own, above a second full-width banner. Between them they
   took roughly a sixth of the window height on every page, to display two
   facts that change once a session. They are now quiet inline text on a
   single strip that the sample-data notice shares. */
QFrame#connectionStatusBar {
    background: $gradient_hero; border: none;
    border-bottom: 1px solid $border; border-radius: 0;
}
QFrame#demoBanner { background: transparent; border: none; }
QLabel#activeProfileLabel {
    background: transparent; color: $text_muted; border: none;
    padding: 0; font-family: $font_mono; font-size: $font_sm;
    font-weight: 600; letter-spacing: 0.5px;
}
QLabel#malConnectionLabel {
    background: transparent; color: $danger_text; border: none;
    padding: 0; font-family: $font_mono; font-size: $font_sm;
    font-weight: 700; letter-spacing: 0.5px;
}
QLabel#malConnectionLabel[connected="true"] {
    background: transparent; color: $success_text; border: none;
}
QFrame#malStatusIndicator {
    background: $danger_text; border: 1px solid $danger_border; border-radius: 0;
}
QFrame#malStatusIndicator[connected="true"] {
    background: $success_text; border-color: $success_border;
}
QLabel#demoBannerText { color: $accent_soft; font-weight: 600; }

/* Discover header strip: channel legend, machine state, run control. */
/* One header instrument: an outer frame, two lines, one hairline between
   them. The strip and the taste half are panes inside it, not boxes of
   their own. */
QFrame#discoverHeader {
    background: $surface; border: 1px solid $border; border-radius: 0;
}
QWidget#discoverActionStrip { background: $surface_sunken; }
QFrame#discoverHeader QFrame#dashboardPanel {
    background: transparent; border: none; border-radius: 0;
}
QLabel#discoverChannel {
    color: $accent_soft; font-family: $font_display;
    font-size: $font_xs; font-weight: 800; letter-spacing: 2px;
}
QLabel#discoverStateCaption {
    color: $text_subtle; font-family: $font_mono;
    font-size: $font_xs; font-weight: 600; letter-spacing: 2px;
}
QLabel#discoverStateValue {
    color: $text; font-family: $font_mono;
    font-size: $font_sm; font-weight: 600; letter-spacing: 0.5px;
}
/* The same tone vocabulary the rail's readout uses, so READY/BUSY/FAULT mean
   the same thing in both places. */
QLabel#discoverStateValue[tone="ok"]    { color: $focus; }
QLabel#discoverStateValue[tone="busy"]  { color: $busy_text; }
QLabel#discoverStateValue[tone="error"] { color: $danger_text; }
/* The sentence beside the state: prose, so the reading face. It used to be
   written into the STATE field itself and rendered as wrapped monospace. */
QLabel#discoverStatusMessage {
    color: $text_muted; font-family: $font_stack;
    font-size: $font_sm; font-weight: 400; letter-spacing: 0;
}
QFrame#stripDivider { background: $border_strong; border: none; }

/* CHANGE [FEED-FURNITURE]: the feed's own controls were still sentence-case
   pills on a surface that had otherwise become an instrument. Labels are
   pinned by tests, so the shift is carried entirely by the typeface, the
   tracking and the corners. */
QPushButton[feedback="liked"], QPushButton[feedback="disliked"],
QPushButton[savedAction="true"], QPushButton[viewToggle="true"],
QPushButton#recommendationDetailsButton, QPushButton#recommendationMoreButton,
QPushButton#recommendationHideButton, QPushButton#recommendationMalButton,
QPushButton#recommendationFilterToggle {
    font-family: $font_mono; font-size: $font_xs; font-weight: 700;
    letter-spacing: 1px; border-radius: 0;
}
QPushButton[viewToggle="true"] {
    min-height: 24px; padding: 5px 12px;
    background: $surface_sunken; border-color: $border;
}
QPushButton[viewToggle="true"]:checked {
    background: $accent_muted; border-color: $accent; color: $accent_soft;
}
QLabel#recommendationResultCount, QLabel#recommendationFeedbackSummary {
    font-family: $font_mono; font-size: $font_xs;
    letter-spacing: 1px; color: $text_subtle;
}
QLabel#recommendationFilterLabel {
    font-family: $font_mono; font-size: $font_xs; letter-spacing: 1px;
}
/* Card metadata is data. */
QLabel#malScoreLabel, QLabel#recommendationMeta, QLabel#personalMatchLabel {
    font-family: $font_mono; letter-spacing: 0.5px;
}
/* The run control is a control, not a floating pill.
   CHANGE [ROW]: and it is the same height as every other control. It stood
   42px tall while the primary action on Settings stood 36, so the two
   surfaces ranked their one primary action differently. Height is not what
   marks it out - the accent is. */
QPushButton#discoverRefreshButton {
    font-family: $font_mono; font-size: $font_sm; font-weight: 700;
    letter-spacing: 1.5px; border-radius: 0; min-height: 20px;
}
QPushButton#tastePanelToggle {
    font-family: $font_mono; font-size: $font_xs; font-weight: 700;
    letter-spacing: 1.5px;
}
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

/* CHANGE [ROW]: inputs measured 38px against a 36px button, so a form row
   holding both was two pixels ragged. They share the button's vertical
   padding now. */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: $surface_sunken;
    color: $text;
    border: 1px solid $border;
    border-radius: ${radius_md}px;
    padding: 7px 9px;
    /* CHANGE [ROW]: 20, matching the button rule. With identical padding on
       both, this two-pixel difference was the entire reason an input measured
       38px beside a 36px button in the same form row. */
    min-height: 20px;
    selection-background-color: $selection;
}
/* CHANGE [ROW]: a spin box wraps its own line edit, which takes the padding
   above a second time and pushed the control to 40px against every other
   control's 36. The outer padding comes back down by the difference. */
/* Numeric fields take the numeric face: these hold counts and multipliers
   ("10", "Any", "1.00x"), and they were rendering in the reading face. */
QSpinBox, QDoubleSpinBox { padding: 5px 9px; font-family: $font_mono; }
QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover { border-color: $border_strong; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border: 2px solid $focus; }
QLineEdit:read-only { background: $well; color: $text_muted; }
/* The drop-down and its arrow are appended at runtime by ThemeManager,
   because the arrow needs an image and an image needs an absolute path. */
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
/* CHANGE [BLEED]: QWidget sets the page background for everything that does
   not override it, so a checkbox or a slider sitting on a panel painted its
   own strip of *page* colour across the panel. Invisible when the two were
   near-identical; a solid slab the moment a gradient theme pulled them apart.
   These controls belong to whatever surface is behind them. */
QCheckBox, QRadioButton, QSlider { background: transparent; }
/* min-height so a check-box row occupies the same band as every other
   control in the grid. The rows ran 36/36/36/36/16/16 and the label column
   sat against two different control heights. */
QCheckBox { spacing: 10px; color: $text; min-height: 20px; padding: 8px 0; }
QCheckBox::indicator {
    width: 13px; height: 13px; border: 1px solid $border_strong;
    border-radius: ${radius_sm}px; background: $surface_sunken;
}
QCheckBox::indicator:hover { border-color: $focus; }
/* Cyan: a settings check box is machine configuration, not the user's
   taste, and amber is reserved for what is theirs. */
QCheckBox::indicator:checked { background: $focus; border-color: $focus; }
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
    height: 2px; background: $border;
    border: none; border-radius: 0;
}
QSlider::sub-page:horizontal { background: $accent; border-radius: 0; }
QSlider::add-page:horizontal { background: $border; border-radius: 0; }
QSlider::handle:horizontal {
    width: 8px; height: 18px; margin: -8px 0;
    background: $well; border: 1px solid $accent; border-radius: 0;
}
QSlider::handle:horizontal:hover { background: $accent_hover; }
QSlider::handle:horizontal:focus { border-color: $focus; }
QSlider::groove:vertical {
    width: 2px; background: $border;
    border: none; border-radius: 0;
}
QSlider::handle:vertical {
    width: 18px; height: 8px; margin: 0 -8px;
    background: $well; border: 1px solid $accent; border-radius: 0;
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
/* The wizard's form keys and machine-value fields, so the first screen a new
   user sees belongs to the same machine as Settings. The keys were rendering
   as prose in the reading face; the inputs hold a hex client id, a secret and
   a redirect URI - machine values, which take the machine face. */
QLabel#wizardFieldKey {
    color: $text_muted; font-family: $font_mono; font-size: $font_xs;
    font-weight: 600; letter-spacing: 1px;
}
QLineEdit#apiClientIdInput, QLineEdit#apiClientSecretInput,
QLineEdit#apiRedirectUriInput, QLineEdit#malProfileReferenceInput,
QLineEdit#settingsClientId, QLineEdit#settingsClientSecret {
    font-family: $font_mono;
}

/* The colour here applies only to any plain text in the label. The label
   holds an <a>, and Qt takes anchor colour from QPalette::Link - set in
   theme.py - never from a stylesheet. Changing the value below will not
   change the link. */
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
QLabel#homeRecommendationTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_sm; font-weight: 700;
}
QLabel#homeRecommendationScore {
    color: $accent_soft; font-family: $font_mono; font-weight: 700;
}
QLabel#homeRecommendationMeta, QLabel#dashboardNoRecommendations { color: $text_muted; }
QPushButton[dashboardAction="true"] { text-align: left; }

/* CHANGE [FIT]: the action grid fixes the column width, so these labels have
   to live inside it. Default button padding left "Not for me" clipped to
   "lot for me"; the padding yields instead of the word. */
QFrame[recommendationCard="true"] QPushButton {
    padding: 6px 4px; min-height: 22px;
    font-family: $font_mono; font-size: $font_xs;
    font-weight: 700; letter-spacing: 0.5px;
}
QFrame[recommendationCard="true"] QPushButton[buttonRole="ghost"] {
    background: $surface_sunken; border: 1px solid $border; color: $text_muted;
}
QFrame[recommendationCard="true"] QPushButton[buttonRole="ghost"]:hover {
    background: $surface_raised; border-color: $border_strong; color: $text;
}
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
    background: transparent; border: none;
    border-bottom: 1px solid $border; border-radius: 0;
}
/* CHANGE [CRT]: the collection switches were the last thing on this surface
   still reading as a web app's tab bar - proportional, near body size, with
   an underline. The artifact spells this kind of control as a stencilled
   chip: display face, small, wide letterspacing, a hairline box, and the
   accent carried by the border and the text rather than by a bar underneath. */
QPushButton[libraryTab="true"] {
    background: transparent; border: 1px solid $border; border-radius: 0;
    color: $text_subtle; padding: 7px 12px; min-height: 20px;
    font-family: $font_mono; font-size: $font_xs; font-weight: 600;
    letter-spacing: 2px;
}
/* CHANGE [FOCUS]: selection takes amber, focus on an unselected tab takes
   cyan. Without this the tabs had no focus state at all - measured as
   pixel-identical to their resting state - so a keyboard user could not see
   which collection they were about to open. Negating :checked keeps the two
   meanings apart on the tab that is both current and focused. */
QPushButton[libraryTab="true"]:focus:!checked {
    border-color: $focus; color: $focus;
}
QPushButton[libraryTab="true"]:hover {
    background: $surface_raised; border-color: $border_strong; color: $text;
}
QPushButton[libraryTab="true"]:checked {
    background: transparent; border-color: $accent; color: $accent;
}
/* CHANGE [ROW]: this used to set padding: 8px 11px, which is three pixels
   more vertical padding than every other control in the same bar. Measured on
   the view row, that produced tops at y=54, 60 and 70 and bottoms at 96 and
   106 - four controls on one line, no two sharing an edge. The toggles take
   the same padding as their neighbours now, and the row centres what is
   left. */
QFrame#recommendationSelectedActions {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QLabel#recommendationSelectedLabel { color: $text; font-weight: 700; }
QLabel#recommendationFilterLabel, QLabel#recommendationResultCount { color: $text_muted; }
QFrame#recommendationEmptyPanel {
    background: transparent; border: none; border-radius: 0;
}
/* An empty collection is an absence, not the user's action, so it does not
   get amber - and a solid filled plate above a heading is the mobile
   empty-state illustration idiom. Outline only. */
QLabel#recommendationEmptyIcon {
    background: transparent; color: $border_strong; border: 1px solid $border_strong;
    border-radius: 0; font-family: $font_mono; font-size: $font_2xl; font-weight: 800;
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
/* The title is the thing being recommended. It was set at body size,
   smaller than the genre line beneath it. */
QLabel#recommendationTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_lg; font-weight: 800;
}
QLabel#recommendationSecondaryTitle { color: $text_muted; }
QLabel#recommendationMeta {
    color: $text_muted; font-family: $font_mono; font-size: $font_xs;
}
/* CHANGE [HIERARCHY]: the genres are what the recommendation is about, so
   they lead the metadata block. The MyAnimeList average is a third party's
   opinion and now sits with the rest of the catalogue data rather than
   above them at the same weight. */
QLabel#recommendationGenres {
    color: $text; font-size: $font_sm; font-weight: 600;
}
QLabel#malScoreLabel {
    color: $text_subtle; font-family: $font_mono;
    font-size: $font_xs; font-weight: 400; letter-spacing: 0.5px;
}
QLabel#recommendationReason { color: $text_muted; font-size: $font_xs; }
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
QLabel#recommendationRowTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_md; font-weight: 700;
}
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
    left: 18px; top: 13px; padding: 0;
    color: $accent_soft; font-family: $font_display;
    font-size: $font_xs; font-weight: 800; letter-spacing: 2px;
}
/* CHANGE [PANEL]: settings rows are a spec sheet, not a web form. The key
   column recedes into a mono legend; hints keep their own identity because
   an id selector outranks this one. */
QGroupBox[settingsCard="true"] QLabel {
    color: $text_subtle; font-family: $font_mono;
    font-size: $font_xs; font-weight: 600; letter-spacing: 1px;
}
/* Prose is prose. The rule above is meant for the key column, but it also
   caught the explanatory hints, and a wrapped paragraph set in monospace at
   this size is measurably slower to read. Sentences go back to the body face
   and keep the technical treatment for the labels beside them. */
QGroupBox[settingsCard="true"] QLabel#settingsDataScopeHint,
QGroupBox[settingsCard="true"] QLabel#settingsStatus,
QGroupBox[settingsCard="true"] QLabel#settingsApiStatus {
    font-family: $font_stack; font-size: $font_sm;
    font-weight: 400; letter-spacing: 0; color: $text_muted;
}
/* Panel actions are controls - and so are the page's own footer actions,
   which sit outside any group box and were falling through to the reading
   face while every button beside them was mono. */
QWidget#page-settings QPushButton,
QGroupBox[settingsCard="true"] QPushButton {
    font-family: $font_mono; font-size: $font_xs;
    font-weight: 700; letter-spacing: 1px; border-radius: 0;
}
QLabel#settingsStatus, QLabel#settingsApiStatus, QLabel#settingsDataScopeHint { color: $text_muted; }
QLabel#settingsStatus[error="true"] { color: $danger_text; }

/* ----- score inspector --------------------------------------------------
   The landing page's scoring bench is the product.  The detail surface uses
   the same hierarchy: recessed readout, calibrated rail, contribution rows,
   and a visible sum.  Texture is painted by InstrumentPanel so it follows all
   generated themes without bitmap assets. */
QDialog#recommendationDetailDialog { background: $bg; }
QFrame#recommendationDetailRack {
    background: $gradient_hero; border: none;
    border-bottom: 1px solid $border; border-radius: 0;
}
QLabel#recommendationDetailRackLegend,
QLabel#recommendationDetailNavigation {
    color: $text_muted; font-family: $font_mono; font-size: $font_xs;
    font-weight: 700; letter-spacing: 1px;
}
QFrame#recommendationDetailRack QPushButton { min-width: 28px; padding: 4px 8px; }
QPushButton#recommendationDetailPrevious,
QPushButton#recommendationDetailNext { font-size: $font_xl; padding: 1px 7px; }
QScrollArea#recommendationDetailScroll,
QWidget#recommendationDetailContent { background: $gradient_page; border: none; }
QLabel#recommendationDetailCover { background: $well; border-radius: ${radius_md}px; }
QLabel#recommendationDetailTitle {
    color: $text_strong; font-family: $font_display;
    font-size: $font_2xl; font-weight: 700;
}
QLabel#recommendationDetailSecondaryTitle { color: $text_muted; font-size: $font_sm; }
QLabel#recommendationDetailAlternatives { color: $text_subtle; font-size: $font_xs; }
QLabel[detailFact="true"] { color: $text_muted; font-size: $font_sm; }
QFrame#recommendationScoreBench {
    background: $gradient_hero; border: 1px solid $border;
    border-radius: ${radius_lg}px;
}
QLabel#recommendationScoreLegend,
QLabel#recommendationScoreMode,
QLabel#recommendationScoreScale,
QLabel#recommendationScoreSumCaption {
    color: $text_subtle; font-family: $font_mono; font-size: $font_xs;
    font-weight: 700; letter-spacing: 1px;
}
QLabel#recommendationScoreMode { color: $focus; }
QLabel#recommendationScoreValue {
    color: $accent; font-family: $font_mono; font-size: $font_4xl;
    font-weight: 700; min-height: 44px;
}
QLabel#recommendationScorePercent {
    color: $accent_soft; font-family: $font_mono; font-size: $font_lg;
    font-weight: 700;
}
QLabel#recommendationDetailReason { color: $text; font-size: $font_sm; }
QWidget#recommendationScoreTrack { background: transparent; }
QFrame[scoreContributor="true"] {
    background: transparent; border: none; border-top: 1px solid $border_subtle;
}
QLabel[scoreContributorName="true"] { color: $text; font-size: $font_sm; }
QLabel#recommendationScoreContributionValue,
QLabel#recommendationScoreSum {
    color: $accent_soft; font-family: $font_mono; font-weight: 700;
}
QLabel#recommendationScoreSum { font-size: $font_lg; }
QLabel#recommendationScoreEmpty { color: $text_muted; font-size: $font_sm; }
QFrame[contributionTone="accent1"] { background: $accent; }
QFrame[contributionTone="accent2"] { background: $accent_hover; }
QFrame[contributionTone="accent3"] { background: $accent_soft; }
QFrame[contributionTone="accent4"] { background: $warning_text; }
QFrame[contributionTone="signal"] { background: $focus; }
QFrame[contributionTone="negative"] { background: $danger_text; }
QFrame#recommendationSynopsisPanel {
    background: $surface; border: none; border-top: 1px solid $border;
    border-radius: 0;
}
QPushButton#recommendationSynopsisToggle {
    color: $accent_soft; font-family: $font_mono; font-size: $font_xs;
    font-weight: 700; text-align: left; letter-spacing: 1px;
}
QLabel#recommendationDetailSynopsis { color: $text_muted; }
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

/* ==========================================================================
   SERIES BUNDLES

   A bundle is a container, not a poster. It reads as raised rather than as a
   third accent colour: amber still means "yours" and cyan still means "the
   system", and a franchise is neither.
   ========================================================================== */
QFrame#bundleCard {
    background: $surface_raised;
    border: 1px solid $border_strong;
    border-radius: ${radius_lg}px;
}
QFrame#bundleCard:hover { border-color: $accent_hover; }
/* Focus takes the signal colour, selection takes the accent - the same rule
   the collection tabs follow, so the two meanings never collapse into one. */
QFrame#bundleCard:focus { border-color: $focus; }
QFrame#bundleCard[expanded="true"] { border-color: $accent; }

QLabel#bundleTitle {
    color: $text; font-family: $font_display; font-size: $font_lg;
    font-weight: 800; letter-spacing: 0.5px; background: transparent;
}
QLabel#bundleCount {
    color: $text_subtle; font-family: $font_mono; font-size: $font_xs;
    letter-spacing: 1px; background: transparent;
}
QLabel#bundleMatch {
    color: $accent; font-family: $font_mono; font-size: $font_sm;
    font-weight: 700; letter-spacing: 1px; background: transparent;
}
QLabel#bundleStack { background: transparent; border: none; }

QFrame#bundleInfo {
    background: $surface;
    border: 1px solid $border;
    border-radius: ${radius_lg}px;
}
QLabel#bundleInfoCaption {
    color: $text_subtle; font-family: $font_display; font-size: $font_xs;
    font-weight: 700; letter-spacing: 2px; background: transparent;
}
QLabel#bundleInfoMeta {
    color: $text_subtle; font-family: $font_mono; font-size: $font_xs;
    letter-spacing: 1px; background: transparent;
}
QLabel#bundleInfoValue {
    color: $accent; font-family: $font_display; font-size: $font_4xl;
    font-weight: 700; background: transparent;
}
QLabel#bundleInfoPercent {
    color: $accent_soft; font-family: $font_display; font-size: $font_lg;
    font-weight: 700; background: transparent;
}
QLabel#bundleInfoReason {
    color: $text_muted; font-size: $font_xs; background: transparent;
}

/* The panel the bundle opens into, and the wrapper that reveals it. */
QFrame#bundlePanel {
    background: $surface_raised;
    border: 1px solid $accent;
    border-radius: ${radius_lg}px;
}
QLabel#bundlePanelLegend {
    color: $accent; font-family: $font_display; font-size: $font_sm;
    font-weight: 700; letter-spacing: 2px; background: transparent;
}
QWidget#bundleUnfold { background: transparent; }

/* ==========================================================================
   DISABLED STATE - and it must stay the last block in this file.

   Qt follows CSS2 specificity, where QPushButton:disabled and
   QPushButton[someRole="true"] score exactly the same, so whichever is
   written last wins. This block used to sit two hundred lines higher with a
   comment claiming it was last; the sheet then grew past it, and the library
   tabs - added afterwards - rendered pixel-identical enabled and disabled.
   test_disabled_rules_are_the_last_word_in_the_stylesheet exists to stop that
   happening again.
   ========================================================================== */
QPushButton:disabled, QPushButton[buttonRole="primary"]:disabled,
QPushButton[buttonRole="secondary"]:disabled, QPushButton[buttonRole="ghost"]:disabled,
QPushButton[buttonRole="link"]:disabled, QPushButton[buttonRole="danger"]:disabled,
QPushButton[libraryTab="true"]:disabled, QPushButton[viewToggle="true"]:disabled,
QPushButton[savedAction="true"]:disabled, QPushButton[feedback="liked"]:disabled,
QPushButton[feedback="disliked"]:disabled, QPushButton[navItem="true"]:disabled {
    background: $surface_sunken; color: $text_disabled;
    border-color: $border_subtle;
}
/* A disabled text action must not suddenly become a grey rectangle. */
QPushButton[buttonRole="link"]:disabled {
    background: transparent; border-color: transparent; color: $text_disabled;
}
/* Nor may a disabled control keep the accent it earned by being current. */
QPushButton[libraryTab="true"]:checked:disabled,
QPushButton[viewToggle="true"]:checked:disabled,
QPushButton:checked:disabled {
    background: $surface_sunken; color: $text_disabled;
    border-color: $border_subtle;
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
