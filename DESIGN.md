# AniRec visual authority

This records the established visual world for concept work, not a new theme.
Current PySide screens and `docs/design` handoffs remain authoritative; current
implementation takes precedence over stale dimensions and obsolete button descriptions.

## Existing visual system

- Green-black ground, bone text, thin square panel boundaries, restrained raster.
- Brass marks the reader's signal and primary action; aqua carries system,
  community, and keyboard focus. Selection and focus stay distinguishable.
- Indexed left navigation: Discover, My Library, Profile, Compare, Settings.
- Shared palette in `AniRec/gui/design_tokens.py` / generated web `tokens.css`:
  background #070C09, surface #0C1410, text #C6D4C2, strong #DCE8D8,
  muted #849686, brass #D9A441, aqua #5FBFB5, border #1E2E24.
- Square to near-square corners (0–3px), compact spacing, not rounded SaaS tiles.
- Existing fonts: display/system condensed headings; mono readouts; Yu Gothic UI /
  Segoe UI for prose. Reuse shared font stacks, not a new font brand.
- Portrait artwork, crisp and unfiltered. Anime covers and their list/table
  thumbnails preserve 2:3 poster proportions (existing Discover: 152 × 228 logical
  pixels), never square crops. The user explicitly reiterated this after viewing
  the concepts; square generated placeholders are not a specification.
  No fake anime cover art in the product.
- Score rails, paired readings, compact tables, and measured labels belong to
  the interface; fake telemetry, meaningless graph decoration, and unsupported
  claims do not.
- Motion communicates state and is restrained/stepped; reduced-motion mode keeps
  the same information immediately readable.

## Scope of current concepts

Layout and information hierarchy may change in the other tabs, with the user's
permission. Each still serves its existing task: manage the library, understand
taste through evidence, compare two people, or configure the application.
Concept images are proposals, not screenshots of implemented features.

## Approved next-tab composition

The user selected concept C, **Library-led workspace**, from the three visual
boards. Treat `.impeccable/mocks/decision/library.png` as a compositional north
star subject to the factual corrections in `reports/ui-tabs-concepts/README.md`:

- Library leads with recognizable 2:3 poster cards and attaches personal-match
  and MAL evidence directly to each saved recommendation.
- Profile keeps the compact identity/metric strip, then lets named anime evidence
  carry the reading instead of filling the page with generic stat cards.
- Compare groups shared interests and disagreements around portrait title cards
  with clearly paired reader/friend scores.
- Settings remains a practical, artwork-free control surface.

Do not copy generated square placeholders, invented dates/counts, omitted global
navigation, or erroneous labels/numbers. Translate the selected topology into
semantic, responsive React rather than rasterizing the board.
