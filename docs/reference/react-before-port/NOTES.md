# React (current) — UI notes

Captured against the isolated instance: React dev server on http://127.0.0.1:5174,
API on port 8771, empty scratch data root → the app serves labelled sample data
(8 titles, no real profile). Port 5173/8770 (the user's real profile) was never
opened or interacted with.

## Global layout & navigation

- CSS grid shell: `.workspace { grid-template-columns: 214px minmax(0,1fr) }`.
  Left sidebar is fixed 214px (170px at a narrower breakpoint), `position: sticky`,
  full viewport height, background `--sidebar` (#050907), right border 1px
  `--border`.
- Sidebar top block "ANIREC" (wordmark, 20px display font, bold/800, letter-spacing
  .1em) with a Japanese subtitle "アニレク" underneath in small muted text.
- Main nav below the brand block: 5 links, each `01 Discover`, `02 My Library`,
  `03 Profile`, `04 Compare`, `05 Settings` — a 2-digit index rendered before the
  label, plus a small mask-icon glyph. Active route gets a 2px left accent border,
  accent-colored text, and a slightly raised background (`aria-current="page"`).
  Routing is hash-based and client-side (`#/discover`, `#/library`, `#/profile`,
  `#/compare`, `#/settings`) — no server-side route needed, so each is directly
  linkable.
- A visually-hidden "Skip to content" link precedes the sidebar for keyboard
  users; a second "Skip to recommendations" link exists inside the Discover page.
- At the mobile breakpoint the sidebar becomes a horizontal top bar: brand row
  collapses to a single line (subtitle and nav index hidden), and the nav becomes
  a 5-column CSS grid (one column per page) with icon-over-label buttons, ≥44px
  tall, bottom-border indicating the active tab instead of a left border.
  Verified with `getBoundingClientRect()` at 375px width: all five nav links sum
  to exactly 375px (Settings right edge = 371px) — no horizontal overflow or
  scrolling in the live app.
- Page content area (`.workspace-content`) has no fixed max-width for Discover;
  `.workspace-page` (Library/Profile/Compare/Settings) caps at `max-width: 1500px`,
  centered, with 30px/34px padding (24px/16px at mobile).
- There is no separate first-run/onboarding screen in the web client today: with
  no profile connected, the Discover route itself renders directly with the
  bundled sample library and an orange "SAMPLE DATA" tag in the page header. The
  `needs_setup` field exists in the generated API schema but nothing in
  `frontend/src` currently reads it — it is unused dead schema, not a rendered
  state.

## Discover — page

- Page header: `<h1>Discover</h1>` plus a tag row. With sample data, one tag is
  shown: `SAMPLE DATA` (styled as a warning pill, uppercase, orange border).
  When a real profile/engine were active, additional tags (`{username}` and an
  `Engine · Working/Loading/Unavailable` status with a status LED dot) would
  appear in the same row — not observed live here since this instance has no
  profile and is not busy.
- A dotted horizontal rule strip (`.ticks`) sits directly under the header.
- `<details class="filter-drawer">` — collapsed by default. Summary text:
  `Filters & sort` followed by a small label `0 ACTIVE · PERSONAL FIT` (active
  filter count · current sort mode, uppercase via CSS).
- Status bar row: a status LED dot, then `<b>8</b> of 8 shown` (visible-count of
  total, plus "· N hidden" when any are set aside), a spacer, and on the right a
  primary button `Recommend 5 more` — disabled on this ephemeral sample feed,
  with title-tooltip "Personal recommendations require a connected profile;
  connection is not available in this browser build yet." While an operation
  runs this button is replaced by `Cancel` plus a progress line; not observed
  live (no operation is running against a profile-less sample feed).
- Feed notices block below the status bar:
  - Sample data note (ephemeral only): "Sample library. Decisions reset on
    reload. Personal picks need a connected profile; connection is not
    available in this browser build yet."
  - A `role="status"` feedback line that carries transient text such as
    "{Title} saved for later in this preview. Changes reset on reload."
  - A "Recommendation activity" `<details>` (hidden entirely for ephemeral
    feeds — not present here) with an opt-in checkbox "Save activity on this
    device" and a "Clear saved activity" pill.
- `<section id="recommendations">` holds the feed grid, then a `PageControls`
  nav ("Previous page" / "Showing 1–20 of N recommendations · Page X of Y" /
  "Next page") which is omitted entirely when there are ≤20 items — true for
  this 8-item sample feed, so no pagination UI is visible on Discover. (My
  Library paginates the same way at `PAGE_SIZE = 20`.)
- Feed grid (`.feed`): CSS grid, `grid-template-columns: repeat(auto-fill,
  minmax(min(100%, 232px), 1fr))`, `gap: var(--space-md)` (12px). At 1440px
  width this renders 4 columns of 8 cards (2 rows); at 375px it is a single
  column.
- Clicking a card's poster, title, "Details" pill, or "Why this pick" all open
  the same modal (`<dialog class="details-dialog">`, native `showModal()`),
  described below under "Card interactions".

## Recommendation card anatomy

Source: `frontend/src/discover/RecommendationCard.tsx` +
`frontend/src/discover/discover.css`. Measured live via `getBoundingClientRect`
at 1440×900 (first card, "Death Note", no operation running, filters closed):

- Card outer box: **287.75px × 621.25px** (`.feed` grid cell; height is uniform
  because `.card { height: 100%; }` fills its row — a CSS comment on this rule
  says the row-uniformity behavior is deliberately covered by
  `test_card_grid_geometry.py`).
- Card is a flex column (`display:flex; flex-direction:column`), 1px `--border`
  outline, `--gradient-card` background (top-to-bottom dark gradient), no
  rounding beyond the token system's near-zero radii.
- Poster block (`.card-art`): **fixed 152px × 228px**, exact **2:3** portrait
  ratio (0.6667), `align-self: center` inside the flex column, `margin: 8px 0 0`.
  No `<img>` element rendered in the sample data (no `cover_url`), so only the
  placeholder layer paints. Empty horizontal space beside the poster, measured
  from the card's own left/right edges: **67.875px on each side** (poster is
  centered inside a wider card, not full-bleed).
  - When artwork does exist, `.card-art img` is `position:absolute; inset:0;
    width/height:100%; object-fit:contain` painted over the placeholder (the
    placeholder is intentionally kept underneath rather than swapped out — a
    CSS comment explains this mirrors a documented Qt-side artwork bug fixed
    from the opposite direction).
- Placeholder content (`.placeholder`, absolutely filling `.card-art`):
  initials in large text (`<b>`, 3.7rem) + "No artwork" caption underneath,
  centered.
- `.card-rank`: small `#N` badge, absolute top-left of the poster.
- `FitIndicator` (`.fit-indicator`): absolute-positioned bar pinned to the
  *bottom* of the poster (`inset: auto 0 0`), full width, ≥44px tall, its own
  1px top border, itself a `<button>` — this is what shows the "Personal fit"
  label + value + "Why this pick" link-styled text, and is one of the several
  ways to open the details dialog.
- DOM child order inside `<article class="card">` (confirmed by
  `[...card.children]` at runtime):
  1. `div.card-art` → button (`Inspect {title}`, invisible full-cover hit
     target) with the placeholder/image inside; `#N` rank badge; the
     `fit-indicator` button (Personal fit / value / "Why this pick").
  2. `div.card-body` → title button (`<h2><button>`), secondary/native title
     line (non-breaking space if empty), sentiment group (Like / Dislike
     buttons + "Saved for evaluation only; votes do not change recommendations
     yet." note), decision group (Save for later / Set aside buttons, plus a
     conditional "Set aside. Excluded from future feeds." line when hidden),
     tag row (studio tags then genre tags, separately styled), meta row (year,
     episode count, status — items whose text says "not available" are
     filtered out entirely rather than shown), MAL score line
     ("MAL score: 8.62 / 10", or "not rated"), and a utilities row (`Details`
     pill + `MyAnimeList ↗` external link).
- Exact strings on card #1 in this sample set: title **"Death Note"**; tags
  **Madhouse** (studio) · **Supernatural · Suspense · Psychological · Thriller**
  (genres); meta **"2006 37 episodes Finished Airing"**; **"MAL score: 8.62 /
  10"**.

## Card interactions

- Poster / title / "Details" pill / "Why this pick" bar all call the same
  `onDetails` handler, opening `<dialog class="details-dialog">`
  (`RecommendationDetails.tsx`) via the native `showModal()` API (real focus
  trap, Escape-to-close, return-to-invoker for free).
- Dialog structure, top to bottom: header row with label "Recommendation
  inspector" and a `Close` button (autofocused); `<h2>` title; optional
  secondary/native title; a "Personal fit" label/value line; then a two-column
  grid with **"Why this pick"** (an `<h3>` + `WhyExplanation`) beside **"About
  this title"** (`<h3>` + a `<dl>` of Genres / Studio / Released / Episodes /
  Status / MAL score, then a synopsis paragraph, then the MyAnimeList link).
  Observed live for "Death Note": Personal fit **"Personal fit unavailable"**;
  Why-this-pick body is the `UnavailableExplanation` state — heading **"This
  pick can't be explained"**, body **"No explanation was recorded for this
  pick."** (the sample engine records no `why`, so `method === "unavailable"`
  for every sample card).
  - Not observed live (no engine/profile attached to this instance), but
    present in code and worth noting for a desktop comparison: an
    `exact-additive` explanation (heuristic engine) renders a ranking-score
    total, a positive/negative `ImpactBar`, and expandable per-segment
    `<details>` rows with rated-title counts and per-title evidence; a
    `counterfactual-removal` explanation (sequence/ONNX engine) instead reruns
    the model with slices of history removed and shows relative rank-change
    effects plus a "Strongest individual history effects" list. Both are typed
    unions in `frontend/src/api/types.ts`-derived models, never blended.
  - Personal fit value, when available, is a rank string:
    `#{fit_rank} of {fit_pool_size} · {engine label}` (engine label
    "sequence model" / "heuristic" / raw id) — never a percentage.
