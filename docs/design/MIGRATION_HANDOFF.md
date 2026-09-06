# AniRec migration handoff

**Latest continuation (2026-09-06): [Latest agent handoff](LATEST_AGENT_HANDOFF.md).**
Read it first for the user's updated next-tab scope, required skills, selected
Library-led concept, portrait-poster requirement, dirty-tree transfer checklist and
the exact approval boundary. The architecture history below remains relevant.

Written 2026-09-05. **The direction here is decided; most of it is not built.**
One React page is validated, the HTTP API is tested, and the desktop shell that
would package them does not exist. PySide6 ships, is untouched, and stays that
way until a separate decision gate says otherwise.

Read this before any frontend work. If you are changing the PySide interface,
read [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md) too — it remains the visual
standard and nothing here supersedes it.

2026-09-06 follow-up: [React Discover preservation audit](REACT_PRESERVATION_AUDIT.md)
records the user's approved bounded polish, current PySide card semantics,
measured comparison, verification, and remaining migration gaps. It does not
promote the PoC to the shipping application or approve the Tauri decision gate.

---

## The one rule

**PySide is the reference implementation, not inspiration.**

The React Discover page was a proof of concept. It was allowed to differ
because it answered *"is React suitable for this interface at all?"*, not
*"does this screen match?"*. That licence ended with the answer. From the first
real migrated page:

> **Same AniRec product and UX, better frontend implementation.**

A migrated page is done when someone who used the PySide version cannot tell
anything moved, except that it feels better.

**Preserved unless approved otherwise, per change:** page structure · control
and widget semantics · button purposes · button placement where it carries
meaning · filtering · sorting · navigation · information hierarchy · card
contents · interaction patterns · terminology · visual identity · feature set ·
workflows.

The implementation underneath a control is free — a `QSlider` with a hand-drawn
`paintEvent` becoming a styled `<input type="range">` is expected. What it does,
what it is called, where it sits and what it looks like is not free.

**Spotted an improvement?** Add it to *Open UX suggestions* below and keep
going. A UX change bundled silently into migration work makes "did the
migration break this?" unanswerable, because every difference becomes a
candidate explanation for every complaint.

---

## What changed in PySide

Structural only. **No user-visible behaviour changed** — the 187 tests touching
the moved modules pass unchanged, and the full suite's only failures reproduce
identically on the commit before this work.

**Five Qt-free modules left `gui/`** into `AniRec/presentation/`:
`taste_profile` (1,178 lines), `compatibility` (399),
`recommendation_view_model` (225), `bundle_view_model` (270),
`metadata_index` (162). None ever imported Qt; living in the widget package
made them look like widget code and put a toolkit import between them and any
second client.

**`discover_filters.py` split.** The filter vocabulary (`FilterKind`,
`ActiveFilter`, `score_filter`, `episode_filter`) moved to
`presentation/filters.py`; the `QObject` that emits `changed`
(`DiscoverFilterState`) stayed in `gui/` and re-exports the names, so existing
importers are unaffected. `FilterKind`'s values double as query parameter
names, which is what lets one filter reach a Qt widget, an HTTP query string
and a React control without three spellings of "studio".

**The rule that keeps this from rotting:** `AniRec/presentation/` may import
`models`, `services`, `scoring`, `infrastructure` — **never `AniRec.gui`**.
Same for `AniRec/api/`, which additionally may never import PySide6. Both are
enforced by tests that parse imports rather than grep source, because the first
version of that test failed on its own docstring.

**Packaging:** `AniRec.spec` no longer sets `upx=True`. UPX packing is a known
antivirus heuristic trigger and bought little against a 178 MB payload. This
applies to the current PySide build regardless of everything else here.

---

## What exists beside it

None of this is wired into PySide. It runs alongside.

### `AniRec/api/` — the HTTP boundary

Re-implements no rules: every route resolves a service from `ApiContainer` and
calls the same method `gui/workers/operations.py` calls, with the same
`CancellationToken` and `progress_callback`.

