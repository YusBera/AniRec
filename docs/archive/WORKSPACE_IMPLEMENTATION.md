# React workspace implementation — 2026-09-07

Historical report for the initial bounded implementation. The later functional
extension and final verification supersede its read-only/sample-only limits and
local publishing status. Start with [LATEST_AGENT_HANDOFF.md](LATEST_AGENT_HANDOFF.md).

Branch: `feat/react-fastapi-boundary`, cloned at
`9b8268cec1a1001144d0cd8a0dd6b254efc5bfab`. Changes are local and uncommitted.

## Implemented boundary

- Indexed five-route workspace with hash navigation, heading focus, and retained
  mounted page state. Discover's existing feed, filters, decisions and inspector
  remain shared with Library.
- Library: Watch Later and Not interested collections, search, card/list/table views,
  inspect and undo. Sample decisions last across tabs and reset on reload.
  Saved IDs absent from the current feed are disclosed without invented metadata.
- Profile: local provider identity, supplied fingerprint readings and higher/lower
  title evidence. Bundled example is an explicit choice. Missing local data never
  silently falls back to sample data. Other desktop Profile sections are not yet
  rendered in this React slice.
- Compare: explicit bundled comparisons, paired scores and source section order.
  Live comparison remains unavailable. The example labels 412 as anime count,
  78% as compatibility, 96 shared and 74 both rated.
- Settings: read-only saved preferences, grouped by purpose. Client ID presence
  is not connection status. No secrets or fake browser account/folder/delete
  actions. Editing preferences stays in PySide.
- New authenticated read routes: `/api/workspace/profile`, `/compare`, `/settings`.
  They adapt existing services/providers; no scoring changes or GUI imports.
  Types remain generated from FastAPI OpenAPI. The generator now passes parsed
  JSON to openapi-typescript to handle Unicode Windows checkout paths.

## Verification

- `npm run ci`: generated schema in sync, TypeScript passed, **52 tests passed**.
  Added integrated shared-save/navigation/table/undo, absent metadata, error/retry,
  stale local response after sample selection, failed-cover recovery and Compare
  selector focus during delayed loading coverage.
- `npm run build`: passed. Main JS 190.44 kB / 59.22 kB gzip;
  CSS 34.45 kB / 7.11 kB gzip.
- `.venv/Scripts/python.exe -m pytest tests/test_api_workspace.py tests/test_api_boundary.py -q`:
  **29 passed**. Includes actual isolated local CSV-to-profile read, explicit sample
  boundaries, preserved counts, unknown-sample refusal and credential redaction.
- Live Chromium through CUA at 1440×1000 and 390×844: navigation, retained Library
  search/list, sample saves, missing posters, local unavailable states, explicit
  samples, inspector Escape/focus return. Source poster containers measured
  152×228 desktop / 80×120 mobile Library cards, 100×150 desktop / 80×120 mobile
  Profile, including long titles. Table thumbnails measured 48×72. Library list
  is 80×120 desktop / 64×96 mobile. Mobile inspector tested.
  First Library title measured y630.75 and Profile evidence y800.94 at390×844.
  Profile disclosure opens/closes with Enter and keeps focus on its summary.
  Compare keyboard selection keeps focus; long sample name does not overflow.
- Captures in `.impeccable/review/`: each route has desktop/mobile PNGs;
  Library additionally has mobile list and desktop/mobile table captures,
  plus 1536×1024 `hero-repro.png`.
  Viewport captures include browser scrollbar width; full-page images can exceed
  viewport height. Invalid resize/full-page captures were replaced with valid
  evidence; table captures use the viewport mode. See capture-metadata.json.
- Impeccable detector on `frontend/src/workspace`: `[]`; recorded once.

## Review state and limits

Spec and plates gates closed. Hero gate recorded **41.1%, failed**, because the
approved 1536×1024 PNG contains four scaled routes and the capture contains one
actual route. The original user-approved handoff calls C a compositional north
star and overrides generated fonts, square art and false values. These corrections
are binding; no four-screen raster UI or false pixel-gate pass was created.
See `LIBRARY_WORKSPACE_SPEC.md`, `.impeccable/build/state.json`, hero diff evidence
and `.impeccable/review/finish-review.md` for the independent review outcome.
The first full review requested six UI fixes and workflow closure. UI fixes were
implemented together: compact mobile Library cards/notices, mobile Profile
disclosure, semantic Table, larger brass compatibility, aqua genre chips, and
Compare focus preservation. `.impeccable/review/finish-verdict.md` records their
subsequent independent disposition. The initial force command refused the
handoff's conceptual-board rationale. The user then explicitly approved removing
literal pixel matching and retaining C as composition reference. Supported force
transitions now record that approval for hero and responsive, preserving failed
raw scores. See `composition-approval.md` and the verdict's workflow addendum.
No pixel-diff pass is claimed, and no UI changes were made for this closure.

No real account was connected for browser QA. This is not full tab parity, a full
Python-suite result, screen-reader certification, light-theme support, Tauri
packaging or a release. PySide GUI, shared design tokens and algorithms were not
changed. No commit, push or deployment was made.

## Isolated preview

From repository root: `python -m AniRec.api --root-override reports/ui-workspace-sample --port 8770`.
From `frontend`: `npm run dev -- --host 127.0.0.1`.
The ignored sample root, API lock, environment and dependencies must not be
transferred as user data. Start at `http://127.0.0.1:5173/#/discover`, save titles,
then open My Library. Profile and Compare samples are explicit on-page choices.