- **Like / Dislike** (`.card-sentiment`) — two toggle buttons under the title,
  `aria-pressed` state, with a fixed caption underneath: "Saved for evaluation
  only; votes do not change recommendations yet." These are optimistic +
  rollback (see `DiscoverPage.tsx` `saveSentiment`); on this ephemeral sample
  feed a vote is held in local React state only and the caption becomes
  "{title}: liked/disliked in this preview. Changes reset on reload."
- **Save for later / Set aside** (`.card-actions`) — the two decision buttons;
  same optimistic/ephemeral behavior, feedback text "{title} saved for later in
  this preview. Changes reset on reload." (confirmed live — see note below on
  an accidental trigger). A hidden/"set aside" card additionally shows "Set
  aside. Excluded from future feeds." and its card border switches to the
  danger/red border color (`.card[data-hidden="true"]`).
  - Caution note for future captures: clicking the "Why this pick" element by a
    stale accessibility-tree ref (`ref_N`) after any DOM/page change can
    resolve to the wrong element — this happened once during this session and
    toggled "Save for later" on Steins;Gate. It was caught immediately (the
    feedback line names the affected title) and cleared with `location.reload()`
    before any further capture; no card was left in a modified state in the
    final screenshots. Re-reading the accessibility tree immediately before
    each click avoided a repeat.
