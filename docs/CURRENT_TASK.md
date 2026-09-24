# Current Task

## Status: PySide design port — backend done, frontend not started

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

- **Taste vector.** `FeedResponse.taste_vector` serves the desktop Discover
  header's taste line, built by `AniRec/presentation/taste_vector.py`: up to 4
  liked and 2 avoided terms, each typed `genre` or `studio`. Tests:
  `tests/test_taste_vector.py`. Generated API types are regenerated.
- **D-015.** Feedback is given after watching, in the Library. The Discover
  vote buttons are retired.
- **D-016.** The design reference. `AGENTS.md`, `CODEMAP.md`, `DESIGN.md`,
  `PRODUCT.md`, the frontend README and `UI_CONTRACT.md` are updated.
- **Reference captures.** 23 PySide states and the pre-port React states, each
  with structural notes, are in `docs/reference/` (read its README).

### Not started

**No frontend file has changed yet.** Two implementation agents were started
and stopped at a usage limit before writing anything. Their work packages
follow, complete. Run them in parallel as written (disjoint files), or one
after the other.

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
cd frontend && npm install && ANIREC_API=http://127.0.0.1:8771 npm run dev -- --port 5174
```

## After this task

- `NEXT_GOALS.md`, "Before a public launch", has the pre-launch checklist.
- **D-015 Library feedback:** report a watched recommendation as liked,
  disliked or scored, and record one observed on return.
- **D-014:** the user's local-mode choice gates accounts.
- A future state-service task must fix stale whole-state `save()` calls.
