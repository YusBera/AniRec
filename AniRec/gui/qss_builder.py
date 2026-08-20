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
    from .design_tokens import FONT_STACK, RADIUS, TYPE_SCALE, palette
except ImportError:  # Compatibility with the sibling import path used by tests.
    from design_tokens import FONT_STACK, RADIUS, TYPE_SCALE, palette


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
QToolTip {
    background: $surface_raised; color: $text; border: 1px solid $border_strong;
    border-radius: ${radius_sm}px; padding: 6px;
}

QFrame#sidebar {
    background: $sidebar;
    border-right: 1px solid $border_subtle;
}
QFrame#sidebar QPushButton { text-align: left; padding: 10px 13px; }
QLabel#sidebarTitle, QLabel#pageTitle {
    color: $text_strong; font-size: $font_2xl; font-weight: 700;
}
QLabel#pageDescription, QLabel#sidebarFooter { color: $text_muted; }
QFrame#connectionStatusBar { background: transparent; border: none; }
QLabel#activeProfileLabel {
    background: $surface; color: $text; border: 1px solid $border;
    border-radius: 11px; padding: 7px 11px; font-weight: 600;
}
QLabel#malConnectionLabel {
    background: $danger_bg; color: $danger_text; border: 1px solid $danger_border;
    border-radius: 9px; padding: 4px 10px; font-weight: 600;
}
QLabel#malConnectionLabel[connected="true"] {
    background: $success_bg; color: $success_text; border-color: $success_border;
}

QPushButton {
    background: $surface_raised;
    border: 1px solid $border_strong;
    border-radius: 9px;
    color: $text;
    padding: 8px 12px;
    text-align: center;
    font-weight: 600;
}
QPushButton:hover { background: $surface; border-color: $accent; }
QPushButton:pressed { background: $surface_sunken; }
QPushButton:focus { border: 2px solid $focus; }
QPushButton:checked { background: $accent; border-color: $accent_hover; color: $accent_contrast; }
QPushButton:disabled { background: $surface_sunken; color: $text_disabled; border-color: $border_subtle; }
QPushButton[buttonRole="primary"] {
    background: $accent; border-color: $accent_hover; color: $accent_contrast;
}
QPushButton[buttonRole="primary"]:hover { background: $accent_hover; border-color: $accent_hover; }
QPushButton[buttonRole="secondary"] { background: $surface; border-color: $border_strong; }
QPushButton[buttonRole="ghost"] { background: transparent; border-color: $border; color: $text_muted; }
QPushButton[buttonRole="link"] {
    background: transparent; border-color: transparent; color: $accent_soft;
    padding: 4px 2px; text-align: left;
}
QPushButton[buttonRole="link"]:hover { color: $accent_hover; background: transparent; }
QPushButton[buttonRole="danger"] { background: $danger_bg; border-color: $danger_border; color: $danger_text; }
QPushButton[feedback="liked"]:checked {
    background: $success_bg; border-color: $success_border; color: $success_text;
}
QPushButton[feedback="disliked"]:checked {
    background: $danger_bg; border-color: $danger_border; color: $danger_text;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {
    background: $surface_sunken;
    color: $text;
    border: 1px solid $border;
    border-radius: 8px;
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
}
QMenu {
    background: $surface_raised; color: $text; border: 1px solid $border;
    border-radius: 9px; padding: 6px;
}
QMenu::item { padding: 8px 28px 8px 12px; border-radius: 6px; }
QMenu::item:selected { background: $accent; color: $accent_contrast; }
QCheckBox { spacing: 8px; color: $text; }
QCheckBox::indicator {
    width: 17px; height: 17px; border: 1px solid $border_strong; border-radius: 5px;
    background: $surface_sunken;
}
QCheckBox::indicator:checked { background: $accent; border-color: $accent_hover; }

QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: $border_strong; border-radius: 5px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: $text_subtle; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal { background: transparent; height: 10px; }
QScrollBar::handle:horizontal { background: $border_strong; border-radius: 5px; min-width: 30px; }

QProgressBar {
    background: $surface_sunken; border: 1px solid $border; border-radius: 6px;
    color: $text; min-height: 12px; text-align: center;
}
QProgressBar::chunk { background: $accent; border-radius: 5px; }
QDialog#operationProgressDialog {
    background: $surface; border: 1px solid $border; border-radius: ${radius_xl}px;
}
QLabel#progressStepLabel { color: $text_strong; font-size: $font_lg; font-weight: 700; }
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

