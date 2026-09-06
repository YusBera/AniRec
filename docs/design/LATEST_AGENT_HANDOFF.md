# Latest agent handoff — React preservation and selected next-tab direction

Updated 2026-09-06. **Start here before resuming this work.** This is a local working-tree handoff, not a release report.

## 1. Exact stopping point

Discover received a bounded preservation/polish pass. Library, Profile, Compare
and Settings have three visual concept boards; the user selected **C — Library-led
workspace** through the local selection page. It is approved as a compositional
north star but has not been implemented in React.

The user's latest instructions:

1. Treat the current PySide screens and AniRec handoffs as visual authority.
2. Use Impeccable critique/audit in preservation mode and UI/UX Pro Max for specific accessibility and React questions.
3. Measure current geometry and behavior; compare the React result directly with PySide.
4. Other tabs may be reimagined, including useful recommendation-site features/layouts/widgets, while preserving their core purpose and AniRec's theme/feel.
5. Visual concepts were shown first; the user selected concept C through the
   selection page. Resume from that approved direction rather than asking again.
6. **Anime images are portrait posters, not squares. Preserve 2:3 aspect ratio; existing Discover posters are 152 × 228 logical pixels.** This applies to smaller table/list thumbnails too. Do not interpret square initials in generated mockups as an artwork specification.
7. The user is transferring the project to another agent and requested this handoff, not additional UI work.

Opening/re-attaching concept A was a Windows image-path troubleshooting exchange,
**not approval of A**. The later selection-page answer explicitly chose C. The
poster correction followed and is a binding refinement of C: every anime image,
including compact thumbnails, remains a 2:3 portrait poster.

This latest scope supersedes older blanket prohibitions on proposing tab redesigns, but does not authorize a new visual identity, removing PySide, Tauri packaging, deployment, or changing recommendation algorithms.

## 2. Read order and source precedence

1. This file.
2. `PRODUCT.md` and `DESIGN.md` at the repository root.
3. `docs/design/REACT_PRESERVATION_AUDIT.md` — actual Discover changes, measurements and scoped verification.
4. `reports/ui-tabs-concepts/README.md` — approved direction, concept limitations and exact data corrections.
5. `docs/design/MIGRATION_HANDOFF.md`, `FRONTEND_HANDOFF.md`, `ICON_HANDOFF.md`; `BACKEND_HANDOFF.md` before API/service changes. Read relevant additional handoffs for affected domains.
6. Actual Qt widgets/services and current React source before copying older prose.

User instructions and verified current behavior outrank stale handoff descriptions. Generated image text never outranks source data. Keep green-black ground, bone text, brass personal signals/actions, aqua community/system/focus, compact typography, thin near-square borders and the existing icon family. No generic SaaS restyle, fake telemetry, invented scores or artificial status lamps.

## 3. Required skills and available tools

Skills are installed outside this repository on the originating machine; transferring the project does **not** install them on another agent. Discover the receiving agent's equivalents. Read each selected `SKILL.md` completely and its required references before using it; do not merely cite the names. If unavailable, disclose that and arrange the appropriate skill rather than claiming to have run it.

| Skill/tool | Requirement and use | Original local entry point |
| --- | --- | --- |
| Impeccable | Required for UI critique/audit, composition, preservation polish and its approval/verification workflow. Existing AniRec identity is pinned; generic anti-pattern warnings do not overrule it. | `C:/Users/yusuf/.codex/skills/impeccable/SKILL.md` |
| UI/UX Pro Max | Required for targeted accessibility, keyboard navigation, state preservation, responsive and React implementation questions. This app is React 18; do not copy React 19-only advice or substitute a generated brand/design system. | `C:/Users/yusuf/.codex/skills/ui-ux-pro-max/SKILL.md` |
| Imagegen | Conditional: use when revising/generating raster concept boards. Inspect actual PySide reference images first. Keep exact prompt sidecars/provenance; obtain approval before implementation. Not required for semantic HTML/CSS or house SVG icons. | `C:/Users/yusuf/.codex/skills/.system/imagegen/SKILL.md` |
| Standalone critique | Available but optional; Impeccable covers the current required critique/audit. Avoid duplicate ceremonial reviews. | `C:/Users/yusuf/.codex/skills/critique/SKILL.md` |
| Browser automation + screenshots | Required for actual web inspection and interaction checks after implementation. Current agent used the in-app browser through CUA. Use the receiving harness's supported equivalent. | Harness-provided, not a repo dependency |
| Qt capture harness | Use isolated sample data and the secondary display for visual authority. Never disturb the user's primary monitor or normal profile. | `reports/ui-tabs-concepts/capture_tabs.py`, `reports/ui-preservation-2026-09-06/capture_qt.py` |

The prior work used Impeccable audit/polish and then surface-composition exploration; UI/UX Pro Max searches covered focus/target sizing/async errors, navigation/back/deep links and state preservation. A new agent should load the skills again, not assume skill instructions persist through this document.

