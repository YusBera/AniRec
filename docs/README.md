# AniRec docs

Read this page first and open only what you need. Everything is **live**
(describes the product or work in flight) or **historical** (kept for citation,
not guidance).

Start with the row that matches what you are about to touch. Opening more than
that costs context you will want later.

## Live

| Document | Status | Open it when |
|---|---|---|
| [design/MIGRATION_HANDOFF.md](design/MIGRATION_HANDOFF.md) | direction decided, mostly unbuilt | **Any frontend work.** PySide is the reference implementation for the React migration; this says what that forbids. |
| [design/FRONTEND_HANDOFF.md](design/FRONTEND_HANDOFF.md) | the working standard | Changing anything the user sees in the PySide app. Palette, geometry, motion, and the Qt traps that have already caused bugs. |
| [design/BACKEND_HANDOFF.md](design/BACKEND_HANDOFF.md) | open P0s | Scoring or service work. What the frontend needs and has not received — including the match-score calibration P0. |
| [design/POST_MODEL_FEATURES.md](design/POST_MODEL_FEATURES.md) | unbuilt, ordered | Work that only becomes possible once the neural recommender ships. Impression logging must land first; it cannot be added retroactively. |
| [design/BUNDLE_HANDOFF.md](design/BUNDLE_HANDOFF.md) | presentation done, data blocked | Series bundles. The unsolved part is franchise-relation data, not the card. |
| [design/ICON_HANDOFF.md](design/ICON_HANDOFF.md) | live spec | Adding or regenerating a UI icon. Geometry is enforced by `scripts/build_ui_icons.py`. |
| [CHANGELOG.md](CHANGELOG.md) | live | What shipped in 1.3.0, 1.2.2 or 1.2.0. |
| [release/ACCEPTANCE_TEMPLATE.md](release/ACCEPTANCE_TEMPLATE.md) | live template | Running second-computer acceptance. Edit in place; do not fork a per-version copy. |

## Historical

| Document | Open it when |
|---|---|
| [release/HISTORY.md](release/HISTORY.md) | You need a past artifact hash, gate result, a limitation carried forward from 1.2.x, or the pointer to a retired document. |

## Assets

- `images/` — screenshots referenced by the root README and the changelog.
- `landing/index.html` — Scoring Bench, the published landing page.
- `landing/workstation.html` — the direction the application itself follows.

These two disagree, deliberately and unreconciled. Read
[design/MIGRATION_HANDOFF.md](design/MIGRATION_HANDOFF.md) before changing either.

## Conventions

- **One document per subject, not per version.** Version-specific facts go in
  `CHANGELOG.md` or `release/HISTORY.md`; everything else is present tense and
  edited in place.
- **A document describing unbuilt work says so in its first three lines.**
- **Retired documents are deleted, not archived in place.** They stay
  recoverable in git history; the pointer lives in `release/HISTORY.md`.
- **Write for one reader opening one file.** A document that restates another
  is a document that will disagree with it later. Link instead.
