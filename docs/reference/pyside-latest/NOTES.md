# PySide latest (HEAD) — UI notes

Source read: `AniRec/gui/*.py` and `AniRec/presentation/*.py` extracted from
the current repository's `HEAD` (`git archive HEAD AniRec anirec_gui.py
scripts`) into an isolated scratch checkout — the working tree at
`C:\Users\yusuf\OneDrive\Desktop\projects\AniRec` was never touched. Captured
offscreen (`QT_QPA_PLATFORM=offscreen`) with `APPDATA`/`LOCALAPPDATA`
redirected to a fresh, separate scratch folder (`pyside-latest-appdata`,
distinct from the 1.3.0 capture's folder), using the app's own "Look around
with sample data" path. No MyAnimeList Client ID/secret/token was ever
entered. The resolved data root was printed and asserted in-process before
any capture (`...\pyside-latest-appdata\AniRec`); the real `%APPDATA%\AniRec`
was not touched.

## Global layout & navigation

Unchanged in structure from 1.3.0: the same five-page nav rail (`01 DISCOVER`,
`02 MY LIBRARY`, `03 PROFILE`, `04 COMPARE`, `05 SETTINGS`), the same SYSTEM
readout (ENGINE/SOURCE/PROFILE/MAL) and ACTIVITY console in the sidebar, the
same instrument-panel visual language, the same sample-mode banner. The
sidebar's ACTIVITY console header now carries a small `+` control next to the
"ACTIVITY" caption (an expand affordance not present in 1.3.0's console
header). The window footer still prints `BUILD 1.3.0` — the app's version
metadata constant was not bumped even though the UI underneath it changed
substantially; do not rely on that string to identify the build.

## Discover — page

Same two-line instrument header (action strip + `TASTE VECTOR` panel) and the
same Cards/List/Table toggle. Two concrete changes in the control bar:

- The result-count line now reads `"{N} IN FEED · SAMPLE · {S} SAVED · {K} SET
  ASIDE · CONNECT TO KEEP"` (1.3.0: `"{N} UNREVIEWED · {M} FILED · SAMPLE ·
  {L} LIKED · {D} PASSED · CONNECT TO KEEP"`) — vocabulary follows the
  Like/Dislike removal (see Changes since 1.3.0).
- A new **Activity** dropdown button sits beside `Recommend 5 more` and the
  `Filters` toggle: a `QMenu` with a checkable "Save activity on this device"
  item and a "Clear saved activity" item, tooltipped "Optional recommendation
  activity stored on this device only" / "Saved locally only; retained for up
  to 90 days and 50,000 events". This did not exist in 1.3.0.
- The `Show hidden` checkbox is renamed **"Show not interested"**.

## Recommendation card anatomy

Source: `AniRec/gui/recommendation_card.py`, `match_badge.py`. Constants
changed from 1.3.0 (all still passed through `scaled()`):

- **Poster**: 2:3 aspect ratio, unchanged. Default/height-derived size grew
  from 132×198px to **152×228px** (`COVER_WIDTH`/`COVER_HEIGHT`); the
  clamp band widened from 108–176px to **124–202px**. The code's own comment
  ("BIGGER-ART") frames this as giving the artwork the room two now-merged
  action rows freed up.
- **Placeholder art**: no longer a generic letter mark. Each card without a
  fetched cover now shows a `title_placeholder_pixmap` — the title's own
  initials (e.g. "M", "DN", "S", "NG", "CA") on a colour derived from the
  title, so a feed without artwork reads as distinct entries rather than
  copies of one missing-image glyph.
- **Match badge**: in this sample-data capture it never renders.
  `RecommendationViewModel.personal_match_available` is hardcoded `False` in
  the current presentation layer, and the match-percentage text line now
  reads **"Personal match unavailable"** for the sample feed (`fit_rank` is
  `None` for these records). When a real ranked feed provides a `fit_rank`,
  the same label instead shows **"Ranked #N of M for you"** — a rank
  statement, not a percentage. (This is consistent with the repo's Goal 2:
  the uncalibrated percentage was retired; `docs/CURRENT_TASK.md`'s claim
  that "the deprecated PySide client still renders its own legacy
  percentage" was not observed here — the percentage path exists in code but
  is gated off by `personal_match_available=False`.)
- **Element order**, top to bottom: poster (with initials placeholder) →
  match-text line ("Personal match unavailable" / "Ranked #N of M for you") →
  title (2 lines) → secondary title (1 line) → **verdict row**: two
  icon-only, checkable buttons — a clock glyph (**Watch Later**) and a
  slashed-circle glyph (**Not interested**), no text labels, each 32×32px
  (`ICON_ACTION_SIZE`, up from 26px in 1.3.0 for WCAG 2.1 AA target-size) →
  studio+genre tag strip → year/status/episodes → MAL score → reason line →
  **utility row**: two icon-only buttons, right-aligned — Details and an
  external-link MyAnimeList icon.
