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
        # "Profile" rather than "Statistics": the page is a portrait of one
        # reader's taste, and naming it after the arithmetic would promise a
        # analytics screen, which is exactly what it is built not to be.
        PageText("Profile", "The shape of your taste, read off your own ratings."),
        # "Compare" rather than "Friends": the surface works on any public
        # username, and a friends list is an accelerator it can do without.
        # Naming it after the list would promise a feature that is optional.
        PageText("Compare", "How your taste lines up with someone else's."),
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
        "Or choose Next to connect your MyAnimeList account. That takes about "
        "two minutes and makes every recommendation yours."
    )
    welcome_demo: str = "Look around with sample data"
    welcome_demo_hint: str = "No account needed. Nothing is saved."
    welcome_demo_accessible: str = (
        "Explore AniRec using a bundled sample library, without connecting an account"
    )
    # Short enough to sit on one line of the status strip. The long form said
    # the same thing across two sentences and needed a banner of its own.
    demo_banner: str = "Sample data. Connect MyAnimeList to see your own picks."
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

    channel: str = "DISCOVER // 推薦"
    state_caption: str = "STATE"
    taste_caption: str = "TASTE VECTOR"
    refresh: str = "RUN ANALYSIS"
    refreshing: str = "ANALYSING…"
    refresh_accessible: str = "Update your anime list and pick new recommendations"
    # A field captioned STATE holds states, not sentences. The message
    # that used to be written here now has its own prose label beside it.
    status_ready: str = "READY"
    status_busy: str = "BUSY"
    status_fault: str = "FAULT"
    status_never_synced: str = "Connect your MyAnimeList account to get started."
    status_synced_template: str = "Last updated {when}."
    taste_show: str = "EXPAND"
    taste_hide: str = "COLLAPSE"
    # CHANGE [TASTE-SENTENCE]: one list held both genres and studios, so the
    # line read "You tend to enjoy Samurai, Bandai Namco Pictures, Parody,
    # Shaft." - a studio is not a thing you enjoy in the way a genre is, and
    # the mixture reads as a data fault even though the ranking behind it is
    # correct. The two kinds now get their own clause.
    taste_summary: str = "You tend to enjoy {genres}."
    taste_summary_studios: str = "You tend to enjoy {genres}, often from {studios}."
    taste_summary_studios_only: str = "You tend to reach for work from {studios}."
    taste_empty: str = "Your taste appears here once AniRec has seen your ratings."
    taste_none_yet: str = "nothing yet"
    taste_line: str = "{genre}: {count} you have finished"
    taste_avoid: str = "{genre}: usually not for you"


@dataclass(frozen=True)
class SettingsTextCatalog:
    """Copy for the simplified Settings surface."""

    adventurousness: str = "ADVENTUROUSNESS"
    adventurousness_hint: str = (
        "Low keeps close to what you already love. High reaches further for "
        "something unexpected."
    )
    adventurousness_low: str = "FAMILIAR"
    adventurousness_high: str = "SURPRISING"
    developer_tools: str = "DEVELOPER TOOLS"
    developer_tools_hint: str = (
        "Shows the individual data steps AniRec runs for you. Not needed for "
        "normal use."
    )



