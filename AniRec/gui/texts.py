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
        PageText("Discover", "Anime picked for you, and the taste behind them."),
        PageText("My Library", "Everything you have loved, saved, or passed on."),
        PageText("Settings", "Your account, how AniRec picks, and your data."),
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
    welcome_connect_hint: str = (
        "Connecting your MyAnimeList account takes about two minutes and "
        "gives you recommendations built from your own ratings."
    )
    welcome_demo: str = "Look around with sample data"
    welcome_demo_hint: str = "No account needed. Nothing is saved."
    welcome_demo_accessible: str = (
        "Explore AniRec using a bundled sample library, without connecting an account"
    )
    demo_banner: str = (
        "You are looking at sample data. Connect your MyAnimeList account to "
        "get recommendations built from your own ratings."
    )
    demo_banner_action: str = "Connect my account"
    client_id: str = "Client ID"
    client_secret: str = "Client Secret"
    redirect_uri: str = "Redirect URI"
    profile_reference: str = "Profile URL or username"
    test_connection: str = "Validate and Continue"
    testing_connection: str = "Testing connection…"
    connection_success: str = "Client ID and public anime list validated."
    saved_secret: str = "A saved secret is configured. Leave blank to keep it."
    api_validation_hint: str = (
        "Fill in the values above, then choose Validate and Continue. "
        "AniRec will check them and ask MyAnimeList for your permission."
    )
    # First-run guidance. A new user has no reason to know what any of this
    # means, so the wizard explains the terms and links straight to the page
    # where the values come from.
    api_intro: str = (
        "AniRec reads your anime list through MyAnimeList's official API. "
        "MyAnimeList asks you to register AniRec once, which takes about two "
        "minutes and gives you the two values below."
    )
    api_steps: str = (
        "1. Open the MyAnimeList API page and choose Create ID.\n"
        "2. Give it any name, for example \"AniRec\", and pick Other for the "
        "app type.\n"
        "3. Paste the Redirect URI shown below into the App Redirect URL field.\n"
        "4. Save, then copy the Client ID and Client Secret back here."
    )
    api_link_label: str = "Open the MyAnimeList API page"
    client_id_hint: str = (
        "A long code MyAnimeList gives you when you register AniRec. It is not "
        "your password and it is stored only on this computer."
    )
    client_secret_hint: str = (
        "Shown next to the Client ID on the same page. Required for the "
        "connection step to succeed."
    )
    redirect_uri_hint: str = (
        "MyAnimeList requires this exact value in the App Redirect URL field. "
        "Copy it across without changing it."
    )
    copy_redirect_uri: str = "Copy"
    copied_redirect_uri: str = "Copied"
    oauth_missing_secret_hint: str = (
        "No Client Secret is saved. If MyAnimeList keeps refusing the "
        "connection, go back one step and paste the Client Secret shown "
        "beside your Client ID on the MyAnimeList API page."
    )
    connect_mal: str = "Connect with MyAnimeList"
    cancel_connection: str = "Cancel Connection"
    oauth_ready: str = (
        "AniRec will open MyAnimeList in your browser so you can approve access. "
        "Your password is never shared with AniRec."
    )
    oauth_opening_browser: str = "Opening your browser…"
    oauth_waiting_approval: str = "Waiting for MyAnimeList approval…"
    oauth_authorization_complete: str = "Authorization received."
    oauth_validating_token: str = "Finishing the connection…"
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


@dataclass(frozen=True)
class DiscoverTextCatalog:
    """Copy for the Discover surface. Plain language, no pipeline vocabulary."""

    refresh: str = "Get new recommendations"
    refreshing: str = "Finding anime for you…"
    refresh_accessible: str = "Update your anime list and pick new recommendations"
    status_ready: str = "Ready when you are."
    status_never_synced: str = "Connect your MyAnimeList account to get started."
    status_synced_template: str = "Last updated {when}."
    taste_show: str = "Why these?"
    taste_hide: str = "Hide"
    taste_summary: str = "You tend to enjoy {genres}."
    taste_empty: str = "Your taste appears here once AniRec has seen your ratings."
    taste_none_yet: str = "nothing yet"
    taste_line: str = "{genre}: {count} you have finished"
    taste_avoid: str = "{genre}: usually not for you"


@dataclass(frozen=True)
class SettingsTextCatalog:
    """Copy for the simplified Settings surface."""

    adventurousness: str = "Adventurousness"
    adventurousness_hint: str = (
        "Low keeps close to what you already love. High reaches further for "
        "something unexpected."
    )
    adventurousness_low: str = "Familiar"
    adventurousness_high: str = "Surprising"
    developer_tools: str = "Developer tools"
    developer_tools_hint: str = (
        "Shows the individual data steps AniRec runs for you. Not needed for "
        "normal use."
    )


DISCOVER_TEXT = DiscoverTextCatalog()
SETTINGS_TEXT = SettingsTextCatalog()
