# Project Instructions

@docs/START_HERE.md
@docs/DOMAIN_RULES.md
@docs/CURRENT_TASK.md

## Purpose of This File

This file defines how an agent must work within this repository.

The imported documentation gives a short project orientation, the product
invariants, and the current scope. Open architecture, decisions, code maps, and
feature references only when the task requires them; `docs/README.md` is the
index.

Completed tasks are recorded in `docs/TASK_HISTORY.md`. Read it only when the
history of a previous task is relevant; it is not imported by default.

Treat those documents as the authoritative project context.

Do not repeatedly rediscover or rewrite information already documented there.

---

# Repository Identity

**Check which checkout you are in before quoting a line number.**

This repository is the superset tree and the one the running application is
served from. A sibling checkout at `projects/AniRec` exists on an older branch;
it has no `frontend/src/workspace/`, no `AniRec/api/workspace.py`, and no
`AniRec/services/workspace_service.py`. Work targeted at this project belongs
here unless the user says otherwise.

The training and evaluation project is a separate root (`AniRecTrainer`), and the
scraper is a third (`AniRecDataCollector`). Neither is modified from this repo.

---

# Context and Credit Optimization

Use repository context conservatively.

Before reading files:

1. Read the imported project documentation.
2. Consult `docs/CODEMAP.md` to locate the owning file before searching. It is
   the index of where endpoints, services, engines, components, and stores live.
   Search the repository only when the code map does not answer the question.
3. Identify the current task and its acceptance criteria.
4. Determine which module owns the requested behaviour.
5. Inspect only the files that are directly relevant.
6. Expand the search only when a concrete dependency requires it.

Keep `docs/CODEMAP.md` accurate: when a change adds, moves, or renames a public
endpoint, service, engine, React route, or persisted file, update the
corresponding row in the same change. An inaccurate map costs more than no map.

Do not scan the entire repository by default.

Do not read `frontend/node_modules/`, `.venv/`, `build/`, `dist/`, `output/`,
`__pycache__/`, `reports/` artefacts, or `.impeccable/` unless a concrete
diagnostic requires it.

Do not reread large files already inspected during the current session unless
they have changed or a specific detail is required.

Prefer targeted search by:

* Endpoint path
* Service or engine class name
* React component or hook name
* CSS selector or design token
* Persisted filename
* Error code or message
* Test name

---

# Task Discipline

Implement only the task described in `docs/CURRENT_TASK.md` unless the user
explicitly changes the scope.

Before making changes:

1. Restate the task in no more than five concise lines.
2. Identify the owning module.
3. List the files likely to require changes.
4. Identify relevant existing tests and patterns.
5. Report any direct conflict with documented architecture or decisions.

Do not produce a long implementation plan for a small task.

Do not implement future roadmap items because they seem useful.

Do not combine unrelated cleanup, refactoring, or feature work with the current task.

Do not modify unrelated files.

Do not rename public endpoints, persisted files, or modules unless required by the task.

When a requirement is slightly ambiguous, inspect existing conventions and choose
the smallest reversible implementation consistent with the documentation.

Ask the user only when the ambiguity could materially affect:

* Public API contract shape
* Persisted data format or migration
* Recommendation output or ranking behaviour
* What a score or explanation claims to mean
* Account identity or data isolation
* Security, credentials, or MyAnimeList terms compliance
* Backward compatibility with an existing profile directory

---

# Change Strategy

Prefer small, reviewable patches over broad rewrites.

Modify existing files in place.

Do not regenerate complete files when a focused edit is sufficient.

Do not replace working implementations solely to match a preferred style.

Reuse established repository patterns before creating new abstractions.

Do not introduce new libraries, architectural layers, base classes, state
managers, or CSS frameworks unless the current task demonstrates a concrete need.

Keep API routes thin. Business behaviour belongs in `AniRec/services/` or
`AniRec/application/`, not in `AniRec/api/app.py`.

Do not expose internal dataclasses or DataFrames directly through the API. Use
the explicit Pydantic models in `AniRec/api/models.py`, and regenerate
`frontend/src/api/generated/schema.d.ts` when they change.

---

# Architecture Boundaries

Python owns recommendation and scoring behaviour. The frontend renders what the
API returns and never recomputes a score, a match percentage, or an explanation.

The recommender is being separated into three stages. Respect the boundary even
where the current code still fuses them:

* **Candidate generation** decides which titles are eligible.
* **Scoring** orders them.
* **Explanation** says why, and must reconcile with the score it explains.

Domain and service code must not depend on PySide, on HTTP types, or on React.

`AniRec/gui/` is deprecated. Do not add features to it, and do not treat it as
the visual or behavioural authority for new work. Bug fixes needed to keep the
developer tool usable are acceptable; new surfaces are not.

---

# Recommendation and Evidence Rules

These are the rules the product is judged on. `docs/DOMAIN_RULES.md` has the full
set and the reasoning.

Never invent a score, a rating, a count, a date, a cover image, or an
explanation. A value that is unavailable is shown as unavailable.

Every displayed number must trace to a value the API returned.