@dataclass(frozen=True)
class FilterTextCatalog:
    """Copy for the filter row, the metadata search and the profile input.

    Every sentence here names the thing it is about. "Could not load" on its
    own is the version of this that leaves a reader guessing which of five
    pills went wrong, and whether it was their typing or the network.
    """

    # ---- the pill row ----
    clear_all: str = "CLEAR ALL"
    clear_all_accessible: str = "Remove every active filter"
    pill_dismiss_accessible: str = "Remove the {label} filter {value}"
    pill_loading: str = "Loading {value}'s anime list…"
    pill_failed: str = "Could not load {value}."
    pill_retry: str = "RETRY"
    pill_retry_accessible: str = "Try loading {value} again"

    # ---- genre and studio search ----
    search_label: str = "FIND A GENRE OR STUDIO"
    search_placeholder: str = "Psychological, Shaft, Science SARU…"
    search_accessible: str = "Search genres and studios to filter the feed"
    search_suggestion: str = "{value} // {type}"
    search_no_results: str = "No matching genres or studios."
    # Naming what was typed makes it obvious the box received the input and
    # simply has nothing for it, rather than having stopped responding.
    search_no_results_for: str = (
        "No genre or studio matches “{query}” in the anime loaded so far."
    )

    # ---- group profiles ----
    profile_label: str = "ADD A FRIEND'S MAL USERNAME FOR GROUP RECOMMENDATIONS"
    profile_placeholder: str = "MyAnimeList username"
    profile_accessible: str = (
        "Add a friend's MyAnimeList username to include their taste in these "
        "recommendations"
    )
    profile_add: str = "ADD"
    profile_add_accessible: str = "Add this profile to the group recommendation"
    profile_limit: str = "Maximum 5 profiles for group recommendations."
    profile_duplicate: str = "{value} is already added."
    profile_is_you: str = "{value} is your own profile. It is always included."
    profile_invalid: str = (
        "A MyAnimeList username uses letters, numbers and underscores only."
    )
    profile_not_found: str = "No MyAnimeList user called {value}."
    profile_private: str = (
        "Could not load {value}. Their anime list may be private."
    )
    profile_unreachable: str = "Could not reach MyAnimeList for {value}."
    profile_rate_limited: str = (
        "MyAnimeList is busy right now. {value} was not loaded."
    )
    profile_failed: str = "Could not load {value}."
    profile_needs_client_id: str = (
        "Connect your MyAnimeList account in Settings to add other profiles."
    )
    profile_offline: str = "Profile lookup is not available in this session."

    # ---- group mode ----
    group_banner: str = "GROUP MODE · {count} PROFILES · {names}"
    group_banner_loading: str = "GROUP MODE · RESOLVING {count} {noun}"
    # Qt has no pluralisation and the count here is genuinely often one.
    profile_noun_one: str = "PROFILE"
    profile_noun_many: str = "PROFILES"
    group_pending: str = (
        "Group recommendations need a backend that ranks for several profiles "
        "at once. Your own feed is shown until that lands."
    )
    group_partial: str = "{count} of the added profiles could not be loaded."
    group_partial_one: str = "One added profile could not be loaded."
    group_all_failed: str = (
        "None of the added profiles could be loaded, so these are your own "
        "recommendations."
    )
    filters_empty: str = (
        "No anime match the current filters. Remove one to widen the feed."
    )


FILTER_TEXT = FilterTextCatalog()


@dataclass(frozen=True)
class CompareTextCatalog:
    """Copy for the Friends surface."""

    channel: str = "COMPARE // 相性"
    hint: str = (
        "Enter a MyAnimeList username to see how your taste lines up with "
        "theirs."
    )
    username_label: str = "MAL USERNAME"
    username_placeholder: str = "MyAnimeList username"
    username_accessible: str = "MyAnimeList username to compare against"
    username_required: str = "Enter a MyAnimeList username."
    submit: str = "COMPARE"
    submit_busy: str = "COMPARING…"
    submit_accessible: str = "Compare your anime list with this profile"
    friends_label: str = "YOUR FRIENDS"
    friends_accessible: str = "Choose a friend from your public MyAnimeList friends list"
    friends_placeholder: str = "Choose a friend…"
    # A private friends list is not an error and must not read as one: the
    # surface still works, by the route that was always there.
    friends_private: str = (
        "Your MyAnimeList friends list is not public, so it cannot be listed "
        "here. Comparing by username works as normal."
    )
    friends_empty: str = (
        "No public friends list available. Comparing by username works as "
        "normal."
    )
    friends_unavailable: str = (
        "Friends lists are not available yet. Comparing by username works as "
        "normal."
    )

    legend: str = "COMPATIBILITY"
    score_caption: str = "MATCH SCORE"
    stat_total: str = "ANIME ON THEIR LIST"
    stat_shared: str = "SHARED ANIME"
    stat_both_rated: str = "BOTH RATED"
    sample_stamp: str = "SAMPLE DATA"
    sample_stamp_tooltip: str = (
        "A bundled example comparison. Connect MyAnimeList to compare real "
        "profiles."
    )

    # ---- states ----
    idle_title: str = "Compare your taste"
    idle_message: str = (
        "Pick a friend, or type any MyAnimeList username, to see where your "
        "ratings agree and where they do not."
    )
    loading_title: str = "Reading {username}'s list"
    loading_message: str = "Fetching their ratings and lining them up with yours."
    not_found_title: str = "No such profile"
    not_found_message: str = (
        "MyAnimeList has no user called {username}. Check the spelling and "
        "try again."
    )
    private_title: str = "That list is private"
    private_message: str = (
        "{username} exists, but their anime list is not public, so there is "
        "nothing to compare against."
    )
    network_title: str = "MyAnimeList is unreachable"
    network_message: str = (
        "AniRec could not reach MyAnimeList. Check your connection and try "
        "again."
    )
    api_title: str = "MyAnimeList could not answer"
    api_message: str = (
        "The request was refused or timed out. This usually clears on its own. "
        "Try again shortly."
    )
    not_connected_title: str = "Connect your account first"
    not_connected_message: str = (
        "Comparing profiles needs a MyAnimeList Client ID. Add one in "
        "Settings, then come back."
    )
    backend_title: str = "Compatibility is not built yet"
    backend_message: str = (
        "Live compatibility is not available in this build. You can still "
        "inspect the bundled sample comparison."
    )
    backend_sample_action: str = "Show a sample comparison"
    retry: str = "Try again"
    self_compare_title: str = "That is you"
    self_compare_message: str = (
        "Comparing a list with itself always agrees. Enter someone else's "
        "username."
    )
    empty_section_default: str = "Nothing to show in this section."
    section_count: str = "{count} TITLES"
    section_count_one: str = "1 TITLE"