- **Like is gone entirely.** Dislike is gone as a separate control; it and
  the old Hide control are merged into the single **Not interested** toggle
  (`not_interested_button`, `not_interested_requested` signal). Checking it
  swaps the glyph to a filled "-active" variant and sets the danger colour
  role; unchecking it is worded "Show this recommendation again" in the
  accessible name/tooltip.
- Every verdict/utility control lost its text label in this version — 1.3.0
  had one labelled button (Later/Saved) plus three icon buttons; the current
  card has zero labelled buttons on its face (labels moved to tooltip +
  accessible name only).

**Like/Dislike buttons do not exist on the card in the latest build.** The
card offers exactly two judgements: **Watch Later** (save for later, neutral)
and **Not interested** (stop recommending this title; a filter, worded in the
code as "not a rating" and explicitly excluded from feeding the taste model),
plus **Details** (open the Score Inspector) and an external **MyAnimeList**
link.

## Card interactions

Unchanged from 1.3.0: click on poster/title/match area or Details opens the
Score Inspector; double-click and Enter also open it; focus selects the card;
`set_selected(True)` still paints a teal/cyan outline
(`10-recommendation-card-selected.png`); a synthetic hover event still
produces a distinct outline (`11-recommendation-card-hover-attempt.png`).
New in this version: the **Not interested** button's checked/pressed state is
independently visible — `11b-recommendation-card-not-interested-checked.png`
shows the glyph swap to its filled "-active" variant with a danger-tinted
outline, which has no 1.3.0 equivalent since that state used to be spread
across two separate controls (Dislike, Hide).

## Filters & sort

Unchanged in layout and behaviour from 1.3.0 (same grid of Add genre / Add
year / Minimum MAL score / Airing status / Minimum–Maximum episodes / Sort
by, same free-text genre/studio search and group-profile username field, same
dismissable pill row). The `Activity` dropdown button (see Discover) now sits
to the left of `Filters` in the same row. The state-filter combo backing the
pill/tab system offers `Recommendations` / `Watch Later` / `Not interested`
(was `Recommendations` / `Watch Later` / `Liked folder` / `Disliked folder`).

## My Library

Structural change: the collection is now exactly two tabs — **WATCH LATER**
and **NOT INTERESTED** (`LIBRARY_STATES = ("watch-later", "not-interested")`)
— replacing 1.3.0's three tabs (LIKED / DISLIKED / WATCH LATER). The default
tab on opening My Library is now **Watch Later** (first in the new tuple),
where 1.3.0 defaulted to Liked. Everything else — the shared
`RecommendationExplorerPage` widget, the Cards/List/Table toggle, the filter
panel, per-tab empty states — is otherwise the same mechanism as 1.3.0.

## My Profile

No structural change observed. Same header (avatar/initials, READER legend,
member-since, four stat readouts), same section set (Taste Fingerprint,
Rating Distribution, Hot Takes, Hype Killers, Hidden Gems, Genre DNA, Studio
DNA, Era Preferences, Watching Habits, Taste Through Time), same
refusal-with-sample-offer pattern when no live statistics backend is wired
("Your taste profile is not built yet" / **Show a sample profile**).

## Compare

No structural change observed. Same selector panel, same
`CompatibilityHeader` (username, large percentage match score, three stat
readouts), same section list built from `RecommendationCard`s with a
YOU/THEM/GAP/MAL comparison strip — those cards also lose the Like/Not-for-me
row and the match badge exactly as the feed cards do (comparison cards never
showed the badge even in 1.3.0), but now additionally lose the Watch
Later/Not-interested verdict row's text labels (icon-only, same as feed
cards). Same refusal-with-sample-offer pattern ("Compatibility is not built
yet" / **Show a sample comparison**).

## Settings

Same card layout (RECOMMENDATION / APPEARANCE / PROFILES / MYANIMELIST API /
LOCAL DATA / DEVELOPER TOOLS), with two changes inside RECOMMENDATION:

- The checkbox row previously labelled **"HIDDEN ITEMS" / "Include hidden
  recommendations"** is now **"NOT INTERESTED" / "Include anime marked Not
  interested"**.
- A new row, **"KEEP IN SYNC"**: a checkbox "Check MyAnimeList for anime you
  have finished, while AniRec is open", with a hint: "Off by default. AniRec
  already checks once when you open a profile. This keeps checking every 30
  minutes, so a title you finish elsewhere leaves your Watch Later list
  without a restart. It only reads your list and never writes to your
  account." No equivalent existed in 1.3.0.

APPEARANCE, PROFILES, MYANIMELIST API and LOCAL DATA cards are unchanged.

## First-run, empty and sample states

Wizard Welcome and API Configuration steps are pixel-for-pixel unchanged in
copy and layout from 1.3.0 (same "Look around with sample data" primary
action, same MyAnimeList API instructions and empty Client ID/Secret fields).
Sample-mode banner unchanged. Empty-state copy changed to match the new
collections:

- My Library, empty Watch Later tab: "Your Watch Later list is empty" / "Save
  an anime from any card and it will appear in this collection." (same
  wording as 1.3.0).
