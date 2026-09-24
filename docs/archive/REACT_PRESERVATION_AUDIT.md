# React Discover preservation pass

2026-09-06. Baseline: `968ec2d` on `feat/react-fastapi-boundary`.

This is a bounded Discover polish pass, not a completed migration or a Tauri
validation. PySide remains the shipping product and visual authority. The user
explicitly allowed recommendation-site layouts/widgets when they retain AniRec's
theme and feel. No Python product code, shared tokens, API model, or scoring
algorithm was changed.

## Authority and method

- Read the current migration/frontend handoffs and the actual Qt card implementation.
- Used Impeccable's technical audit and polish playbooks in preservation mode.
  Its generic aesthetic warnings do not override AniRec's instrument vocabulary.
- Used UI/UX Pro Max for targeted keyboard focus, web target sizing, and async
  React error handling. Did not adopt its React 19 Actions advice in this React 18 app.
- Captured the live PySide sample app at 1280 × 900 on the secondary monitor,
  with every service pointed at disposable data. Compared it directly with the
  live React sample feed at the same viewport, then checked 320, 375, and 768px widths.
- Qt evidence: [capture](../../reports/ui-preservation-2026-09-06/pyside-baseline.png),
  [geometry](../../reports/ui-preservation-2026-09-06/pyside-geometry.json),
  [capture script](../../reports/ui-preservation-2026-09-06/capture_qt.py).
  Browser screenshots and DOM measurements were captured in the accompanying task.

Current Qt source is important: it deliberately removed Like/Dislike verdicts
from Discover. A person can save an unwatched prospect or set it aside; neither
decision is a rating. Older descriptions of a Like/Not-for-me action row are stale.

## Audit health

These are scoped engineering assessments, not a WCAG certification or a full
performance benchmark. Light theme, screen-reader operation, and a real signed-in
account were not tested in this pass.

| Dimension | Before | After | Evidence / remaining limit |
| --- | ---: | ---: | --- |
| Accessibility | 2/4 | 3/4 | Heading/region semantics, explicit states, focus, native inspector, announced save outcomes; no screen-reader certification |
| Performance | 3/4 | 3/4 | Lazy artwork, stable keys, no new library, removed card entrance staggering; no large-feed performance profile |
| Responsive design | 2/4 | 3/4 | Bounded artwork, aligned decision rows, collapsible controls, no overflow at checked widths; no exhaustive localization/text-zoom matrix |
| Theming | 3/4 | 3/4 | Shared tokens unchanged; raster moved beneath content; light theme not rendered |
| Implementation integrity | 2/4 | 3/4 | Qt decision semantics, truthful sample/save state, complete inspector; full product migration still outstanding |
| **Total** | **12/20** | **15/20** | **Good for this scoped pass; not release-complete** |

Integrity verdict: the preserved system is coherent and product-specific. Brass
personal readouts, aqua system/community signals, square controls, compact type,
the calibration strip, and the green-black ground remain. No generic design
system, invented recommendation signal, or decorative status metric was introduced.

## Verified findings and disposition

Initial findings: 0 P0, 4 P1, 4 P2. Priorities describe user impact, not security risk.

| Priority | Finding / location | Impact and disposition |
| --- | --- | --- |
| P1 | Discover verdict drift — `RecommendationCard.tsx` | Like asked for an opinion on an unseen show. Replaced with Save for later / Not interested, matching current Qt semantics. No sentiment request is sent by these controls. |
| P1 | No in-app explanation — card title and artwork | Title led straight to MAL, artwork/match had no inspector. Cover, title, and Details now open an accessible in-app inspector; MAL is a separate, explicitly external link. |
| P1 | Silent/racy saves — `DiscoverPage.tsx` | A failed request silently restored state; concurrent whole-state responses could erase another decision. Added announced outcome/error, rollback, retry only when allowed, and serialized writes. |
| P1 | Hidden arithmetic mismatch — `ScoreRail.tsx` | The old total carried an invisible `data-drift` attribute only. A visible warning now identifies non-reconciling supplied contributions. The sample One Piece data totals 38.9 against a displayed 34.7; the UI reports this without changing either value. |
| P2 | Oversized posters / low decisions — `discover.css` | At the desktop reference size the decision row began below the viewport. Restored 152 × 228 posters and decision-first hierarchy; collapsed filter panel follows Qt's feed-first behavior. |
| P2 | Weak web semantics / compact targets — page and controls | Added an h1, named filter/sort groups, skip link, slider value text, progress semantics, larger targets, and a stronger focus indicator. Removed invalid `aria-pressed` from a noninteractive active-filter wrapper. |
| P2 | Sample/hidden states — cards and notices | Ephemeral decisions previously looked persisted; hidden cards were faded to 42% opacity. Added reset-on-reload wording, readable Set aside state, and Show again. Cards stay in the current view to permit undo. |
| P2 | Visual presentation gaps — cards and base CSS | Added genre/studio evidence, reserved title/secondary/tag rows, recoverable artwork fallback, and a content-exempt raster. Reduced-motion alternatives are explicit static states rather than a global 0.01ms override. |