- No inline score/percentage is ever computed client-side; every value on the
  card traces to `RecommendationViewModel` fields from the API.

## Filters & sort

`Controls.tsx`, opened via the `<details class="filter-drawer">` on Discover.
Three-column layout at desktop width:
- **Genre** — collapsible sub-`<details>`, summary "▸ GENRE — 13 options · 0
  selected"; expands to a wrapped row of pill toggle-buttons (Action, Adventure,
  Avant Garde, Award Winning, Drama, Fantasy, Mystery, Psychological, Romance,
  Sci-Fi, Supernatural, Suspense, Thriller — the set found in this sample's 8
  titles).
- **Studio** — same pattern, "▸ STUDIO — 7 options · 0 selected" (CoMix Wave
  Films, Gainax, Kyoto Animation, Madhouse, Studio Ghibli, Toei Animation, White
  Fox).
- **Minimum MAL score** — a `type="range"` slider, label "MINIMUM MAL SCORE",
  current value shown as "ANY", scale ticks 0/5/10 underneath.
- **Sort** — 4 pill buttons: `Personal fit` (selected/accent by default),
  `MAL score`, `Year`, `Title`.
Selecting any filter updates the summary's "N active" count and resets Discover
to page 1 (`setPage(0)`).

## My Library

Route `#/library`, rendered by `LibraryPage.tsx` inside the same `DiscoverPage`
component tree (shares its feed/vote state), but as a separate workspace page.
- `<h1>My Library</h1>` + intro "Saved recommendation decisions, with the
  evidence attached." + (sample data) "Sample data. Decisions reset on reload."
- Two count tabs: `WATCH LATER · 0` (accent/selected by default) and `NOT
  INTERESTED · 0`.
