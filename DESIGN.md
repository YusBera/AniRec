# AniRec visual authority

This records the established visual world, not a new theme.

**The latest PySide client is the design reference** (`docs/DECISIONS.md` D-016,
which revises D-004). It is the reference for:
- structure and proportion;
- which controls exist;
- wording (`AniRec/gui/texts.py`).

The web client is the product, and it adapts that design to the browser,
including narrow breakpoints. It does not replace the design with its own.
Where this file and the PySide code disagree, the PySide code wins, unless a
domain rule forbids what it shows.

## Existing visual system

- Green-black ground, bone text, thin square panel boundaries, restrained raster.
- Brass marks the reader's signal and primary action; aqua carries system,
  community, and keyboard focus. Selection and focus stay distinguishable.
- Indexed left navigation: Discover, My Library, Profile, Compare, Settings.
- Shared palette in `AniRec/gui/design_tokens.py` / generated web `tokens.css`:
  background #070C09, surface #0C1410, text #C6D4C2, strong #DCE8D8,
  muted #849686, brass #D9A441, aqua #5FBFB5, border #1E2E24.
- Square to near-square corners (0–3px), compact spacing, not rounded SaaS tiles.
- Existing fonts: display/system condensed headings; mono readouts; Yu Gothic UI /
  Segoe UI for prose. Reuse shared font stacks, not a new font brand.
- Portrait artwork, crisp and unfiltered. Anime covers and their list/table
  thumbnails preserve 2:3 poster proportions (existing Discover: 152 × 228 logical
  pixels), never square crops. The user explicitly reiterated this after viewing
  the concepts; square generated placeholders are not a specification.
  No fake anime cover art in the product.
- Score rails, paired readings, compact tables, and measured labels belong to
  the interface; fake telemetry, meaningless graph decoration, and unsupported
  claims do not.
- Motion communicates state and is restrained/stepped; reduced-motion mode keeps
  the same information immediately readable.

## Scope of current concepts

Layout and information hierarchy are the web client's to decide. Each surface
still serves its existing task: manage the library, understand taste through
evidence, compare two people, or configure the application. Concept images are
proposals, not screenshots of implemented features.

Two constraints now outrank the concept boards. Every surface must work at 375px,
by keyboard and with a screen reader; and a feed that can grow must paginate or
virtualise rather than mount in full. Where a board and those constraints
conflict, the constraints win.

## Approved next-tab composition

The user selected concept C, **Library-led workspace**, from the three visual
boards. Treat `.impeccable/mocks/decision/library.png` as a compositional north
star subject to the factual corrections in `reports/ui-tabs-concepts/README.md`:

- Library leads with recognizable 2:3 poster cards and attaches personal-match
  and MAL evidence directly to each saved recommendation.
- Profile keeps the compact identity/metric strip, then lets named anime evidence
  carry the reading instead of filling the page with generic stat cards.
- Compare groups shared interests and disagreements around portrait title cards
  with clearly paired reader/friend scores.
- Settings remains a practical, artwork-free control surface.

Do not copy generated square placeholders, invented dates/counts, omitted global
navigation, or erroneous labels/numbers. Translate the selected topology into
semantic, responsive React rather than rasterizing the board.

## Typography

The React workspace reuses the generated display, mono and prose font stacks;
it does not establish a new font identity. Page headings use display (26px, 800),
section headings (18px, 700), and title headings (16px, 700). Base readouts are
mono (13px, line-height 1.55); paragraphs use the shared sans stack and a 75ch
maximum width. Paired scores use mono (24px, 700); compatibility is a larger
brass reading (32px), above the subordinate identity counts (20px).

## Layout

These are implemented React adaptations of approved C, not replacement rules
for PySide. Sources: `frontend/src/workspace/workspace.css`, workspace components,
and shared `frontend/src/styles`.

- The desktop workspace has a sticky, full-height indexed navigation column
  (214px) and a flexible content column. Pages cap at 1500px with 34px side padding.
  At 1050px and below, navigation becomes 170px and side padding 22px;
  Settings groups become one column.
- At 700px and below, navigation becomes a wrapping top row, page side padding
  becomes 16px, and buttons, fields and navigation have a 44px minimum height.
  Library cards put their small poster beside attached title evidence.
- Library/Compare shelves use flexible columns with a 210px minimum and 16px
  gaps. Profile evidence pairs posters with scores and wraps into available width.
- Every poster remains 2:3, including an unavailable-image fallback. Sizes below
  are CSS pixels at the normal desktop/mobile layouts; the ratio also survives
  available-width constraints.