| File | What it is |
|---|---|
| `container.py` | Composition root, mirroring `gui_main.main()` |
| `operations.py` | `WorkerController` with threads instead of `QThread`, a replayable log instead of signals |
| `models.py` | Pydantic models — the OpenAPI contract, and the source of truth for generated TS types |
| `security.py` | Per-launch token; the threat model is the module docstring |
| `__main__.py` | Ephemeral port, readiness handshake, single-instance lock, graceful shutdown |

Operation semantics are copied deliberately — they are what the application's
behaviour was tuned against: one running operation per
`operation_key(kind, profile_id)`, a second start refused rather than queued,
the BUG1 stale-handle retirement, cooperative cancellation, and
`started → (progress|step)* → (result|error|cancelled) → finished`.

One thing genuinely differs, and it is HTTP's fault: a Qt client connects slots
before the worker starts and cannot miss an event; an HTTP client learns the
operation id from the response that started it. So events are retained and the
stream replays from the beginning. Hence the monotonic `seq`.

### `frontend/` — React + TypeScript

One page, Discover, rendering real data through the real boundary: 114
recommendations from a live profile, score-sum invariant holding on all 114 in
the rendered DOM.

Types are **generated, not written** — `AniRec/api/models.py` is the source of
truth:

```powershell
npm run generate:api-types   # rewrite src/api/generated/schema.d.ts
npm run verify:api-types     # fail if stale — use in CI
```

`src/api/types.ts` holds only aliases into the generated file, plus SSE frame
types, which are hand-written because OpenAPI has no vocabulary for the shape
of individual event frames. That is said out loud beside them rather than
quietly fudged.

### One palette, two frontends

`scripts/build_theme.py` emits both from `AniRec/gui/design_tokens.py`:
`{dark,light}.qss` via `qss_builder.py`, and `frontend/src/styles/tokens.css`
via `css_tokens.py`. No stylesheet in `frontend/` contains a hex value. Qt
gradients are translated by computing the angle from the `qlineargradient`
vector rather than eyeballing one — the palette uses three different vectors,
and guessing would put the light source in a different place on each surface.

### Sample mode is formally ephemeral

`SampleDataService.profile_id` is `"__sample__"`, and `paths.profile_dir`
rejects it: the profile-ID pattern requires a leading alphanumeric as a
path-traversal guard.

**Intended, and it stays.** The alternative was weakening a security invariant
so one sentinel could pass, buying demonstration data a place to write it
should not have. Both frontends already resolved it identically and now say so
— the desktop via `_enter_demo_mode`'s `set_ephemeral(True)`, the API via
`FeedResponse.ephemeral`. `tests/test_ephemeral_profile_semantics.py` locks it
in both directions.

---

## The direction

```text
        AniRec/presentation/ + services/ + scoring/
                          |
          +---------------+---------------+
          |                               |
    AniRec/gui/                      AniRec/api/
    (PySide6, shipping)              (FastAPI, HTTP + SSE)
                                          |
                              +-----------+-----------+
                              |                       |
                        frontend/ in a          frontend/ in a
                        browser (later)         desktop shell
```

Python stays the source of truth for recommendation, scoring, data processing
and ML. Not transitional — it is where Python is strongest.

The desktop shell is Rust/Tauri glue only: windowing, updater, keychain, deep
links, and owning the local Python process. **No domain logic in Rust.** Moving
ONNX inference to Rust is explicitly *not* committed, and will not be revisited
until the model contract is stable and there is evidence the Python sidecar is
a real distribution problem.

---

## Proven, and not

| Claim | Status |
|---|---|
| React/CSS suits the instrument aesthetic | **Proven.** `docs/landing/workstation.html` had realised the language in 32 KB; the PoC ported it |
| CSS collapses the layout code Qt needed | **Proven.** `ReflowGrid`'s ~186 lines became four declarations; the card-height bug class became structurally impossible |
| The FastAPI boundary is clean | **Proven.** 24 boundary tests; the operation contract mapped near 1:1 |
| Real data flows end to end | **Proven.** 114 live recommendations, sum invariant intact |
| Backend lifecycle is robust | **Proven at process level.** 21 tests: ephemeral port, handshake, token, single-instance refusal, graceful exit, controlled startup failure |
| The Python payload shrinks usefully | **Measured.** API-only PyInstaller bundle is 85 MB against the PySide package's 178 MB, and serves the real feed |
| Tauri packages this cleanly | **Not proven. Not attempted.** |
| A page can migrate without drifting into redesign | **Not proven.** No page has been migrated |

