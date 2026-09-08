# AniRec docs

Read this page first and open only what you need. Everything here is either
**live** (still describes the product or work in flight) or **historical**
(kept for citation, not for guidance).

## Live

| Document | Status | Open it when |
|---|---|---|
| [CHANGELOG.md](CHANGELOG.md) | live | You need what shipped in 1.3.0, 1.2.2, or 1.2.0. |
| [design/FRONTEND_HANDOFF.md](design/FRONTEND_HANDOFF.md) | live — the working standard | You are changing anything the user sees. This is the one to read before touching the GUI. |
| [design/ICON_HANDOFF.md](design/ICON_HANDOFF.md) | live spec | You are adding or regenerating a UI icon. Geometry rules are enforced by `scripts/build_ui_icons.py`. |
| [design/BUNDLE_HANDOFF.md](design/BUNDLE_HANDOFF.md) | live — presentation done, data blocked | You are working on series bundles. The unsolved part is franchise-relation data, not the card. |
| [design/BACKEND_HANDOFF.md](design/BACKEND_HANDOFF.md) | live — open P0s | You are on the scoring or service side. Lists what the 1.3.0 frontend work needs from the backend and has not received. |
| [release/ACCEPTANCE_TEMPLATE.md](release/ACCEPTANCE_TEMPLATE.md) | live template | You are running second-computer acceptance. Edit this file when a release changes user-visible behaviour; do not fork a per-version copy. |

## Background

| Document | Status | Open it when |
|---|---|---|
| [design/CONVERSION_TEARDOWN.md](design/CONVERSION_TEARDOWN.md) | 2026-08-26 audit | You want the reasoning behind the workstation direction and the activation funnel, not instructions. |
| [design/RECOMMENDATION_FATIGUE.md](design/RECOMMENDATION_FATIGUE.md) | design only, **not implemented** | You are about to build ignore-decay or artwork rotation. Nothing in it exists in the codebase. |
| [release/HISTORY.md](release/HISTORY.md) | historical | You need a past artifact hash, gate result, or a limitation carried forward from 1.2.x. |

## Assets

- `images/` — screenshots referenced by the root README and the changelog.
- `landing/index.html` — Scoring Bench landing page.
- `landing/workstation.html` — the workstation alternative the app now follows.

## Conventions

- **One document per subject, not per version.** Version-specific facts go in
  `CHANGELOG.md` or `release/HISTORY.md`; everything else is written in the
  present tense and edited in place.
- **A document that describes unbuilt work says so in its first three lines.**
- Retired documents are deleted, not archived in place. They stay recoverable in
  git history; the pointer to them lives in `release/HISTORY.md`.