- My Library, empty Not interested tab: unlabelled folder icon
  (`folder-not-interested`), title/body not fully visible in the captured
  frame but the tab and its `0` count render correctly
  (`15-my-library-not-interested-empty-state.png`).
- The "no matches / clear filters" and "build your first feed" empty states
  are otherwise the same as 1.3.0.

## Language & tone

Same technical/instrument-panel register. Concrete string changes from
1.3.0:

- Personal-match line: **"Personal match unavailable"** or **"Ranked #{N} of
  {M} for you"**, replacing 1.3.0's literal **"Personal match: NN.N%"**.
- Score Inspector legend: **"PERSONAL FIT"** with a **"RANKED RESULT"** tag,
  replacing 1.3.0's **"PERSONAL MATCH"** / **"EXPLAINED SCORE"**. The
  contribution-rail track and the "SUMS TO" reconciliation row are gone from
  the dialog in this sample capture (no `fit_rank`/contributions to show);
  1.3.0 always rendered a rail and a sum line, even if degenerate.
  Feedback row in the dialog is now Watch Later / Not interested (icon
  buttons in the card, but still labelled text buttons inside this dialog),
  replacing Like / Not for me.
- Card verdict tooltips/accessible names: **"Save for later"** / **"Remove
  from Watch Later"**, and **"Not interested"** / **"Show this recommendation
  again"** (tooltip: "Stop recommending this anime. It stays in Not
  interested." / "Show this anime in For You again.") — replacing 1.3.0's
  Like/Dislike wording ("Move to Liked", "Remove dislike", etc.).
- Feed status line vocabulary: **"IN FEED" / "SAVED" / "SET ASIDE"**,
  replacing **"UNREVIEWED" / "FILED" / "LIKED" / "PASSED"**.
- Library collection labels: **"Collections · N not interested"** (a hidden
  compatibility button, `taste_folders_button`), replacing **"Taste folders ·
  N liked · N disliked"**.
- Settings: **"NOT INTERESTED"** replaces **"HIDDEN ITEMS"**; new **"KEEP IN
  SYNC"** row (see Settings section).

## Visual language

Palette, typography (Yu Gothic UI / Martian Mono / IBM Plex Mono stacks),
spacing scale, near-square radius scale and the CRT-instrument-panel metaphor
are all unchanged from 1.3.0 in this capture. The one visible density change
is the larger poster (152×228 vs 132×198) and the shift of every card action
to icon-only glyphs, which reduces the amount of text set on a card overall
and gives the artwork proportionally more of the card's footprint. Anime
artwork is still always 2:3 portrait everywhere it appears (feed cards, list
thumbnails, score-inspector cover), consistent with 1.3.0.

## Screenshots index

| File | State |
| --- | --- |
| `01-first-run-welcome.png` | Setup wizard, Welcome step, standalone (760x620) |
| `02-first-run-api-settings.png` | Setup wizard, API Configuration step, standalone, empty fields (760x620) |
| `03-discover-cards-1440x900.png` | Discover, Cards view, sample data |
| `04-discover-list-1440x900.png` | Discover, List view |
| `05-discover-table-1440x900.png` | Discover, Table view |
| `06-discover-filters-open.png` | Discover, Cards view, Filters panel expanded |
| `07-discover-taste-vector-expanded.png` | Discover, TASTE VECTOR panel expanded |
| `08-discover-no-matches-empty-state.png` | Discover, "No matches found" empty state |
| `09-recommendation-card-alone.png` | One `RecommendationCard`, resting state, grabbed alone |
| `10-recommendation-card-selected.png` | Same card, `selected` property true |
| `11-recommendation-card-hover-attempt.png` | Same card, synthetic `QEnterEvent` sent |
| `11b-recommendation-card-not-interested-checked.png` | Same card, "Not interested" toggled on (filled glyph, danger tint) |
| `12-score-inspector-detail-dialog.png` | `RecommendationDetailDialog` ("Score Inspector") opened from a card |
| `13-my-library-default.png` | My Library, default tab (now Watch Later), empty |
| `14-my-library-watch-later-empty-state.png` | My Library, Watch Later tab, empty state |
| `15-my-library-not-interested-empty-state.png` | My Library, Not interested tab, empty state |
| `16-profile-backend-missing.png` | Profile page, refusal state with "Show a sample profile" |
| `17-profile-sample-data.png` | Profile page, sample profile shown |
| `18-compare-idle.png` | Compare page, idle state |
| `19-compare-sample-data.png` | Compare page, sample comparison shown |
| `20-settings-default.png` | Settings page, default state |
| `21-discover-cards-1024x768.png` | Discover, Cards view, at 1024x768 |
| `22-discover-list-1024x768.png` | Discover, List view, at 1024x768 |

