# Latest agent handoff — Library-led workspace

Updated 2026-09-07. Read this first. Prepared for review on another PC in
`YusBera/AniRec`, branch `codex/library-led-workspace-handoff`, based on
`feat/react-fastapi-boundary` at commit
`9b8268cec1a1001144d0cd8a0dd6b254efc5bfab`.

At publication preparation, the remote source branch had advanced to
`059bf918310db047c9ad94a0e139a7645772b81e`. Those later remote changes were not
merged into this reviewed local snapshot. This new branch preserves the completed
work without overwriting the source branch; assess divergence before a later merge.

The authorized workspace implementation and requested verification are complete.
**The full Python suite is not green: 738 passed, 2 failed.** The failures and
remaining product limits are documented below. This branch is a review handoff,
not a deployment, packaged release, or merge into the original branch.

## Read order and binding decisions

1. This file, then `PRODUCT.md` and `DESIGN.md`.
2. `docs/design/LIBRARY_WORKSPACE_SPEC.md` and `WORKSPACE_FUNCTIONAL_EXTENSION.md`.
3. `docs/design/REACT_PRESERVATION_AUDIT.md` and
   `reports/ui-tabs-concepts/README.md` for Discover preservation and concept provenance.
4. Relevant `MIGRATION_HANDOFF.md`, `FRONTEND_HANDOFF.md`, `BACKEND_HANDOFF.md`
   and `ICON_HANDOFF.md` before changes to their domains.
5. Current source and verification reports. `WORKSPACE_IMPLEMENTATION.md` describes
   the earlier bounded implementation; its read-only/sample-only limits are historical.

Preserve PySide's visual authority and the existing Discover work. Concept C,
Library-led workspace, is approved as a composition reference. Do not reopen the
A/B/C decision without a new reason from the user. Every anime image and fallback,
including compact thumbnails, must be a **2:3 portrait poster**. Discover's reference
poster is 152 × 228 logical pixels. Generated concept text, counts and square
placeholders are not data or artwork specifications.

Retain green-black ground, bone text, brass personal signals/actions, aqua
community/system/focus, compact typography, thin near-square borders and house
icons. Python owns recommendation/scoring behavior. Show unavailable values
honestly; do not invent metadata, history, personal matches or compatibility.

## Required skills

Before UI work, read the complete Impeccable and UI/UX Pro Max skills and their
required references. They were used on the originating machine at:

- `C:/Users/yusuf/.codex/skills/impeccable/SKILL.md`
- `C:/Users/yusuf/.codex/skills/ui-ux-pro-max/SKILL.md`

These machine-local installations are not transferred by cloning. Find or install
the receiving agent's equivalents from https://impeccable.style/ and
https://ui-ux-pro-max-skill.nextlevelbuilder.io/ if necessary; do not claim to have
loaded unavailable skills. Apply Impeccable in preservation mode and UI/UX Pro Max
for targeted accessibility/React questions. React is 18, not 19.

## Implemented behavior

- **Workspace:** Discover, Library, Profile, Compare and Settings hash routes;
  heading focus, route scroll/state preservation and responsive navigation.
- **Discover:** existing feed, filters, decisions and inspector preserved and
  shared with Library.
- **Library:** Watch Later / Not interested, search, card/list/table views, inspect
  and undo. Saved metadata can come from the full saved result and local
  completed/top/candidate CSVs beyond the visible feed. Explicit MAL resolution
  is available for missing saved titles with a configured Client ID. Metadata-only
  cards have N/A personal match; network-resolved metadata lasts for the mounted
  page session. Sample decisions reset on reload.
- **Profile:** local identity and supplied analysis, including archetype,
  higher/lower evidence, highly ranked low-rated titles, hidden gems, histogram,
  genre/studio disclosures, eras/seasons, habits and timeline. Missing statistics
  remain unavailable; sample mode requires explicit opt-in.
- **Compare:** joins the active local completed snapshot with a named public MAL
  completed list. Shows source counts, both scores, absolute differences and
  separate unrated shared titles. Live compatibility is N/A because no aggregate
  algorithm exists. Explicit sample mode remains labelled and separate. Invalid
  responses and foreign pagination URLs are rejected. NSFW preference scopes the
  remote titles returned.
- **Settings:** validated allowlisted saved preferences, dirty/save/error/discard
  states; errors preserve edits. Credentials and unexposed settings are retained.
  Unreadable settings cannot be overwritten with defaults. Desktop appearance
  values do not change the browser theme. Account/folder/delete actions remain
  desktop-only and are presented as unavailable in the browser.
- **PySide cache repair:** successful local Profile loading now sets its loaded
  profile ID and clears dirty state. Sample loading invalidates that local cache;
  the misplaced undefined `profile_id` reference was removed. This changes
  behavior only; PySide visual styling and shared design tokens are preserved.

Main code: `frontend/src/workspace/`, `frontend/src/discover/DiscoverPage.tsx`,
`AniRec/api/workspace.py`, `AniRec/services/workspace_service.py`, and
`AniRec/gui/main_window.py`. API routes share the existing token boundary.
Types in `frontend/src/api/generated/schema.d.ts` are generated from FastAPI,
including workspace Pydantic models. The generator now passes parsed JSON to
openapi-typescript to support Unicode Windows checkout paths.

## Verification completed