No new external design-service account/plugin is necessary for the current next step. Earlier research links (Vercel Design, 21st.dev, TasteSkill and codebase-memory-mcp) are optional resources, not proof those services/tools were installed and not visual authorities over AniRec. Do not install persistent hooks, telemetry, credential stores or unrelated plugins implicitly.

## 4. Concepts and approval state

All three boards show Library, Profile, Compare and Settings. **C is selected:**

| Choice | File | Structural idea / tradeoff |
| --- | --- | --- |
| A — Comparison matrix | `.impeccable/mocks/decision/matrix.png` | Aligned evidence/score rows; easy comparison, less artwork-forward. |
| B — Split workbench | `.impeccable/mocks/decision/workbench.png` | Browse list beside persistent inspector; strong context, needs an intentional narrow-screen detail view. |
| C — Library-led workspace | `.impeccable/mocks/decision/library.png` | Poster-led browsing and attached evidence; closer to original cards, lower visible density. |

Use **repository copies**, not images under the previous agent's global generated-images directory. Each has a same-stem JSON sidecar with exact prompt; only `library.json` is `approved: true`. All three contain generated text/data errors: see the concept README before treating anything literally. In particular, 412 is the friend's anime count, not match score; Personal match is a percentage, MAL score is /10; added dates and saved counts are illustrative. Source values must be used in implementation. No fake covers; actual covers use 2:3 posters and appropriate portrait fallbacks.

PySide authority captures: `reports/ui-tabs-concepts/pyside-{library,profile,compare,settings}.png`, captured at 1440 × 1000 in an isolated sample session on the secondary display. These are real captures; the concept boards are not. The capture harness directly supplies the bundled Profile payload, so its screenshot is not proof that normal Profile navigation works end to end.

Impeccable state to resume rather than restart blindly:

- `.impeccable/config.json`: `buildPath: comp`.
- `.impeccable/build/state.json`: comps are closed and the `spec` phase is open.
  The approved portable comp is `.impeccable/mocks/library-led.png`; no UI code
  has been written for the other tabs. The two alternatives and all exact-prompt
  sidecars are also in `.impeccable/mocks/` so the phase gate is reproducible.
- Surface seed `e94eea46`; prewritten structures in `reports/ui-tabs-concepts/structures.md`; selected indices 4, 2, 5. These map to A/B/C above, not new theme choices.
- `.impeccable/tab-concepts.json`: selection-page payload referencing portable repo image paths.
- Original local selection page was `http://127.0.0.1:56766/`, key `fdd64048`.
  Its answer was `optionId: library`. This is an ephemeral local process, not a
  hosted or transferable URL; the approved JSON sidecar is the portable record.
- Original CLI: `C:/Users/yusuf/.codex/skills/impeccable/scripts/impeccable.cmd`.
  After reading the skill, resume its current `build-phase` workflow from the
  checked-in state; do not restart the visual-direction round without user cause.

The exact choice and poster constraint are recorded in `DESIGN.md`. These boards contain four scaled desktop views, so derive per-tab layouts and responsive behavior deliberately; do not implement the board as one giant image or rasterize UI text/controls. Follow the installed skill's review gates, including any required independent reviewer, without presenting a failed/missing review as passed.

## 5. Existing Discover work — preserve it

Verified branch at handoff: `feat/react-fastapi-boundary`; HEAD `968ec2d614c4c4becd1999bfe2e24e7391699e31`. There are **uncommitted modified and untracked files**. Do not reset, clean, overwrite or switch to a supposedly newer checkout without preserving this work. No fetch/latest-remote check was performed for this documentation handoff.

The previous preservation pass includes:

- `frontend/src/discover/RecommendationCard.tsx`: Save for later / Not interested, not Like/Dislike; title/artwork open an inspector, MAL is separate; 152 × 228 posters, fallback and metadata.
- New `RecommendationDetails.tsx`: native dialog, full explanation/metadata/synopsis, StrictMode-safe asynchronous close behavior.
- `DiscoverPage.tsx` and `Controls.tsx`: collapsible controls, optimistic decisions with serialized writes/rollback/retry, truthful sample/reset notices, semantics and focus.
- `ScoreRail.tsx`: visible supplied-contribution mismatch warning; no fabricated reconciliation of sample data.
- `discover.css`, `styles/base.css`, `styles/instrument.css`: aligned card geometry, legible targets, content-safe raster, reduced-motion handling. Shared Python tokens/scoring were not changed.
- Tests in `DiscoverPage.test.tsx`, `ScoreRail.test.tsx` and `test/setup.ts`.
- `frontend/scripts/generate-api-types.mjs`: CRLF/LF normalization for verification; generated schema remains Python-owned.