COMPARE_TEXT = CompareTextCatalog()


@dataclass(frozen=True)
class ProfileTextCatalog:
    """Copy for the Profile surface.

    Section headings are written as instrument legends rather than as report
    titles - "RATING DISTRIBUTION", not "Your rating distribution" - because
    the whole page is one panel and a panel labels its readouts. The sentences
    underneath are ordinary English: a legend says what a thing is, and the
    line under it says what it means.
    """

    # Keep the channel technical and legible in the bundled display face.
    # Decorative Japanese copy would be out of place here and the font does
    # not promise CJK coverage, so it can degrade into missing-glyph boxes.
    channel: str = "PROFILE // TASTE READOUT"
    hint: str = "A portrait of your taste, read off the scores you have already given."
    sample_stamp: str = "SAMPLE DATA"
    sample_stamp_tooltip: str = (
        "A bundled example profile. Connect MyAnimeList and generate "
        "recommendations to see your own figures here."
    )

    # ---- header ----
    identity_legend: str = "READER"
    member_since: str = "MAL MEMBER SINCE {year}"
    member_since_unknown: str = "MAL MEMBER SINCE N/A"
    stat_completed: str = "COMPLETED"
    stat_episodes: str = "EPISODES"
    stat_days: str = "DAYS"
    stat_mean: str = "MEAN"
    avatar_accessible: str = "{username}'s MyAnimeList avatar"
    avatar_fallback_accessible: str = "{username}, no avatar set"

    # ---- sections ----
    fingerprint_title: str = "TASTE FINGERPRINT"
    fingerprint_description: str = (
        "How your scores sit against everyone else's. None of these is a "
        "grade. They describe a reader; they do not rank one."
    )
    distribution_title: str = "RATING DISTRIBUTION"
    distribution_description: str = "Every score you have given, and how often."
    distribution_axis: str = "SCORE"
    distribution_count: str = "TITLES"
    distribution_mean: str = "MEAN"
    distribution_median: str = "MEDIAN"
    distribution_mode: str = "MODE"
    distribution_scale_usage: str = "SCALE USAGE"
    distribution_total: str = "RATED"

    hot_takes_title: str = "HOT TAKES"
    hot_takes_description: str = (
        "Where your score and the community's are furthest apart."
    )
    hot_takes_higher: str = "YOU RATED HIGHER"
    hot_takes_lower: str = "YOU RATED LOWER"
    hot_takes_empty: str = "No large disagreements on record."

    hype_killers_title: str = "HYPE KILLERS"
    hype_killers_description: str = (
        "Titles the community ranks near the top that you did not get on with."
    )
    hype_killed: str = "HYPE KILLED"
    hype_killers_biggest: str = "BIGGEST CASUALTY"
    hype_killers_empty: str = "Nothing highly ranked has been rated low."

    hidden_gems_title: str = "HIDDEN GEMS"
    hidden_gems_description: str = (
        "Little-watched titles you scored well above the room."
    )
    hidden_gem_rate: str = "HIDDEN GEM RATE"
    hidden_gems_deepest: str = "DEEPEST CUT"
    hidden_gems_empty: str = "No obscure titles rated highly yet."

    genre_title: str = "GENRE DNA"
    genre_description: str = (
        "What you watch, and how you score it. Select a genre to list the "
        "titles behind its figures."
    )
    genre_best: str = "BEST MATCH"
    genre_weakness: str = "QUESTIONABLE RELATIONSHIP"
    genre_divisive: str = "MOST DIVISIVE"
    genre_titles_heading: str = "{genre} // TITLES"
    genre_titles_empty: str = "No titles recorded for this genre."
    genre_watched: str = "WATCHED"
    genre_average: str = "AVG"

    studio_title: str = "STUDIO DNA"
    studio_description: str = "The houses you keep going back to, for and against."
    studio_most_watched: str = "MOST WATCHED"
    studio_most_trusted: str = "MOST TRUSTED"
    studio_nemesis: str = "STUDIO NEMESIS"
    studio_titles: str = "TITLES"

    era_title: str = "ERA PREFERENCES"
    era_description: str = "When the anime you finish was made, and how it scored."
    era_golden: str = "GOLDEN ERA"
    era_season_heading: str = "SEASONAL TASTE"
    era_season_scale: str = "SCALE"
    era_season_choice: str = "SEASON OF CHOICE"

    habits_title: str = "WATCHING HABITS"
    habits_description: str = "What you do with a series once you have started it."
    habits_rewatched: str = "MOST REWATCHED"

    timeline_title: str = "TASTE THROUGH TIME"
    timeline_description: str = "Your mean score, year by year."
    timeline_trend: str = "RATING TREND"
    timeline_axis_high: str = "HIGH"
    timeline_axis_low: str = "LOW"

    # ---- shared labels ----
    you: str = "YOU"
    community: str = "MAL"
    delta: str = "GAP"
    popularity: str = "POPULARITY"
    rank: str = "RANK"
    above_community: str = "ABOVE COMMUNITY"
    below_community: str = "BELOW COMMUNITY"

    # ---- states ----
    section_error: str = "UNABLE TO LOAD {section}"
    section_error_message: str = (
        "This part of your profile could not be read. The rest of the page is "
        "unaffected."
    )
    section_retry: str = "RETRY"
    section_empty: str = "Not measured yet."
    loading_title: str = "Reading your list"
    loading_message: str = (
        "Counting scores, lining them up against the community, and working "
        "out what that says about you."
    )
    backend_title: str = "Your taste profile is not built yet"
    backend_message: str = (
        "Live profile statistics are not available in this build. You can "
        "still inspect the bundled sample profile."
    )
    backend_sample_action: str = "Show a sample profile"
    not_connected_title: str = "Connect your account first"
    not_connected_message: str = (
        "A taste profile is read from your MyAnimeList history. Add a Client "
        "ID in Settings and sync your list, then come back."
    )
    network_title: str = "MyAnimeList is unreachable"
    network_message: str = (
        "AniRec could not reach MyAnimeList. Check your connection and try "
        "again."
    )
    api_title: str = "MyAnimeList could not answer"
    api_message: str = (
        "The request was refused or timed out. This usually clears on its own. "
        "Try again shortly."
    )
    private_title: str = "Your list is private"
    private_message: str = (
        "AniRec can only read a public list. Make yours public on "
        "MyAnimeList, then try again."
    )
    empty_title: str = "Nothing to read yet"
    empty_message: str = (
        "A taste profile needs scored anime. Rate a few titles on "
        "MyAnimeList, sync, and this page fills in."
    )
    retry: str = "Try again"


PROFILE_TEXT = ProfileTextCatalog()

DISCOVER_TEXT = DiscoverTextCatalog()
SETTINGS_TEXT = SettingsTextCatalog()
