# Concept C implementation specification

2026-09-06. Operate mode. Resume the approved `e94eea46` surface choice.

## Direction contract

THESIS: Saved titles lead; evidence stays attached to the anime it describes.

OWN-WORLD: Inherit PySide's green-black surfaces, bone type, brass personal
signals, aqua community/focus, square borders and existing SVG icons.

STORY: Save in Discover, revisit in Library, inspect taste evidence, compare
completed lists or the explicit bundled example, and save supported preferences.

FIRST VIEWPORT: Persistent indexed navigation beside a page heading and compact
controls. Library presents portrait cards; Profile pairs identity and readings
with title evidence; Compare places paired scores under portraits; Settings
groups practical fields without artwork. Narrow screens stack these groups.

FORM: Library-led workspace, structure 5, seed e94eea46; approved Concept C.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance

## Measured composition and binding corrections

The approved PNG is 1536 × 1024 and contains FOUR scaled screens, not a single
application viewport. The grid is `.impeccable/build/comp-grid.png`.

| Board region | Pixel bounds (x, y, width, height) | Translation |
| --- | --- | --- |
| Library | 9, 10, 753, 492 | One full route, three leading cards where space permits |
| Profile | 773, 10, 753, 492 | Identity strip, readings, selected title disagreements |
| Compare | 9, 515, 753, 499 | Identity pair, summary, ordered title sections |
| Settings | 773, 515, 753, 499 | Two columns of settings groups; single column on narrow screens |
| Library navigation | 10, 85, 171, 417 | Persistent navigation using existing house icons |
| Library controls | 199, 85, 550, 74 | Collection and view controls |
| Library first card | 199, 175, 175, 295 | Fluid card, 152 × 228 portrait artwork |
| Profile identity | 943, 80, 573, 85 | Wrapping identity and supplied metrics |
| Profile readings | 943, 177, 573, 126 | Compact labelled evidence, no invented analytics |
| Compare title cards | 184, 752, 560, 245 | Fluid portrait cards with paired /10 scores |
| Settings groups | 934, 576, 580, 434 | Separate recommendation, appearance, account and data groups |

These bounds are read from the grid image, not live browser measurements.
The user's explicit portrait correction overrides the board's square initials.
Existing token fonts override generated lettering. The board's four-screen
scale, invented dates, unavailable controls and erroneous labels cannot be
pixel-reproduced as an application. No board crop ships as UI or artwork.

## Capability mapping

- Library: existing feed/local-state/feedback boundary; preserve sample decisions
  in shared in-memory state across navigation, reset on reload. Saved IDs absent
  from the current recommendation snapshot are resolved from saved local CSV
  metadata or an explicit MAL request. Missing metadata is disclosed; metadata-only
  titles never acquire an invented personal-match score.
- Profile: `LocalTasteProfileProvider` over `ProfileStatisticsService`; explicit
  bundled demonstration via `SampleTasteProfileProvider`. Missing local statistics
  get an unavailable state, never an automatic substitution with example figures.
  Source-backed archetype, rating distribution, title evidence, genre/studio
  analysis, eras/seasons, habits and timeline are rendered when supplied.
- Compare: join the active local completed snapshot with a named public MAL
  completed list. Show source counts, paired ratings and absolute gaps; zero
  is unrated and aggregate compatibility remains N/A. NSFW preference scopes
  returned titles. `SampleCompatibilityProvider` remains explicit and labelled.
- Settings: allowlisted, validated preferences saved through `SettingsService`,
  preserving credentials and unexposed fields. Saving desktop appearance does
  not change or promise a browser theme. Account setup,
  folder opening and destructive data actions remain in the desktop app.
- Keep Python scoring and PySide visual authority unchanged. The authorized
  desktop Profile caching repair records successful local loads, invalidates on
  sync and sample display, and preserves all visual behavior. Generate HTTP types from
  Python models; do not mirror response interfaces manually in TypeScript.

## Verification

Exercise shared save/undo, navigation/back and retained filters, loading/error/
empty/sample states, missing artwork, long titles, keyboard focus and dialogs.
Inspect desktop and narrow renders against the PySide captures and corrected C
composition. Report manual structural review separately from automated pixel gates.