- A toolbar: "Find a saved title" text input, and a "View" `<select>` (only
  option visible in this state: `Cards`).
- Section heading "Saved for later" with a "0 matching" count.
- Empty state (no saved titles in this fresh sample session): heading "Your
  Watch Later list is empty", body "Choose a title in Discover to add this
  collection.", button "Explore Discover".

## My Profile

Route `#/profile`, `ProfilePage.tsx`.
- `<h1>Profile</h1>` + intro "A portrait of your taste, read off the scores you
  have already given."
- Two pill buttons: `LOCAL PROFILE` (selected by default, accent) and `VIEW
  SAMPLE PROFILE`.
- Default (Local profile) empty/unavailable state: heading "Profile data
  unavailable", body "Profile connection is not available in this browser
  build. You can explore the sample profile above.", button "Reload profile".
  (The sample-profile alternate view was not opened — out of scope for
  "default state".)

## Compare

Route `#/compare`, `ComparePage.tsx`.
- `<h1>Compare</h1>` + intro "See how two readers' interests and ratings line
  up."
- An info panel: "Compare your synchronized completed list with a public MAL
  completed list. A compatibility percentage is not calculated. The NSFW
  preference controls which titles MAL returns." — an explicit statement that
  match percentages are not fabricated here either.
- Form: label "MAL username" + text input + button "Compare completed lists".
- Secondary button: "Explore sample comparison" (not opened — default state
  only).
- Status line: "Enter a MAL username to compare."

## Settings

Route `#/settings`, `SettingsPage.tsx`.
- `<h1>Settings</h1>` + intro "Set your recommendation defaults. Desktop-only
  controls are available below."
