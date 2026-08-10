"""Central English UI text catalog, ready for future translation adapters."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageText:
    label: str
    description: str


@dataclass(frozen=True)
class UiTextCatalog:
    application_subtitle: str
    sidebar_footer: str
    no_active_profile: str
    active_profile_template: str
    mal_connected: str
    mal_disconnected: str
    startup_error: str
    about_description: str
    about_owner: str
    about_gui_contribution: str
    about_license: str
    about_libraries: str
    about_unofficial_notice: str
    github_link_label: str
    progress_dialog_title: str
    progress_waiting: str
    progress_working: str
    progress_counter_template: str
    progress_cancel: str
    progress_cancelling: str
    progress_cancelled: str
    progress_completed: str
    progress_close: str
    pages: tuple[PageText, ...]


UI_TEXT = UiTextCatalog(
    application_subtitle="Your personal anime recommendation desktop app",
    sidebar_footer="Desktop application",
    no_active_profile="No active profile",
    active_profile_template="Active profile: {profile_name}",
    mal_connected="MAL: Connected",
    mal_disconnected="MAL: Disconnected",
    startup_error=(
        "AniRec could not start. Please close the application and try again. "
        "If the problem continues, review the AniRec log file."
    ),
    about_description=(
        "AniRec is an open-source desktop application that turns your "
        "MyAnimeList history into explainable anime recommendations."
    ),
    about_owner="Original project owner: YusBera",
    about_gui_contribution=(
        "Desktop GUI contribution: a PySide6 interface built on the original AniRec project."
    ),
    about_license="License: GNU General Public License v3.0 (GPL-3.0)",
    about_libraries="Open-source libraries: Python, PySide6, pandas, and requests.",
    about_unofficial_notice=(
        "AniRec is an unofficial application and is not affiliated with or endorsed by "
        "MyAnimeList."
    ),
    github_link_label="AniRec on GitHub",
    progress_dialog_title="Operation progress",
    progress_waiting="Waiting to start…",
    progress_working="Working…",
    progress_counter_template="{current} of {total}",
    progress_cancel="Cancel",
    progress_cancelling="Cancelling…",
    progress_cancelled="Operation cancelled.",
    progress_completed="Operation completed.",
    progress_close="Close",
    pages=(
        PageText("Home", "Your anime activity at a glance."),
        PageText("Recommendations", "Discover anime selected from your preferences."),
        PageText("Genre Analysis", "Explore the genres that shape your anime taste."),
        PageText(
            "Advanced Operations",
            "Run individual data and recommendation operations.",
        ),
        PageText("Settings", "Manage AniRec preferences and profiles."),
        PageText("About", "Learn about AniRec and its open-source project."),
    ),
)


PROGRESS_STEP_TEXT = {
    "oauth": "Connect MyAnimeList account",
    "fetch_top": "Fetch top anime",
    "fetch_completed": "Fetch completed anime",
    "impute_scores": "Handle missing scores",
    "genre_importance": "Calculate genre importance",
    "generate_candidates": "Generate recommendation candidates",
    "generate_recommendations": "Generate recommendations",
}


@dataclass(frozen=True)
class DashboardTextCatalog:
    title: str = "Home"
    subtitle: str = "Your anime activity at a glance."
    empty_state: str = "Connect a MyAnimeList profile to start building your dashboard."
    username: str = "Active user"
    completed: str = "Completed anime"
    rated: str = "Rated anime"
    genres: str = "Genres analyzed"
    last_sync: str = "Last synchronization"
    recommendations: str = "Recommendations"
    strongest_genres: str = "Strongest genres"
    recent_recommendations: str = "Recent recommendations"
    no_genres: str = "No genre analysis yet."
    no_recommendations: str = "No recommendations yet."
    not_connected: str = "Not connected"
    never: str = "Never"
    generate: str = "Generate New Recommendations"
    sync: str = "Update MAL Data"
    open_recommendations: str = "Open Existing Recommendations"
    view_genres: str = "View Genre Analysis"
    open_folder: str = "Open Output Folder"
    profile_required: str = "Connect or select a profile first."
    sync_required: str = "Synchronize MAL data first."
    recommendations_required: str = "Generate recommendations first."
    genres_required: str = "Run genre analysis first."
    folder_required: str = "The profile output folder is not available."
    operation_running: str = "This operation is already running."


DASHBOARD_TEXT = DashboardTextCatalog()


@dataclass(frozen=True)
class WizardTextCatalog:
    title: str = "Set up AniRec"
    welcome: str = "Welcome"
    connection: str = "MyAnimeList Setup"
    api: str = "API Configuration"
    oauth: str = "MyAnimeList Connection"
    profile: str = "Profile"
    analysis: str = "Initial Analysis"
    back: str = "Back"
    next: str = "Next"
    cancel: str = "Cancel"
    finish: str = "Finish"
    open_setup: str = "Open Setup Wizard"
    required_hint: str = "Complete this step before continuing."
    welcome_body: str = (
        "AniRec uses your MyAnimeList history to build genre-based, explainable anime "
        "recommendations. Settings, profile data, and generated results stay in your local "
        "AniRec application-data folder. AniRec is an unofficial application and is not "
        "affiliated with or endorsed by MyAnimeList."
    )
    client_id: str = "Client ID"
    client_secret: str = "Client Secret (optional)"
    redirect_uri: str = "Redirect URI"
    profile_reference: str = "Profile URL or username"
    test_connection: str = "Validate and Continue"
    testing_connection: str = "Testing connection…"
    connection_success: str = "Client ID and public anime list validated."
    saved_secret: str = "A saved secret is configured. Leave blank to keep it."
    api_validation_hint: str = (
        "Enter a Client ID and a public MyAnimeList profile URL or username. "
        "After validation, AniRec will request MyAnimeList OAuth approval."
    )
    connect_mal: str = "Connect with MyAnimeList"
    cancel_connection: str = "Cancel Connection"
    oauth_ready: str = "Open MyAnimeList authorization in your browser to continue."
    oauth_opening_browser: str = "Opening your browser…"
    oauth_waiting_approval: str = "Waiting for MyAnimeList approval…"
    oauth_authorization_complete: str = "Authorization received."
    oauth_validating_token: str = "Validating the OAuth token…"
    oauth_success: str = "MyAnimeList connection completed successfully."
    oauth_cancelled: str = "MyAnimeList connection was cancelled. You can try again."
    username: str = "MyAnimeList username"
    validate_profile: str = "Validate Profile"
    validating_profile: str = "Validating profile and anime-list access…"
    profile_ready: str = "Enter the MyAnimeList username whose history AniRec should analyze."
    profile_success: str = "Profile validated successfully."
    display_username: str = "Display username"
    local_profile_id: str = "Local profile ID"
    top_anime_limit: str = "Top anime to analyze"
    recommendation_count: str = "Recommendation count"
    candidate_pool_size: str = "Candidate pool size"
    randomness_factor: str = "Randomness (1–10)"
    start_analysis: str = "Start Initial Analysis"
    cancel_analysis: str = "Cancel Analysis"
    analysis_ready: str = "Review the defaults, then create your first recommendations."
    analysis_running: str = "Initial analysis is running…"
    analysis_success: str = "Initial analysis completed. Finish setup to open your dashboard."
    analysis_cancelled: str = "Initial analysis was cancelled. No partial result was saved."
    analysis_retry: str = "Retry Initial Analysis"


WIZARD_TEXT = WizardTextCatalog()


OAUTH_STATUS_TEXT = {
    "oauth_opening_browser": WIZARD_TEXT.oauth_opening_browser,
    "oauth_waiting_approval": WIZARD_TEXT.oauth_waiting_approval,
    "oauth_authorization_complete": WIZARD_TEXT.oauth_authorization_complete,
    "oauth_validating_token": WIZARD_TEXT.oauth_validating_token,
    "oauth_success": WIZARD_TEXT.oauth_success,
}