An explanation must reconcile with the score it explains. Do not show a
contributor list that omits terms which moved the score, and do not attach a
reason string to a ranking that did not produce it.

Do not recommend a title whose prerequisite the user has not consumed.

Do not present an uncalibrated model output as a percentage.

Sample and demonstration data must remain visibly labelled and must never be
written into a real profile.

---

# Data, Identity, and Security Rules

Never read, display, commit, or modify secrets. Do not inspect `.env`, `.env.*`,
credential files, private keys, or production configuration.

Never log access tokens, refresh tokens, client secrets, client IDs, or password
material. `AniRec/infrastructure/logging_config.py` holds the redaction set; extend it rather
than working around it.

Do not add scraping of MyAnimeList from this repository. Content is obtained
through the API or from the existing collector snapshot. `docs/DOMAIN_RULES.md`
records the terms that constrain this and the open questions on it.

Do not widen the local API's exposure. Every state-mutating route must remain
origin-checked, and the bound host must remain loopback.

User-supplied identifiers must never select another account's data. Derive scope
from authenticated server-side context, never from a request field.

---

# Frontend Rules

React 18 and TypeScript. Vite. No CSS framework.

Colours, spacing, and type come from `frontend/src/styles/tokens.css`. Do not
introduce hex values or off-scale pixel values in component CSS.

The workspace is dark-only today. Do not add a theme switcher without a decision.

Every interactive surface must work at 375px width, by keyboard, and with a
screen reader. Touch targets are at least 44px on coarse pointers; check the
computed value rather than the rule, because stylesheet order has defeated this
before.

Anime artwork is a 2:3 portrait poster everywhere, including compact thumbnails.

Do not mount unbounded lists. A feed that can grow must paginate or virtualise.

---

# Testing Rules

Every behavioural change must include or update appropriate tests.

Prioritise tests for:

* API contract shape and error envelopes
* Persistence round-trips and corrupt-input handling
* Recommendation invariants (contributions reconcile, exclusions hold)
* Optimistic UI rollback and request serialisation
* Long-running operation lifecycle and cancellation

Do not create tests that merely repeat implementation details. Tests must verify
externally observable behaviour and important invariants.

Do not write a test whose fixture takes a code path production never takes. A
fixture that omits real columns and silently triggers a legacy compatibility
branch is worse than no test, because it reports success for untested code.

For bug fixes: add a failing test, confirm it fails for the expected reason,
implement the smallest correction, then run the relevant scope.

Before declaring completion, run the smallest relevant commands that validate the
change. Run targeted `pytest` for Python behavior. Run `npm run ci` from
`frontend/` when frontend code, an HTTP response model, or generated API types
changed.

## Review Agent Cadence

Do not use a sub-agent for documentation, copy, or a narrow internal refactor.
Use one final adversarial review for ranking, eligibility, catalogue routing,
persistence, or API-contract changes. Use an early design review plus a final
review only for training, migration, authentication, security, or release work.
Re-review only a reported blocker and the invariants it affects.

---

# Command and Tool Efficiency

Group related file reads and searches.

Prefer `git diff --stat`, `git diff -- <paths>`, targeted `pytest` paths, vitest
filters, and direct file reads.

Avoid repeated full-repository scans, repeated full builds after each edit,
dumping generated files, and reading binary or cache artefacts.

Never start a dev server or an API process without checking for an existing
listener first.

---

# Communication Style

Be concise and implementation-focused.

Do not explain basic Python, FastAPI, React, TypeScript, or pandas concepts
unless asked.

Do not repeat the project definition in every response.

Do not narrate every tool call.

Provide early notice only when you discover:

* A conflict with a documented decision
* A security or credentials exposure
* A data-loss path
* A recommendation output that is visibly wrong
* A test failure that changes the implementation approach

When presenting code changes, avoid pasting complete files unless requested.
Prefer file paths, concise summaries, and focused diffs.

---

# Completion Report

After completing a task, report only:

## Changed

* Files modified
* API or persisted-format changes
* Behaviour implemented

## Verification

* Commands executed
* Tests executed
* Result, stated honestly, including failures

## Decisions

* Assumptions made
* Decisions introduced

## Remaining

* Known risk
* Deferred work
* Recommended next task

Do not produce a lengthy retrospective unless requested.

Update `docs/CURRENT_TASK.md` completion notes after the implementation.

Update `docs/DECISIONS.md` only when a durable decision was introduced.

Update `docs/ARCHITECTURE.md` only when the implemented architecture changed.

Do not modify documentation solely to restate unchanged information.

---

# Definition of Done

A task is complete only when:

* Acceptance criteria are satisfied
* No displayed value is invented, and unavailable values say so
* Explanations reconcile with the scores they explain
* Credentials and tokens remain unlogged and unexposed
* Relevant tests pass, and failures are reported rather than suppressed
* Any changed user-facing surface works at 375px, by keyboard, and with a screen reader
* No unrelated functionality was added
* `docs/CODEMAP.md` reflects any moved or renamed public thing
* The completion report identifies remaining risks honestly