See `REACT_PRESERVATION_AUDIT.md` for measurements and limits. Preserve all other dirty/untracked files too; not every file in `reports/` was created by this work.

## 6. Verification evidence and limits

These scoped checks were rerun immediately before the handoff commit:

- `npm run ci` in `frontend`: generated API types in sync, TypeScript passed,
  46 tests passed. The sandbox attempt could not spawn project Python (`EPERM`);
  the cleanup-permitted rerun passed.
- `npm run build`: passed; JS 169.22 kB / 54.06 kB gzip, CSS 25.23 kB / 5.39 kB gzip.
- `pytest tests/test_card_grid_geometry.py -q`: 5 passed on the cleanup-permitted
  run. The sandbox attempt also passed all five assertions but reported teardown
  errors because Windows temp-directory cleanup was denied.
- Browser checks included sample save/undo, filter/clear, inspector Close/Escape/focus return, desktop and 320/375/768px widths; no horizontal overflow in the checked states.
- PySide/React Discover geometry compared at 1280 × 900; evidence in `reports/ui-preservation-2026-09-06/`.

Not verified by this work: full Python suite, real-account writes, full onboarding, screen-reader certification, light theme, exhaustive text zoom/localization, large-feed performance, complete tab migration, Tauri packaging, deployment/release. The older migration handoff lists pre-existing/flaky Python failures; reproduce before attributing them to new changes. Do not call all tests green on the strength of the scoped results above.

## 7. Architecture and safe local startup

React 18 + TypeScript + Vite consume the loopback FastAPI boundary. Python owns scoring, recommendation, profiles and domain services. PySide remains the shipping fallback. No `src-tauri/` app has been implemented; existing frontend Tauri adapter imports are not proof of desktop support.

Current API exposes health/system state, Discover feed/feedback and operations (including SSE), but no dedicated Library/Profile/Compare/Settings read routes. Before building those tabs, map each proposed control to an existing service and add only the scoped boundary needed after approval. Do not equate sample payloads or an operation name with proven live capability. Browser-native folder/account/data actions require honest capability handling.

Original browser preview: `http://127.0.0.1:5173/`; API loopback `127.0.0.1:8770`; Vite defaults to proxying that port (`ANIREC_API` overrides it). These processes may not survive transfer. Inspect listeners before launching duplicates or touching locks. Use a project environment with dependencies installed; inspect the repository's setup docs instead of assuming a global Python is suitable.

Example commands, each from the indicated working directory, in separate terminals:

```powershell
# Repository root, with the project's Python environment active.
python -m AniRec.api --root-override reports/ui-preservation-2026-09-06/sample-data --port 8770
```

```powershell
# frontend/
npm run dev -- --host 127.0.0.1
# After approved implementation:
npm run ci
npm run build
```

Keep sample data isolated from normal APPDATA/profiles/tokens. Confirm sample mode in the UI. Never copy credentials into a handoff or expose the local API beyond loopback. On Windows image paths use `C:/Users/...`, **not `/C:/Users/...`** (the latter caused os error 123). Prefer paths resolved from the transferred repository, not this machine's username.

## 8. Transfer checklist and next-agent assignment

- This work is being committed and pushed to `feat/react-fastapi-boundary` after
  this handoff was written. The receiving agent should still verify branch/HEAD
  and preserve any additional local changes before switching or pulling.
- Transfer/pull the changed frontend files plus `RecommendationDetails.tsx`, this handoff, the audit, `PRODUCT.md`, `DESIGN.md`, `.impeccable/` concept images/JSON/state/payload, and the two relevant report folders' screenshots/geometry/scripts/README. Include existing source and lockfiles.
- Do not send credentials, real profiles, `.env`, tokens, caches/logs, runtime `api.lock`, `node_modules`, `.venv`, or unrelated build artifacts. A Git-only transfer omits untracked work unless explicitly included. No archive, commit or push was performed by this handoff task.
- Skills/tool binaries live outside the repo: acquire or point the next agent at the required skills separately. Local server URLs and process IDs are not portable state.
- Recheck branch/diff and read the required docs/skills; preserve unrelated work.
- Resume from approved concept C and explain the 2:3 poster correction and
  generated-label limitations in any implementation brief. Do not mistake the
  earlier concept-A attachment for the selection; the page answer selected C.
- Implement bounded tab work tied to real services, retaining the existing Discover behavior; test keyboard/focus, empty/loading/error/sample states, navigation state, long titles, portrait artwork and narrow layouts. Compare directly with PySide and the approved composition, and report remaining capability gaps honestly.

Suggested message to the receiving agent:

> Read `docs/design/LATEST_AGENT_HANDOFF.md` first and load the required Impeccable and UI/UX Pro Max skills. Preserve the current PySide visual authority and Discover work. Concept C, Library-led workspace, is approved; resume its checked-in Impeccable phase, keep every anime image a 2:3 portrait poster, and implement only truthful capabilities.
