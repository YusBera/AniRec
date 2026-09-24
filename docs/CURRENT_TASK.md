# Current Task

## Status: PySide design port — implemented, reviewed, review fixes applied

Handoff written 2026-09-24 on branch `feat/pyside-design-port`. It branches
from `codex/ui-v3-engine`.

The user designed the PySide desktop client carefully. The first React port
copied its styling without understanding it. **D-016**: the latest PySide client
(`AniRec/gui/` at HEAD, not only the 1.3.0 package) is the design reference for
the web client:
- its structure;
- which controls exist;
- its wording (`AniRec/gui/texts.py`);
- the intent in its docstrings and CHANGE comments.

Domain rules still outrank both clients.

### Done on this branch

- **Taste vector** (removed again in the review round, D-017).
  `FeedResponse.taste_vector` served the desktop Discover
  header's taste line, built by `AniRec/presentation/taste_vector.py`: up to 4
  liked and 2 avoided terms, each typed `genre` or `studio`. Tests:
  `tests/test_taste_vector.py`. Generated API types are regenerated.
- **D-015.** Feedback is given after watching, in the Library. The Discover
  vote buttons are retired.
- **D-016.** The design reference. `AGENTS.md`, `CODEMAP.md`, `DESIGN.md`,
  `PRODUCT.md`, the frontend README and `UI_CONTRACT.md` are updated.
- **Reference captures.** 23 PySide states and the pre-port React states, each
  with structural notes, are in `docs/reference/` (read its README).

### Done: both work packages (2026-09-24)

Packages A and B below are implemented in one change; see "Completion notes"
at the end of this file. The package descriptions are kept as the record of
what was asked.

## Decisions already made (do not reopen)

- Remove Like/Dislike from Discover cards and the inspector (D-015). Keep the
  backend vote endpoint and the stored votes.
- "Set aside" becomes **Not interested**, mapped to the existing `hidden`
  action.
- **Compare shows no compatibility percentage.** PySide showed one, but it is
  uncalibrated (DOMAIN_RULES, "Scoring Honesty"). The user has not decided to
  calibrate it.
- **The inspector takes the PySide Score Inspector layout** and carries the
  existing honest `why` explanation (exact-additive / counterfactual-removal /
  unavailable) inside its PERSONAL FIT panel.
- **First run:** port the Welcome step and "Look around with sample data".
  Connecting an account from the web is not built. The web cannot ask visitors
  for a Client ID; the hosted, username-only import waits on D-014. The
  connect step must say so honestly, and must never tell the reader to install
  a desktop app.
- **SYSTEM readout values come only from the API.** ENGINE comes from
  `active_operations`, PROFILE and MAL from `/api/system/state`, and SOURCE
  from the feed's `source`.

## Work package A — Discover, card, views, inspector, Library

**Owns:** `frontend/src/discover/**`, `frontend/src/workspace/LibraryPage.tsx`,
`frontend/src/api/{client,types,hooks}.ts` and a new
`frontend/src/assets/icons/`.

**PySide sources:**
- `gui/recommendation_card.py`, `match_badge.py`, `cover_art.py`,
  `metadata_tags.py`;
- `recommendation_row.py` (List view) and `recommendation_page.py` (the
  explorer: Cards/List/Table, filters, pills, empty states, Library states);
- `discover_page.py`, `recommendation_detail_dialog.py`,
  `discover_filters.py`, `filter_pills.py`, `texts.py`;
- the icons in `gui/resources/icons/ui/*.svg`.

1. **The card, as `recommendation_card.py` builds it.**
   - **Poster:** 2:3, default 152×228, width derived from the card, clamped to
     about 124–202px, so it fills the card. Use grid columns that give about 5
     cards per row at 1440px. Today there are 4 cards per row and 68px of dead
     space beside the poster.
   - **Nothing over the artwork:** no fit overlay, no `#N` badge.
   - **Element order:** poster → personal-fit line → title → secondary title →
     verdict row → studio and genre tags → year/status/episodes → MAL score →
     reason line → utility row.
   - **Personal-fit line**, worded as in `texts.py`: "Ranked #N of M for you",
     or unavailable.
   - **Reason line:** the API's `reason`, shown only when present. Never
     compose one.
   - **Verdict row:** exactly two icon toggles, Watch Later and Not interested,
     with the active SVG variants and the tooltips and accessible names from
     `texts.py`.
   - **Utility row:** two icons, Details and MyAnimeList.
   - **Touch targets:** at least 44px on coarse pointers.