QFrame#dashboardMetricCard, QFrame#dashboardPanel, QFrame[metricCard="true"] {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
}
QLabel#dashboardMetricLabel, QLabel#dashboardActionReason { color: $text_muted; }
QLabel#dashboardMetricValue { color: $text_strong; font-size: $font_xl; font-weight: 700; }
QLabel#dashboardSectionTitle { color: $text_strong; font-size: $font_lg; font-weight: 700; }
QLabel#dashboardEmptyState {
    background: $warning_bg; border: 1px solid $warning_border; border-radius: 10px;
    color: $warning_text; padding: 10px 12px;
}
QLabel#dashboardActivity {
    background: $surface_raised; border: 1px solid $border; border-radius: 10px;
    color: $text_muted; padding: 6px 11px; font-weight: 600;
}
QLabel#dashboardActivity[tone="success"] { background: $success_bg; border-color: $success_border; color: $success_text; }
QLabel#dashboardActivity[tone="busy"] { background: $busy_bg; border-color: $busy_border; color: $busy_text; }
QLabel#dashboardActivity[tone="error"] { background: $danger_bg; border-color: $danger_border; color: $danger_text; }
QLabel#dashboardGenreName { color: $text; font-weight: 600; }
QLabel#dashboardGenreScore { color: $accent_soft; font-weight: 700; }
QProgressBar#dashboardGenreBar { min-height: 9px; max-height: 9px; border: none; background: $surface_sunken; }
QFrame[homeRecommendationCard="true"] {
    background: $surface; border: 1px solid $border; border-radius: 12px;
}
QFrame[homeRecommendationCard="true"]:hover { border-color: $accent; background: $surface_raised; }
QLabel#homeRecommendationCover { background: $well; border-radius: 8px; }
QLabel#homeRecommendationTitle { color: $text_strong; font-size: $font_sm; font-weight: 700; }
QLabel#homeRecommendationScore { color: $accent_soft; font-weight: 700; }
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
QFrame#recommendationHero {
    background: $gradient_hero;
    border: 1px solid $border; border-radius: ${radius_xl}px;
}
QLabel#recommendationEyebrow, QLabel#recommendationActionCaption {
    color: $accent; font-size: $font_xs; font-weight: 800;
}
QLabel#recommendationHeroTitle { color: $text_strong; font-size: $font_4xl; font-weight: 800; }
QLabel#recommendationHeroDescription { color: $text_muted; font-size: $font_sm; }
QFrame#recommendationControls, QTableWidget {
    background: $surface; border: 1px solid $border; border-radius: 12px;
}
QFrame#recommendationControls { padding: 4px; }
QLabel#recommendationFeedbackSummary {
    background: $surface_raised; border: 1px solid $border; border-radius: 10px;
    color: $text; padding: 8px 11px; font-weight: 600;
}
QFrame#recommendationLibraryBar {
    background: $surface_sunken; border: 1px solid $border; border-radius: 15px;
}
QPushButton[libraryTab="true"] {
    background: transparent; border: 1px solid transparent; border-radius: 10px;
    color: $text_muted; padding: 9px 15px; font-weight: 700;
}
QPushButton[libraryTab="true"]:hover { background: $surface_raised; color: $text_strong; }
QPushButton[libraryTab="true"]:checked {
    background: $accent_muted; border-color: $accent; color: $text_strong;
}
QPushButton[viewToggle="true"] { padding: 8px 11px; }
QFrame#recommendationSelectedActions {
    background: $surface; border: 1px solid $border; border-radius: 12px;
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
QLabel#recommendationEmptyTitle { color: $text_strong; font-size: $font_2xl; font-weight: 800; }
QLabel#recommendationEmptyState { color: $text_muted; font-size: $font_md; }
QLabel#personalMatchLabel { color: $accent_soft; font-size: $font_lg; font-weight: 700; }
QLabel#recommendationTitle { color: $text_strong; font-size: $font_md; font-weight: 700; }
QLabel#recommendationSecondaryTitle, QLabel#recommendationMeta { color: $text_muted; }
QLabel#recommendationGenres { color: $text; }
QLabel#recommendationReason { color: $text_muted; }
QLabel#recommendationCover { background: $well; border-radius: 10px; }
QPushButton[savedAction="true"]:checked {
    background: $saved_bg; border-color: $saved_border; color: $saved_text;
}
QHeaderView::section {
    background: $surface_sunken; color: $text_muted; border: none;
    border-bottom: 1px solid $border; padding: 8px; font-weight: 600;
}
QTableWidget { gridline-color: $border; selection-background-color: $selection; }

QGroupBox[settingsCard="true"] {
    background: $surface; border: 1px solid $border; border-radius: ${radius_lg}px;
    margin-top: 12px; padding: 18px 14px 14px 14px; font-weight: 700;
}
QGroupBox[settingsCard="true"]::title {
    subcontrol-origin: margin; left: 14px; padding: 0 7px; color: $text_strong;
}
QLabel#settingsStatus, QLabel#settingsApiStatus, QLabel#settingsDataScopeHint { color: $text_muted; }
QLabel#settingsStatus[error="true"] { color: $danger_text; }

QLabel#recommendationDetailTitle { color: $text_strong; font-size: $font_2xl; font-weight: 700; }
QLabel#recommendationDetailSecondaryTitle, QLabel#recommendationDetailAlternatives { color: $text_muted; }
QLabel#recommendationDetailSectionTitle { color: $text_strong; font-size: $font_md; font-weight: 700; }
QFrame#genreBarsFrame, QTableWidget#genreAnalysisTable, QFrame[advancedOperation="true"] {
    background: $surface; border: 1px solid $border; border-radius: 12px;
}
QLabel#genreAnalysisEmptyState, QLabel#genreImportanceExactScore,
QLabel#advancedOperationDescription, QLabel#advancedOperationPrerequisite,
QLabel#advancedOperationLastRun { color: $text_muted; }
QLabel#advancedOperationTitle { color: $text_strong; font-size: $font_md; font-weight: 700; }
QLabel#errorDialogTitle { color: $text_strong; font-size: $font_xl; font-weight: 700; }
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
) -> str:
    """Render the stylesheet for a theme at a given font scale."""
    colours = palette(theme)
    base = base_point_size if base_point_size > 0 else DEFAULT_BASE_POINT_SIZE
    values = dict(colours)
    values["theme_name"] = str(theme).strip().casefold()
    values["font_stack"] = FONT_STACK
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