Not captured, for the same reasons as the 1.3.0 pass: wizard OAuth-connect
and Initial-Analysis steps, the "all caught up" exhausted-feed state, and a
genuine (non-synthetic) mouse hover.

## Changes since 1.3.0

Grounded in `git show --stat e4710a1` ("ask for the judgement a card can
actually support", 2026-09-02) plus later commits touching `AniRec/gui`
through the current `HEAD` (`cb8e3d0`):

1. **Like removed entirely.** No like control exists anywhere in the PySide
   client any more — not on the card, not in the list row, not in the Score
   Inspector.
2. **Dislike and Hide merged into one control: "Not interested."** Previously
   two controls did the same exclusion (`disliked_mal_ids | hidden_mal_ids`);
   now there is one (`hidden_mal_ids`) and one button. It is explicitly
   documented in code as a filter, not a rating — it "says nothing to the
   taste model."
3. **My Library collections changed** from LIKED / DISLIKED / WATCH LATER to
   **WATCH LATER / NOT INTERESTED** — two tabs instead of three, and the
   default tab is now Watch Later instead of Liked.
4. **Card controls became icon-only.** Watch Later and Not interested (the
   verdict row) and Details/MyAnimeList (the utility row) all dropped their
   text labels; state and meaning now live only in tooltip + accessible
   name. Icon touch targets grew 26px → 32px for WCAG 2.1 AA (2.5.8)
   pointer-target-size compliance.
5. **Poster grew.** 132×198px → 152×228px (default/derived size), clamp band
   108–176px → 124–202px — freed by consolidating what used to be two action
   rows (Like/Dislike, then Watch Later/Details/MAL/Hide) into fewer,
   icon-only rows.
6. **Placeholder artwork became per-title.** A generic single letter (all
   covers showed the same "A" glyph in 1.3.0) is replaced by a title-derived
   two-letter initial on a title-derived colour, so an artwork-less feed
   reads as distinct titles.
7. **The percentage "personal match" is gone from the sample/no-rank path.**
   The badge and its percentage text do not render when
   `personal_match_available` is false; the text line instead reads "Personal
   match unavailable" or, when a ranked feed provides one, "Ranked #N of M
   for you" — a rank statement instead of a percentage. The Score Inspector
   was relabelled "PERSONAL FIT" / "RANKED RESULT" (was "PERSONAL MATCH" /
   "EXPLAINED SCORE") and no longer shows a contribution rail or "SUMS TO"
   line in this state.
8. **New opt-in recommendation activity control** ("Activity" dropdown:
   enable/disable local activity logging, clear saved activity) added to
   Discover/My Library's control bar. Not present in 1.3.0.
9. **New "Keep in sync" setting**: an opt-in 30-minute MyAnimeList
   completion poll while the app is open, added to Settings → RECOMMENDATION.
   Not present in 1.3.0.
10. **Vocabulary changes** throughout: "UNREVIEWED/FILED/LIKED/PASSED" →
    "IN FEED/SAVED/SET ASIDE"; "Show hidden" → "Show not interested";
    "HIDDEN ITEMS" → "NOT INTERESTED" in Settings; "Taste folders · N liked ·
    N disliked" → "Collections · N not interested".
11. **Internal reorganisation** (no visible UI effect but relevant to anyone
    extending this code): `FilterKind`, `ActiveFilter`,
    `RecommendationViewModel`, the compatibility and taste-profile providers,
    and the metadata catalogue moved out of `AniRec/gui` into a new
    Qt-free `AniRec/presentation` package, re-exported from their old `gui`
    module paths for backward compatibility.
12. **Theme/QSS files were touched** (`dark.qss`, `light.qss`,
    `qss_builder.py` each show diffs in `e4710a1`'s stat summary,
    ~35 lines each) to support the icon-verdict button states (checked/
    filled glyph variants, danger-tinted "not interested" outline); no
    palette-role or colour-token change was observed in `design_tokens.py`
    itself, and the dark theme's colours in this capture read the same as
    1.3.0's.

Overall this is a "no unearned verdicts" redesign of the review loop
(remove pre-watch opinions the product can't honestly retract; keep only
the two judgements a card's pitch can actually support) plus a companion
change that stops the desktop client from claiming an uncalibrated match
percentage it cannot support either — both are the same underlying honesty
principle applied to two different controls.