2. **The Discover header, as `discover_page.py` builds it.**
   - The "DISCOVER //" header with STATE.
   - A primary **RUN ANALYSIS** button. It starts `POST
     /api/operations/recommendation` with the same client pattern as "more":
     progress, cancel, reload when done, and handling of a 409. It is disabled,
     with the reason given, on the sample feed.
   - **TASTE VECTOR** from `feed.taste_vector`, with the sentence built exactly
     as `_summary_sentence` builds it and the expanded `taste_line` /
     `taste_avoid` lines.
   - The status line in the `texts.py` vocabulary.
   - "Recommend 5 more" stays.
3. **Cards / List / Table** on Discover, with PySide's toggle and icons.
   Pagination stays.
4. **My Library:** the same explorer, with tabs WATCH LATER / NOT INTERESTED
   (Watch Later first), the three views, and PySide's empty-state copy.
5. **The Score Inspector:** a full surface headed "ANIREC / SCORE INSPECTOR".
   - Previous/next buttons and an "07 / 08" position across the visible feed.
   - Close.
   - A large poster and a meta grid.
   - The PERSONAL FIT panel, containing the fit value, the reason and the
     honest `why`.
   - Watch Later / Not interested as text buttons, "Open on MyAnimeList", and
     "READ SYNOPSIS +".
   - Focus management: Escape closes it and focus returns to the card.

## Work package B — shell, Profile, Compare, Settings, first run

**Owns:**
- `frontend/src/workspace/{Workspace,ProfilePage,ProfileSections,ComparePage,SettingsPage,common}.tsx`;
- `workspace.css` and `WorkspaceRead.test.tsx`;
- new files under `frontend/src/workspace/`;
- `frontend/src/styles/{instrument,base}.css` and `frontend/src/main.tsx`;
- a new `frontend/src/assets/shell/`.

Do not change the `common.tsx` exports (`PAGE_SIZE`, `PageControls`).

**PySide sources:**
- `gui/main_window.py`, `system_log.py`, `instrument_widgets.py`,
  `sync_notice.py`;
- `profile_page.py`, `profile_widgets.py`, `presentation/taste_profile.py`;
- `compare_page.py`, `presentation/compatibility.py`;
- `settings_page.py`, `setup_wizard.py`, `texts.py`.

1. **The shell.**
   - The brand block and the numbered nav rail in PySide's style and wording.
   - A **SYSTEM** readout (ENGINE / SOURCE / PROFILE / MAL) and an **ACTIVITY**
     console showing real operation progress and history from
     `/api/operations`, never invented lines.
   - The BUILD footer.
   - The sample banner, "Sample data. Connect MyAnimeList to see your own
     picks.", with its button.
   - `X // Y` page headers.
2. **Profile.**
   - The reader block and THE READING verdict.
   - "NOT ON YOUR MAL PROFILE", with icons and character cards: biggest hype
     kill, deepest cut, most rewatched, nemesis studio, and the rest.
   - The remaining sections, in PySide order and wording.
   - A section the API has no data for says so; nothing is invented.
   - The Local / Sample switch stays.
3. **Compare:** PySide's layout and wording, with no percentage.
4. **Settings:** six sections in PySide order.
   - **RECOMMENDATION:** includes NOT INTERESTED (`include_hidden`) and KEEP IN
     SYNC (`background_sync`, with the PySide hint).
   - **APPEARANCE:** says the web client is dark-only.
   - **PROFILES / MYANIMELIST API / LOCAL DATA / DEVELOPER TOOLS:** the PySide
     structure. Where the web API cannot act, say "not available in the web
     client yet" instead of showing fake controls. Never display a Client ID.