| Surface | Desktop | At 700px and below |
| --- | --- | --- |
| Library Cards | 152 × 228 | 80 × 120 |
| Library List | 80 × 120 | 64 × 96 |
| Library Table | 48 × 72 | 48 × 72 |
| Profile evidence | 100 × 150 | 80 × 120 |
| Compare | 152 × 228 | 152 × 228 |

## Elevation & Depth

Workspace panels use flat shared surfaces and thin borders, without added card
shadows. The inherited raster stays behind the content; artwork remains crisp.
Selection uses brass; the inherited keyboard outline uses aqua (2px, 2px offset).
Existing stepped Discover motion remains governed by the pinned motion rule above.

## Components

- **Navigation and shared state:** hash routes retain visited page state and restore
  route scroll position; route changes focus the visible page heading. Discover
  and Library share decisions, filters and the title inspector. Library search,
  collection and view remain selected across navigation.
- **Library:** Cards, List and Table expose the same source personal-match and
  MAL readings, details and removal/restore actions. Table uses a caption,
  semantic column/row headers and 2:3 thumbnails. Its 640px minimum width scrolls
  inside a labelled, keyboard-focusable region rather than widening the page.
  Compact sample/status copy keeps titles close to the controls on mobile.
- **Profile:** identity and supplied readings precede named above/below-community
  evidence. Desktop readings remain expanded. Mobile uses a native, initially
  collapsed “Taste readings” disclosure; its summary retains keyboard focus and
  expansion exposes every supplied reading and explanation. Further analysis
  reuses portrait evidence cards, labelled rating meters, native genre/studio
  title disclosures and compact definition lists for eras, habits and timeline.
- **Compare:** compatibility is the brass focal reading; anime count, shared and
  both-rated counts remain subordinate and correctly labelled. Title scores pair
  brass for the reader with aqua for the friend. Library and Compare use compact,
  wrapping aqua-outline genre chips from actual source genres. The sample-friend
  selector stays mounted and focused during loading; old scores disappear and a
  loading status is announced before the new report appears. Live comparison
  accepts a named public MAL completed list, retains N/A compatibility and keeps
  shared titles with an unrated score separate from paired rated evidence.
- **Settings:** artwork-free forms save allowlisted recommendation and desktop
  appearance preferences. Dirty, saving, saved, discard and error states are
  explicit; failed saves retain edits. Unreadable settings cannot be overwritten
  with displayed defaults. Desktop appearance values do not imply browser theme
  controls. Credentials and unavailable account/folder/delete actions are absent.
- **Unavailable and sample states:** missing posters have labelled portrait
  fallbacks; absent scores use N/A. Saved IDs outside the feed resolve from local
  snapshots or explicit MAL retrieval; metadata-only titles have no personal-match
  score. Profile and Compare require explicit sample opt-in; unavailable local
  data never silently becomes sample data. Preview decisions reset on reload.

## Do's and Don'ts

- **Do** preserve the established visual world - ground, brass/aqua roles, density,
  2:3 posters - and the approved C corrections above when extending these patterns.
- **Do** treat mobile as a first-class target rather than a narrow desktop. Touch
  targets are at least 44px on coarse pointers; verify the computed value, since
  stylesheet order has silently defeated that rule before.
- **Do** keep source evidence, sample labels, unavailable states and real capability
  limits visible without letting notices displace the title evidence.
- **Do** carry the Profile provider's additional archetype, histogram, genre/studio
  title disclosures, era/season, habit and timeline evidence without inventing
  unavailable statistics. Retain existing higher/lower title evidence first.
- **Do** distinguish live completed-list comparisons from bundled samples: live
  counts describe returned completed titles; scores pair the local snapshot with
  the named public list, and compatibility stays N/A. Unrated shared titles are
  separate. NSFW preference affects returned titles.
- **Don't** reach for desktop parity as a goal. Parity with a retired application is
  not a target; the web surface is judged on its own terms (`docs/DECISIONS.md` D-004).
- **Don't** claim populated live-result browser verification.
  The two-account API check passed for the existing NeoBalls_ snapshot against
  Kuroboshi_'s live completed list; it does not establish a fresh local sync.
- **Don't** canonize the four-screen concept board as a single-route pixel target.
  The raw hero comparison remains 41.1% FAIL. After explicit user approval to
  remove literal pixel matching, supported force transitions record C's
  composition-reference authority. The independent verdict resolves the six UI
  findings; the workflow addendum records this clarification without changing UI.
  This is not a pixel pass or certification of the whole surface. Evidence:
  `.impeccable/review/finish-verdict.md`, route desktop/mobile captures (including
  Library Table), and `docs/archive/WORKSPACE_IMPLEMENTATION.md`.
