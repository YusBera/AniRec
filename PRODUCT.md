# AniRec

<!-- impeccable:product-schema 1 -->

## Platform

web

## Product Purpose

Help people choose anime through recommendations they can inspect and understand,
manage their library, understand their taste, and compare interests and ratings.
This record scopes the React migration; PySide remains the shipping application.

## Operating Context

React 18 and TypeScript consume a local FastAPI boundary over existing Python
services. Discover is implemented as a browser proof of concept. Other desktop
surfaces are being explored for migration. No Tauri shell is currently implemented.

## Capabilities and Constraints

- Discover supports filtering, sorting, explanation inspection, saving for later,
  and setting prospects aside. Discover decisions are not ratings of unseen shows.
- PySide supplies Library, Profile, Compare, and Settings reference surfaces.
- Profile and Compare include explicitly labelled bundled demonstration payloads;
  a demonstration is not evidence that a live backend capability exists.
- Sample data must remain distinguishable and must not write to a real profile.
- API schemas are generated from Python models; UI must not invent scores or
  infer unavailable connection state from unrelated signals.

## Brand Commitments

The user named PySide screens and AniRec handoffs as authority and authorized
reimagining tab layouts while preserving the core purpose, theme, and feel.
The user requested visual concepts before implementation for the other tabs.

## Evidence on Hand

`docs/design/MIGRATION_HANDOFF.md`, `docs/design/FRONTEND_HANDOFF.md`,
`docs/design/REACT_PRESERVATION_AUDIT.md`, current `AniRec/gui` implementations,
shared design tokens, and bundled sample payloads in `AniRec/gui/resources/sample`.
Live isolated PySide captures supplement stale handoff geometry where necessary.

## Product Principles

- Preserve useful workflows while improving clarity and layout.
- Every score, status, comparison, and explanation must have evidence.
- Keep real profile data separate from sample data and design demonstrations.
- Make the interface usable with a keyboard and at narrow web viewport widths.

## Approved Direction and Open Decisions

The user selected concept C, the Library-led workspace, through the concept
selection page. Anime artwork must be 2:3 portrait posters, including compact
list/table thumbnails; square shapes in generated concepts are not authoritative.
Live Profile/Compare service availability and full account setup in the browser
must still be validated before those features are represented as production-ready.