5. **First run:** shown when `needs_setup`, and remembered for the session.

## Rules for both packages

- Read the PySide file first, including its docstrings and CHANGE comments,
  then build. The screenshots in `docs/reference/pyside-latest/` are for
  checking, not the source.
- Use tokens only from `frontend/src/styles/tokens.css`, which is generated
  from `gui/design_tokens.py`. Never hand-edit it.
- Posters are 2:3 everywhere, including List and Table thumbnails.
- Every surface works at 375px, by keyboard and with a screen reader.
- Never invent a value. Unavailable values say so in words, and the frontend
  never recomputes scores.
- Update the vitest tests to match, and delete the tests of removed vote UI.
- Verify with `npm run ci` from `frontend/` and targeted `pytest` from the root.
  Compare against `docs/reference/pyside-latest/` at 1440×900 and at 375px.
- Per `AGENTS.md`: one final adversarial review, because this changes an API
  contract (`taste_vector`) and many user-facing surfaces.

## Running it without a real profile

```bash
python -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m AniRec.api --port 8771 --root-override /tmp/anirec-sample   # empty root = labelled sample data
cd frontend && npm install && ANIREC_API=http://127.0.0.1:8771 npm run dev -- --port 5173
# Writes are Origin-checked (D-021): another dev port needs
# ANIREC_ALLOWED_ORIGIN=http://127.0.0.1:<port> set for the API.
```

## After this task

- `NEXT_GOALS.md`, "Before a public launch", has the pre-launch checklist.
- **D-015 Library feedback:** report a watched recommendation as liked,
  disliked or scored, and record one observed on return.
- **D-014:** the user's local-mode choice gates accounts.
- A future state-service task must fix stale whole-state `save()` calls.

## Completion notes (2026-09-24)

**Changed.** Only `frontend/src/**` plus `docs/CODEMAP.md`. No API route,
model or persisted format changed; the generated types still verify.
- Discover: `DiscoverHeader.tsx` (DISCOVER // STATE, RUN ANALYSIS, TASTE
  VECTOR), `RecommendationCard.tsx` (the PySide card), `FeedViews.tsx`
  (Cards / List / Table), `ScoreInspector.tsx` (replaces
  `RecommendationDetails.tsx`), and `DiscoverPage.tsx`.
- Library: the same explorer, WATCH LATER then NOT INTERESTED tabs.
- Shell: `Shell.tsx` (SYSTEM, ACTIVITY), `FirstRun.tsx`, `Workspace.tsx`.
- Profile, Compare, Settings rewritten to the PySide structure and wording;
  `profileFacts.ts` composes the "NOT ON YOUR MAL PROFILE" board.
- Icons are copies of `AniRec/gui/resources/icons/ui/*.svg` under
  `frontend/src/assets/`, applied as CSS masks.

**Choices made where the spec was open** (reversible, not new decisions):
- MAL readout says `CLIENT ID` / `NO CLIENT ID`, not the desktop's
  `ONLINE` / `OFFLINE`: `/api/system/state` reports only whether a Client ID
  is configured, not a live connection.
- Not interested leaves the For You feed at once, as the desktop's "all"
  collection does; "Show not interested" brings it back. On a profile feed
  that re-reads the feed with `include_hidden`; the sample feed is never
  refetched, so its in-memory decisions survive.
- Activity impressions and positions are recorded from the Cards view only
  (the event surface is `web_cards`); List and Table record nothing.
- Library and Settings have no desktop channel legend; they use
  "MY LIBRARY // COLLECTIONS" and "SETTINGS // CONFIGURATION".
- Compare cards omit the verdict row: compared titles are finished ones.
- KEEP IN SYNC and APPEARANCE say they apply to the desktop app; the web
  client does not sync in the background and is dark-only.