- "Recommendation" section: Adventurousness (1–10) number input (default 5),
  Batch size number input (default 10), "Minimum MAL score (blank for any)"
  number input (empty by default), "Default sort" select (`Personal fit` /
  `MAL score` / `Year` / `Alphabetical`), two checkboxes ("Include Not
  interested", "Include NSFW anime").
- Collapsed `<details>` "Desktop-only settings" with an explanatory line
  ("These controls affect the desktop app only. This browser keeps its current
  dark appearance.") — not expanded for this capture, but its fields per source
  are: Desktop background sync checkbox, Theme select (system/dark/light/oled/
  gradient), GUI scale, Font scale, "Show anime covers" checkbox.
- Toolbar: `Save preferences` / `Discard edits` buttons (both disabled — "No
  unsaved edits" — until a field is changed) and a live "No unsaved edits" /
  "Unsaved edits" status text.
- "Account and local data" section: "Active profile: {username or None}. MAL
  Client ID: Configured/Not configured." plus "Connection has not been tested
  here. Profile connection and local data tools are not available in this
  browser build."

## First-run, empty and sample states

- There is no dedicated onboarding/setup screen in the web client. With an
  empty data root the app boots straight into Discover with the bundled
  8-title sample library and an orange `SAMPLE DATA` tag — this *is* the
  effective first-run state today.
- Every page that needs a real profile instead shows an explicit unavailable
  message rather than blank content or a fabricated number: Discover disables
  "Recommend 5 more" with an explanatory tooltip; My Profile says "Profile data
  unavailable … Profile connection is not available in this browser build";
  Compare requires a MAL username and states no compatibility percentage is
  computed; votes/decisions on the sample feed are explicitly labelled
  "in this preview. Changes reset on reload."
- Generic empty-state copy (`discover/states.tsx`, not hit directly in this
  8-item sample but present in code): no-filter-match state heading "Nothing to
  show yet" / body "Run an analysis to generate recommendations from your
  MyAnimeList history."; filtered-to-zero state heading "No titles match these
  filters" / body "Every recommendation in the feed was excluded by the active
  filters." with a "Clear filters" button.

## Language & tone

Quoted exactly as rendered:
- "SAMPLE DATA" (header tag)
- "Filters & sort", "0 ACTIVE · PERSONAL FIT"
- "8 of 8 shown", "Recommend 5 more"
- "Sample library. Decisions reset on reload. Personal picks need a connected
  profile; connection is not available in this browser build yet."
- "Saved for evaluation only; votes do not change recommendations yet."
- "Personal fit unavailable"
- "Why this pick"
- "This pick can't be explained" / "No explanation was recorded for this pick."
- "Save for later" / "Set aside" / "Set aside. Excluded from future feeds."
- "MAL score: 8.62 / 10" (never shown as a bare "8.62" or percentage)
- "Your Watch Later list is empty" / "Choose a title in Discover to add it to
  this collection."
- "Profile data unavailable" / "Profile connection is not available in this
  browser build. You can explore the sample profile above."
- "A compatibility percentage is not calculated." (Compare page)
- "This browser keeps its current dark appearance." (Settings)
- Personal fit, when computable, is phrased as a rank ("#N of M · engine"), not
  a percentage — no UI string in this codebase presents an uncalibrated score
  as "% match".

## Visual language

- Dark-only palette (`frontend/src/styles/tokens.css`, generated from
  `AniRec/gui/design_tokens.py`): near-black greens/olives — `--bg #070C09`,
  `--sidebar #050907`, `--surface #0C1410`, body text `--text #C6D4C2` on that
  ground. Accent is a warm gold `--accent #D9A441` (hover `#E8B85C`) used for
  active nav, selected pills, primary emphasis. A second accent, teal
  `--focus #5FBFB5`, is used for focus rings and some secondary "saved" states.
  Semantic colors: success green, danger red-orange (`#D98363` on `#241110`),
  warning amber (`#E08A43` on `#241609`).
- Typography: three stacks — `--font-sans` for body copy (Yu Gothic UI / Meiryo
  UI / Segoe UI Variable / Noto Sans CJK JP fallbacks), `--font-display` for
  headings/brand/nav (Martian Mono / Bahnschrift / Segoe UI Variable Display —
  a monospaced/condensed display face), `--font-mono` for numeric/tabular
  values (IBM Plex Mono / Cascadia Mono / Consolas). All-caps, letter-spaced
  micro-labels (e.g. "PERSONAL FIT", "SAMPLE DATA", filter drawer summary) are
  a recurring pattern.
- Density: compact — 12px base UI text in the sidebar, 8–12px internal
  paddings/gaps (`--space-sm`/`--space-md` = 8/12px), ≥44px minimum touch
  targets enforced via CSS at coarse-pointer/narrow breakpoints on buttons,
  pills and links.
- Shapes: almost square. `--radius-sm..xl` run 0px/1px/2px/3px — visually
  borders and hairline rules do essentially all of the separating, not
  rounding or shadow. Cards use a very subtle 180°-linear top-to-bottom
  gradient (`--gradient-card`, #101A14 → #0A120E) rather than a flat fill.
- A recurring "terminal/HUD" motif: a `.ticks` dotted rule strip under the
  Discover header, monospace numeric labels, uppercase micro-labels, status LED
  dots (`.led`) next to busy/engine-state text.

## Screenshots index

All captured at the isolated instance (127.0.0.1:5174 / API :8771), never on
port 5173/8770.

| File | State |
| --- | --- |
| `01-discover-sample-1440.png` | Discover, sample data, default filters/sort, 1440×900 (Edge headless) |
| `02-card-closeup.png` | Card #1 ("Death Note") close-up, cropped from `01-...png` to the card's measured box |
| `05-library-1440.png` | My Library, default (empty Watch Later), 1440×900 (Edge headless) |
| `06-profile-1440.png` | Profile, default (Local profile, unavailable state), 1440×900 (Edge headless) |
| `07-compare-1440.png` | Compare, default (no username entered), 1440×900 (Edge headless) |
| `08-settings-1440.png` | Settings, default saved preferences, 1440×900 (Edge headless) |
| `09-discover-mobile-375.png` | Discover at 375×812 — **known headless-only artifact**: Edge headless (`msedge.exe --headless=new`) renders this route with text noticeably wider than the live app at the same viewport, clipping the nav row and right-edge buttons in the saved PNG. The interactive Claude Browser pane at the identical 375×812 size, and a live `getBoundingClientRect()` check, both confirm no real overflow (all 5 nav links fit within 375px, right edge of "Settings" = 371px). Treat this PNG as visually unreliable for mobile layout; the measurements and pane screenshot described under "Global layout & navigation" are authoritative. |

States that exist only as pane screenshots (interactive/modal states that Edge
headless cannot reach without JS/click automation, and which were not otherwise
saved to disk):
- "Why this pick" / Details dialog open on card #1 ("Death Note") — described
  fully under "Card interactions".
- Filters & sort drawer open, with Genre and Studio sub-panels expanded —
  described fully under "Filters & sort".