The three questions were separated so they could fail independently: *is React
better for this UI*, *does the Python API boundary work*, *does Tauri package
it*. The first two are answered. The third is open.

### What "not attempted" means concretely

So nobody mistakes groundwork for working desktop support:

- **There is no `src-tauri/`.** No Tauri application has been created, built or
  run. `frontend/src/platform/tauri.ts` calls a `backend_connection` command
  that is unimplemented; `isTauri()` is false everywhere today, so the file is
  never loaded.
- **`AniRec-api.spec` is unused.** It builds the API as a standalone 85 MB
  binary and that binary was verified serving the real feed, but nothing
  spawns it. It exists to measure the payload, not to ship one.
- **A linked Windows binary was never produced**, and not for a design reason:
  building one needs the MSVC toolchain, whose installer requires interactive
  elevation. Any claim about installer size, startup latency, SmartScreen or
  antivirus behaviour for a Tauri build is therefore unmeasured and must not be
  made until someone runs it on a machine with Build Tools.

### Known test state

`pytest tests` is green apart from three failures that reproduce identically on
a clean checkout of `2a97405`, i.e. they predate this work:

- `test_gui_dashboard.py::test_returning_to_profile_reuses_the_rendered_taste_profile`
  — a real caching bug: the provider is called twice where the test asserts once.
- two `test_security_audit.py` credential-signature scans, which match on
  build artefacts under `release/` rather than on source.

Separately, `test_setup_wizard_analysis.py::test_analysis_cancel_saves_no_result_or_completion_flag`
is flaky under `-n auto` and passes reliably when run serially. None of these
were touched, and none should be "fixed" by weakening the assertion.

---

## Where the next stage stops

Tauri validation is a decision gate, not a migration. It ends with a report and
a stop.

Do **not**, during it: migrate another page · remove or modify PySide6 ·
redirect PySide through FastAPI · rewrite recommendation or ML code · move
inference to Rust · start mobile/Expo/PWA work · redesign Discover · introduce
a remote production backend · delete the existing Python packaging path.

PySide remains a working fallback throughout, because once migration starts it
is what every migrated page is checked against.

---

## Open UX suggestions

Noticed while doing other work. **None approved. None to be implemented as part
of migration work.** Here so they are neither lost nor smuggled in.

- The presentation layer carries pre-formatted strings beside its numbers
  (`mal_score` and `mal_score_text`, `year` and `year_text`). Written for
  `QLabel`, which takes a string. A browser wants the number and its own
  formatting, and a second locale would need every `_text` field rebuilt
  server-side for nothing. Worth revisiting as a contract change — separately,
  not while a page is being ported.
- Live match scores land around 27% while the landing page demonstrates ~90%.
  Already a P0 in [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md); a scoring
  calibration question, not a frontend one. The frontend must not fabricate
  better numbers to hide it.
- `docs/landing/index.html` (Scoring Bench, published) and
  `workstation.html` (what the app follows) present two different products.
  Reconciling them is a real decision nobody has made.

---

## Where to start reading

| You are | Read |
|---|---|
| changing the PySide interface | [FRONTEND_HANDOFF.md](FRONTEND_HANDOFF.md) |
| working on the API boundary | `AniRec/api/app.py`, then `operations.py` |
| securing the local service | `AniRec/api/security.py` — the threat model is the docstring |
| adding a React component | `frontend/src/styles/instrument.css`, then the Qt widget you are replacing |
| on scoring or services | [BACKEND_HANDOFF.md](BACKEND_HANDOFF.md) |
| planning post-model work | [POST_MODEL_FEATURES.md](POST_MODEL_FEATURES.md) |