**Verification.** `npm run ci` (88 tests), `vite build`, the non-Qt pytest
set, and Chromium captures at 1440×900 and 375×812 against a sample-only API
(5 cards per row at 1440, poster 202×303; no horizontal overflow at 375; no
visible control under 44px at 375).

**Review round (2026-09-24).** The user's decisions (D-017) and the review
findings were applied on this branch.
- **Removed:**
  - RUN ANALYSIS;
  - the Discover taste vector, together with its API field
    (`FeedResponse.taste_vector`), `presentation/taste_vector.py` and its
    tests;
  - every "Connect my account" prompt and the first-run connect step;
  - the status line's "CONNECT TO KEEP";
  - the decorative Japanese text in both clients.
- **Fixed:**
  - The Table's Rank column shows the position in the reader's order
    (CHANGE [RANK]).
  - A progress stream that closes early now reads the operation's own state
    instead of staying "running".
  - SYSTEM shows unknown values after a failed poll.
  - Card tags past the reservation collapse into a "+n" that names the rest
    (`metadata_tags.py`).
  - "You're all caught up" appears when every title is hidden.
  - The inspector's focus falls back to the list.
  - Buttons are sentence case.
- **Still open from the review:**
  - A decision can visibly revert during an overlapping reload.
  - Library title details go stale after a new generation.
  - Icon-only buttons lose their glyph in Windows High Contrast.
  - Some off-scale pixel values remain in component CSS.
  - Each card has three tab stops for one action.

**Automatic refresh (2026-09-24, D-018).**
- Backend:
  - a `refresh` operation (`run_refresh`) that syncs, then rebuilds only for
    a missing feed, changed inputs or filters, or a different engine;
  - `_snapshot_is_current` is now shared with "more";
  - `run_step` takes the server-bound profile, as the other entry points do;
  - `engine_identity` names the engine that would rank now.
- Frontend:
  - "Recommend 5 more" is gone;
  - 50 per page, with "Next page" continuing the ranking;
  - an automatic refresh once per session, plus a small Refresh button;
  - a stale "more" refusal triggers one refresh.
