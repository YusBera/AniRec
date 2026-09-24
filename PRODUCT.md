# AniRec

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

Help people choose anime through recommendations they can inspect and understand,
manage their library, understand their taste, and compare interests and ratings.

The web client is the product. Mobile follows it; a third-party recommendation
API follows that. See `docs/PROJECT_DEFINITION.md` for the binding order.

## Operating Context

React 18 and TypeScript over a FastAPI boundary on the existing Python services.
Discover, My Library, Profile, Compare and Settings are implemented in the
browser workspace.

The PySide application is deprecated and is being retired to a development and
power-user tool (`docs/DECISIONS.md` D-004). It is not the shipping application,
but its design is the reference the web client follows (D-016).

The service layer behind the API still assumes one user in one process. Accounts,
per-request identity, and an owned catalogue are the named gaps in
`docs/ARCHITECTURE.md`.

## Capabilities and Constraints

- Discover supports filtering, sorting, explanation inspection, saving for later,
  and setting prospects aside. Discover decisions are not ratings of unseen shows.
- A web surface that instructs the reader to install a desktop application is a
  defect, not a limitation.
- Profile and Compare include explicitly labelled bundled demonstration payloads;
  a demonstration is not evidence that a live backend capability exists.
- Sample data must remain distinguishable and must not write to a real profile.
- API schemas are generated from Python models; the UI must not invent scores or
  infer unavailable connection state from unrelated signals.
- Recommendation and evidence rules are binding and live in `docs/DOMAIN_RULES.md`.

## Brand Commitments

The established visual world - green-black ground, bone text, brass personal
signals, aqua community and focus, compact typography, thin near-square borders,
2:3 portrait posters - is preserved. `DESIGN.md` records it.

That world is now carried by the web client, which owns its own layout decisions.
Preserving the feel does not mean reproducing desktop geometry.

## Evidence on Hand

`docs/RECOMMENDER_EVALUATION.md` for measured ranking behaviour.
`docs/archive/REACT_PRESERVATION_AUDIT.md`, `docs/archive/FRONTEND_HANDOFF.md` and
`docs/archive/MIGRATION_HANDOFF.md` for the migration record. Shared design tokens
and bundled sample payloads in `AniRec/gui/resources/sample`.

## Product Principles

- Preserve useful workflows while improving clarity and layout.
- Every score, status, comparison, and explanation must have evidence.
- Keep real profile data separate from sample data and design demonstrations.
- Make the interface usable with a keyboard, by a screen reader, and at 375px.
- Do not recommend a continuation of a story the reader has not started.

## Open Decisions

Recorded in `docs/DECISIONS.md`. The two that block launch messaging: what the
match figure claims to mean (D-008), and which ranking engine ships (D-006).
Account setup in the browser must exist before the product can be described as
usable without the desktop application.