| Check | Result and limit |
| --- | --- |
| Frontend CI | 56 tests passed; TypeScript and generated schema verification passed |
| Production build | Passed; main JS 200.34 kB / 61.83 kB gzip, CSS 35.66 kB / 7.34 kB gzip |
| Scoped Python | 56 passed across workspace, API boundary, settings/tokens, taste profile and MAL mapping |
| Desktop dashboard tests | All 10 passed after the Profile cache repair |
| Full Python suite | **738 passed, 2 failed, 740 total**, 4327.76 seconds; completed after the cache repair |
| Two distinct real MAL accounts | API check passed; existing local NeoBalls_ snapshot against actual remote Kuroboshi_ completed list |

Full-suite command, from repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short -rA --junitxml=reports/workspace-full-tests.xml
```

Evidence: `reports/workspace-full-tests-summary.md` and
`reports/workspace-full-tests.xml`. Failures are
`test_repository_contains_no_real_credential_signatures` and
`test_binary_assets_carry_no_credential_signatures` in `tests/test_security_audit.py`.
The diagnostic scan found all 15 flagged files under ignored
`frontend/node_modules/`, using only the generic 32-hex pattern. No scanned file
outside node_modules matched. Inspected text contexts were public identifiers,
example values and numeric comments. The scan excludes Python environments and
build directories but does not exclude node_modules. Tests were not modified to
suppress these failures. A future test-scope fix should retain detection in
project-owned files; do not report this recorded run as passing.

Distinct-account evidence: `reports/workspace-live-compare-check.json`.
HTTP 200, non-sample response: local 167, remote 555, shared 108, both rated 89,
unrated shared 19. All 108 score pairs and supplied differences were checked
against the actual sources. No duplicate/missing shared IDs; compatibility null.
The active account remained NeoBalls_. This uses an existing local snapshot,
not a fresh local sync, and certifies the API integration rather than populated
live-result browser rendering. User-authorized accounts:
https://myanimelist.net/profile/NeoBalls_ and
https://myanimelist.net/profile/Kuroboshi_. No real-account writes were performed.

## UI evidence and Impeccable state

Portable reference: `.impeccable/mocks/library-led.png`; approval/provenance
sidecars and alternatives remain checked in. PySide authority captures live in
`reports/ui-tabs-concepts/pyside-*.png`. They used isolated sample data; they do
not by themselves establish normal Profile navigation behavior.

The original Impeccable workflow is closed. The user explicitly approved dropping
literal pixel matching for the four-screen composition board. Supported forced
hero/responsive transitions and their reason are recorded in build state and
`.impeccable/review/composition-approval.md`. The raw **41.1% FAIL** pixel comparison
is preserved; it is not a pixel pass. Do not restart an obsolete spec phase or
change fonts, poster proportions or real values to match generated pixels.

Original UI correction verdict: `.impeccable/review/finish-verdict.md`.
Extension review: `.impeccable/review/extension/finish-review.md` and
`finish-verdict.md`. Its ship disposition covers the resolved stale-design-doc
finding, not a fresh whole-surface certificate, full-suite success or the separate
PySide cache repair. Those review records predate the final distinct-account
check and this authorized handoff and retain their historical wording.

Nine required extension captures include Library/Profile/Compare/Settings desktop
and mobile plus Profile analysis. Profile full-page exports and readable crops
cover the added sections. Settings save 5 to 7 survived reload in an isolated
fixture; saved Monster metadata absent from the test feed loaded from CSV with
N/A match. Keyboard disclosures and checked mobile layouts worked; inspected
posters remained 2:3. Compare captures show missing connection/sample states,
not populated real-account comparison. Capture exports can omit scrollbars or
rescale pixels; see the packet. The invalid Library full-page export was replaced.

## Fresh Windows PC setup

Clone the review branch, then work from the repository root:

```powershell
git clone --branch codex/library-led-workspace-handoff https://github.com/YusBera/AniRec.git
cd AniRec
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
cd frontend
npm ci
npm run ci
npm run build
```

Use a compatible installed Python and Node runtime. The originating Python
verification used Python 3.10; recreate the virtual environment, do not copy it.
`requirements-dev.txt` includes the application, API and test dependencies.
The type generator prefers the repository `.venv`, falling back to PATH Python.

Run two terminals. In the repository root, start an isolated data directory:

```powershell
.\.venv\Scripts\python.exe -m AniRec.api --root-override reports/ui-workspace-sample --port 8770
```

In `frontend/`:

```powershell
npm run dev -- --host 127.0.0.1
```

Open http://127.0.0.1:5173/#/library (other routes use their lowercase names).
Vite proxies `/api` to loopback port 8770; `ANIREC_API` overrides that target.
Check existing listeners before starting duplicates. The ignored isolated root,
real profile data, credentials, dependencies and virtual environment are not
included in this branch. An empty root uses labelled sample/empty/unavailable
states; it will not reproduce the private live account data or discarded browser
fixture automatically. Configure real accounts privately through the existing
desktop workflow when needed. Keep sample writes isolated from normal account data.

## Remaining limits and next work

1. Resolve the two dependency-scanner false-positive failures in a separately
   reviewed change, preserving project credential detection, then rerun affected
   checks and the full suite if required. This handoff does not conceal the failures.
2. Populated real Compare browser inspection is still additional coverage;
   the two-account API check is complete.
3. Network-resolved Library metadata is not persisted beyond the mounted session.
   Browser account setup, folder selection/deletion, complete desktop parity,
   aggregate compatibility, Tauri packaging and deployment remain outside this work.
4. Full accessibility certification, exhaustive localization/zoom/light-theme and
   large-feed performance were not established by the scoped captures/tests.

No extra implementation is implied by receiving this handoff. Review the branch
and choose further scope with the user. Preserve current work and evidence; do
not reset the checkout to the original feature branch or silently mark old failures
as resolved. For future UI changes, load both required skills and resume from the
actual checked-in state.