- Tests: 6 backend tests (`test_recommendation_explanation.py`, "automatic
  refresh") and the frontend tests updated and added.
- **Review round 2 (NO-GO, then fixed):**
  - The engine version comes from the manifest, so a restart is not a change.
  - The digest covers only the reader's own list data plus the generated
    files, so community drift no longer rebuilds the feed.
  - A rebuild runs the full run's own `_generate_feed`.
  - Frontend:
    - honest wording after a failed recovery;
    - the page holding the first new pick;
    - no duplicate "next" control;
    - an accessible name that matches the visible label;
    - every refreshed profile remembered per session;
    - a profile with no feed yet refreshes;
    - no reconnect advice.
- **Final adversarial review (2026-09-24), fixed with a failing test first:**
  - A feed the fallback ranked for this reader (the model loads but declines
    them) read as "engine-changed" on every refresh, so it was rebuilt each
    session. The snapshot now records which preferred engine declined
    (`preferred-engine` row, outside the ranking identity), and the feed stays
    current until that engine can load or changes version.
  - A failed history fetch read as "inputs-changed" and rebuilt the feed
    without history. The list is now judged against the saved history; the
    saved history is not overwritten, and a feed ranked without history is
    marked so the next working fetch rebuilds it.
  - The digest now treats NaT and `<NA>` as the empty cell a CSV reads back.
  - With session storage unwritable, the automatic refresh restarted after
    every finished run. It is now also remembered in memory.
  - An automatic refresh that meets another tab's running operation (409)
    no longer shows a fault; a Refresh the reader pressed still reports it.
  - `auth_timeout` advice ("start the connection again") is dropped like
    `auth_error`'s (D-017).
  - Confirmed as sound: a "current" refresh never overwrites the saved feed
    (`save_merged` keeps the previous recommendations); "more" still refuses
    a stale feed and continues with unique ranks; refresh is exclusive with
    every feed-writing kind.
  - Still open, minor: after a 409 the page does not reload the feed when the
    other tab's run finishes; the next open or Refresh shows it. A history
    that became empty leaves the old `user_history.csv` on disk, so such a
    feed rebuilds on every refresh.

**Shell redesign (2026-09-24, D-019).** The left rail is gone. A top bar
holds the name, the tabs (Discover, My Library, Compare), a notifications
bell and the account picture, whose menu holds Your profile and Settings; on
a phone the tabs are a bottom bar. The SYSTEM readout, ACTIVITY console and
BUILD line are removed; the same real events become plain-language
notifications, and the version is shown in Settings. The sample banner is
reworded to reassure ("Try anything; nothing here is saved."). The package B
items above for the rail, readout, console and BUILD footer are superseded.
- Tests: `Shell.test.tsx` (top bar, account menu, bell, notifications from
  operations, no history announced, version in Settings); `npm run ci` 105.
- Follow-up, done: Discover opens with a plain title and one line ("Anime
  picked for you."); "Updating your recommendations…" appears only while an
  update runs, and failures stay in the control bar's alert. The STATE
  readout is gone. The status line says "8 recommendations"; saved counts
  live on the My Library tabs ("Watch Later 0"). Page headings are plain
  ("My Library", "Profile", "Compare", "Settings"), with no "X // Y" marks.
  The second sample note on Discover and Library is gone; the shell's banner
  labels sample data on every page.
- Still in the desktop's voice, for a later pass if wanted: Profile's
  upper-case legends ("THE READING", "NOT ON YOUR MAL PROFILE", "THE
  INSTRUMENT") and Settings' upper-case group titles.

**First-time setup (2026-09-24, D-020).** A two-column pop-up: "Welcome to
AniRec" (accent) and "your personal anime recommender" on the left; on the
right a MyAnimeList username field with Continue, AniList and AniDB marked
"Coming soon", "I'm new to anime" (not active yet), and "Just look around".
- Backend: `POST /api/onboarding/mal-profile` (`AniRec/api/onboarding.py`)
  calls `OnboardingService.import_public_mal_profile`, which validates the
  public list with the installation's Client ID, makes it active and marks
  setup complete. Failures return a `reason`; nothing is created. Tests:
  `tests/test_onboarding_api.py` (13).
- Frontend: `FirstRun.tsx` rewritten; a guest can reopen it from the account
  menu ("Set up your profile"). A successful import notifies and nudges the
  shell, so the automatic refresh (D-018) builds the first feed. Tests in
  `Shell.test.tsx`; `npm run ci` 112.
- **Final adversarial review, fixed with a failing test first:**
  - MyAnimeList refusing the installation (401) read as a private list; it
    is now `installation-refused`, with its own wording.
  - MyAnimeList outages and unexpected statuses read as the reader's
    connection; they are now `unavailable` (`UnexpectedStatusError` for
    other 4xx).
  - Importing a reader who already had a profile overwrote it, and a
    desktop `mal-<id>` profile got a second, username-keyed one. A known
    username (case-insensitive) now reactivates the saved profile untouched.
  - A disk error while saving returned a 500; it is now `unavailable`, with
    setup still needed.
  - The pop-up no longer opens by itself when a profile is already active.
  - One stable live region for progress and problems; the button's
    accessible name keeps its visible words; the notice no longer promises
    what follows ("AniRec is reading it now.").
  - Tests: `tests/test_onboarding_api.py` 25; `npm run ci` 115.
- **Next: the newcomer poster picker.** Needs decisions first (see D-020):
  a non-MAL local profile, how picks become history, and a model check with
  a real bundle.

**Accounts, phase 1 (2026-09-24, D-021).** The user reported that anyone
could import any MyAnimeList username and then see and change the saved
decisions of whoever had imported it before. Design, review findings, known
limits and later phases: `docs/ACCOUNTS.md`.
- Backend:
  - `AccountService` (`config/accounts.sqlite3`): server-assigned account IDs,
    guest and registered accounts, scrypt passwords, SHA-256-only sessions,
    import ownership, the installation owner.
  - Every reader route resolves `ReaderScope` from the session cookie
    (`api/accounts.py`); the API no longer reads `profile_state.json`.
    Operations are visible only to the account that owns their import.
  - `RequestGuardMiddleware`: Host allowlist on every `/api/` request (DNS
    rebinding) and Origin checks on every write.
  - Web imports are `imp_<hex>` directories owned by the account; a guest
    account is created only after a list is read. Imports and new accounts
    are capped per hour.
  - Installation settings: only the owner may save them; the operator names
    the owner with `python -m AniRec.api.accounts owner <email>`, which also
    hands over pre-account profiles.
- Frontend: `AccountDialog.tsx` (create account / sign in), the account menu
  (Create account, Sign in, Sign out), the dismissible "Create an account so
  you don't lose your Watch Later." prompt for a guest with a list, "Already
  have an account? Sign in" in first-time setup, read-only Settings for
  non-owners. Pages remount and notifications clear when the account changes.
- Early design review: 13 findings (4 blockers), all applied to the design
  before code.
- Tests: `test_account_service.py`, `test_account_api.py`, onboarding and
  the older API tests moved to signed-in readers (`tests/account_helpers.py`);
  frontend `Shell.test.tsx`. `npm run ci` 126; pytest 577 passed (the 7
  failures and 39 Qt collection errors predate this change).
- **Final adversarial review: GO.** It found no cross-account path and no
  session fixation. Fixed, each with a failing test first:
  - a `busy` hash refusal was counted as a wrong password and could lock out
    the right one; the hashing slot is now taken before the attempt counts;
  - an unreadable `accounts.sqlite3` made every route a 500, the sample feed
    included; it now reads as no session, and account routes answer
    `unavailable`;
  - the documented dev port (5174) could not write; the docs use 5173 and
    name `ANIREC_ALLOWED_ORIGIN`.
  - Nits: the session no longer claims a sliding expiry the cookie does not
    have; a guest's list moved into an account that has one is named in the
    sign-in notice (`moved_imports`); the shell forgets the previous
    account at once; the password field shares the live region; focus
    returns to the page after signing in; one loose test assertion.
  - Recorded as hosted-launch gates in `ACCOUNTS.md`: process-wide caps,
    the open shutdown route, uncapped lookup and Compare, import switching.
- **Next:** phase 2 (account management, reader preferences split from
  installation settings, guest pruning) is required before any hosted launch;
  then Google (needs an OAuth client the owner creates), passkeys (needs
  `localhost`, not `127.0.0.1`), email (needs a sender).

**Accounts, hosted-launch gates (2026-09-24, D-021).** The items the phase-1
final review listed:
- **Switching lists:** `GET /api/account/imports`,
  `POST /api/account/imports/active` (own lists only); "Your lists" and
  "Add another list" in the account menu. A guest's list moved into an
  account is reachable this way.
- **Per-visitor limits** (`api/limits.py`) replace the process-wide caps:
  new accounts, sign-in failures across emails, and one MyAnimeList budget
  for imports, `profile-lookup`, live Compare and Library title look-ups.
- **Trusted proxies:** `ANIREC_TRUSTED_PROXIES` decides who the visitor is
  and whether the cookie is `Secure`; forwarded headers from anyone else
  are ignored.
- **Shutdown:** only the launcher's token or the installation owner.
- Tests: `tests/test_account_phase2.py` (10), the lifecycle and onboarding
  tests updated; frontend `Shell.test.tsx`. pytest 586 passed (the same 7
  failures and 39 Qt collection errors as before); `npm run ci` 129.
  Chromium at 375×812: the switcher works, no control under 44px.
- Still before a hosted launch: change password, delete account, export,
  reader preferences split from installation settings, guest pruning.

**Known limits.** The fonts in the token stacks are not bundled, so browsers
without them fall back to system faces. The Qt test modules cannot import in
a container without `libEGL`; two `test_api_lifecycle` tests fail on Linux
(`os.kill` overflow in `single_instance.py`), unrelated to this change.