Positive baseline practices retained: shared generated tokens, API-generated
types, local filtering/sorting, stable keyed cards, lazy images, signed contribution
rows, and the platform boundary for external URLs.

## Direct geometry comparison

Logical pixel coordinates, 1280 × 900, sample data, dark theme. Browser scrollbar
takes 15px of the viewport. Qt has a sidebar; React still has only its Discover shell.

| First-row measure | PySide reference | React before | React after |
| --- | ---: | ---: | ---: |
| Card width | 235 | 238.59 | 238.59 |
| Card height | 547 | 605.97 | 573.25 |
| Poster | 152 × 228 | 236.59 × 354.89 | 152 × 228 |
| Card top | 232 | 340.34 | 232.86 |
| Title top | 477 | 717.23 | 477.86 |
| Decision-row top | 543 | 920.09 | 542.17 |
| Decision-row height | 36 | 25.22 | 36 |

React's first five cards now share title, decision, and metadata baselines. The
card is 26.25px taller than Qt because the web version uses labelled utilities and
a larger metadata reservation. Five web columns versus four Qt columns reflect
the absent sidebar, not a claim of complete screen parity.

At 320px, measured document width equals the available client width (305px);
at 375px, both are 360px; at 768px, both are 753px. No horizontal page overflow.
The 375px inspector also has equal scroll/client width. Phone decision targets
are 44px high. These checks were performed with filters collapsed; expanded
filter interactions were additionally exercised at desktop width.

Nominal dark text-token contrast on `--surface`: strong 14.76:1, normal 12.11:1,
muted 5.95:1, subtle 4.82:1. These calculations do not certify every state/theme.

## Detector review

Ran Impeccable's bundled detector once on all changed web UI targets.

1. `layout-transition`, warning: the existing stepped progress bar transitions
   width. Confirmed as a single bounded progress track, not evidence of measured
   layout thrashing. Retained; profile actual operation performance before expanding
   animation work. Suggested follow-up if needed: `$impeccable optimize`.
2. `codex-grid-background`, advisory: the calibration strip in `instrument.css`.
   Not a defect here. It is part of the pinned PySide instrument identity, so the
   generic aesthetic suggestion is intentionally rejected.

## Verification and handoff

- `npm run ci`: API types in sync, TypeScript passed, **46 tests passed**.
- `npm run build`: passed; main JS 169.22kB / 54.06kB gzip, CSS 25.23kB / 5.39kB gzip.
- `pytest tests/test_card_grid_geometry.py -q`: **5 passed**, isolated/offscreen.
  The first sandboxed attempt passed its assertions but failed temporary-directory
  cleanup; rerun with cleanup permission completed successfully.
- Browser: save/undo sample state, four-title Psychological filter and clear,
  inspector open, Close/Escape, return focus, native modal background exclusion,
  desktop and phone rendering; no captured browser errors/warnings at final check.
- Regression additions cover sample persistence messaging, set-aside restoration,
  StrictMode dialog lifecycle, broken artwork, failed saves/retry, serialized writes,
  unavailable scores, and contribution mismatch disclosure.
- Fixed a Windows-only verification false alarm: schema verification now normalizes
  CRLF/LF before comparison. Generated types and Python schema were not changed.

No full Python suite, live-account write, remote generation run, Tauri package,
deployment, or release was performed. The preview uses isolated sample data at
`reports/ui-preservation-2026-09-06/sample-data`, not the user's normal app data.
The temporary Qt capture root was removed after capture; screenshots remain.

Next scoped work: validate signed-in flows and real artwork, carry over PySide's
interactive metadata filtering if desired, and test light theme, screen readers,
text zoom, and unusually long metadata. Keep recommendation explanations faithful
to supplied data. Use `$impeccable harden` for those behavior cases, then
`$impeccable polish`; do not treat this report as permission for a new visual world.
