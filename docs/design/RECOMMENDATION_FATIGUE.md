# Design note: repeated recommendations and artwork rotation

Status: **design only, not implemented.** Nothing described here exists in the
codebase yet. It is written so the shape of the work is agreed before any of it
is built.

The problem: a title that keeps appearing and keeps being ignored costs a slot
in every feed it appears in, and the current engine has no way to notice. A
recommendation is either excluded (rejected, hidden, already watched) or fully
eligible. There is no state between "never seen" and "explicitly rejected",
which is exactly where an ignored title sits.

## 1. Detecting a title the user keeps passing over

### What counts as being shown

Not "present in the result set". A title scrolled past is a weaker signal than
one that sat at the top of the feed. Impressions should be recorded when a card
is actually on screen, which the explorer already knows: the lazy cover loader
computes visibility to decide what to fetch, and the same check identifies what
was genuinely displayed. Recording at generation time would count titles the
user never scrolled to.

Debounce per session. Scrolling a card out of view and back is one impression,
not two.

### What counts as engagement

Any of: opening details, opening the MyAnimeList page, saving to Watch Later,
liking, or rejecting. Rejecting is engagement even though it is negative,
because the user did decide, and the existing exclusion already handles it.

### Proposed threshold

Fatigue after **3 impressions with no engagement**, and only when those
impressions are on separate days, or at least separated by a full regeneration.
Three views in one sitting is one browsing session, not a pattern.

The day condition matters more than the count. Someone who opens AniRec twice
in an evening should not have their feed reshuffled for it.

### Where the state lives

`recommendation_state.json` already holds per-profile, per-anime state (hidden,
watch later, feedback), and already has a versioned schema. Add:

```
"impressions": { "<mal_id>": { "count": 3, "last_seen": "2026-08-25", "days": 3 } }
```

Same file, same schema bump. This is deliberately not a new store: it is the
same kind of local, per-profile fact as the ones already there.

Prune aggressively. An entry for a title the user has since engaged with, or
that has not appeared for months, is noise.

## 2. Acting on it in the ranker

Fatigue should be a **score term, not a filter**. Filtering would silently
remove a title the user simply had not got to yet, and would be invisible and
unexplainable. `scoring/ranking.py` already blends weighted terms and
renormalises when one is unavailable, so this fits the existing shape:

```
final = w_content·content + w_collab·collab + w_quality·quality − w_fatigue·fatigue
fatigue = min(1, (impressions_without_engagement − threshold + 1) / span)
```

Two properties this must preserve, both already covered by
`tests/test_scoring_invariants.py`:

- the contributions must still sum to the displayed percentage, so fatigue
  appears in the breakdown as a named negative part rather than an invisible
  adjustment;
- the calibration must stay batch independent, so a title's percentage still
  does not depend on what was ranked beside it.

Being visible in the breakdown is the point. "Shown often, not opened" is a
reason a user can read and disagree with.

Decay it. Fatigue that never fades permanently buries a title the user might
want in a year. Halving every 90 days is a reasonable starting point, tuned
against the same held-out evaluation the neural work will use.

## 3. Artwork and presentation variants

MyAnimeList exposes a `pictures` field on the detail endpoint: several images
per title. `AnimeGraphService` already fetches detail pages for seed titles,
caches them per profile with a TTL, and degrades to nothing on failure, so
variants can ride along on the request it already makes rather than adding one.

Storage: extend the existing `anime_graph.json` cache entry rather than adding a
store. Cache the URLs; the cover cache on disk already handles the images.

Selection: deterministic, keyed by `(mal_id, impression_count)`, so the same
title shows a different image the second and third time it appears but does not
flicker between renders of the same feed. Random selection would change the
artwork mid-scroll.

Presentation variants beyond artwork are worth more than a second image:

- lead with a different genre in the explanation, if the title matches on more
  than one;
- surface the collaborative reason instead of the content one where the graph
  supports it, since "people who loved X recommend this" is a different
  argument from "matches your interest in Drama";
- promote it into the list layout, where the reason text carries more weight
  than the poster.

Honesty constraint: a variant may change **which true reason is emphasised**.
It must never state a reason the score does not support. The whole value of the
explanation is that it reflects the arithmetic.

## 4. Reducing fatigue in the interface

Ordered by cost, cheapest first.

**Say what happened.** When a title is demoted for fatigue, its breakdown shows
it. No new interface, and it makes the behaviour inspectable.

**A dismissal that is not a rejection.** "Not now" alongside "Not for me".
Rejecting teaches the taste profile something false when the user simply is not
in the mood. This is the highest value item here and the least work: it is a
third feedback state on a model that already carries two.

**Reshuffle rather than refill.** When several picks come back fatigued,
re-rank the existing candidate pool with a higher softmax temperature instead
of fetching more. The Adventurousness slider already maps to that temperature,
so the mechanism exists.

**"Try something different?"** offering a deliberately higher-variance batch.
Only when fatigue is measured across several titles, and only as an offer.
Silently widening the net makes the recommendations look worse for no visible
reason.

**A/B artwork variants** are listed last on purpose. Measuring them properly
needs impression and engagement volume that a single-user desktop app does not
have. Per-user, the result would be noise. Worth revisiting only if the corpus
work makes aggregate measurement possible, and only with genuine consent.

## 5. What would need deciding before building

- Does an impression require the card to be on screen, or is a rendered card
  enough? This drives whether the explorer needs new visibility tracking or can
  reuse what the cover loader already computes.
- Is fatigue per profile only? Almost certainly yes, but it interacts with the
  sample library, which deliberately persists nothing.
- Does the impression count survive "Delete all local data"? It should: it is
  profile-local behavioural data and belongs in the same scope as feedback.
- Should fatigue influence the taste profile at all, or only ranking? The
  recommendation is only ranking. Ignoring a title says something about that
  title, not reliably about its genres, and the taste profile is the one thing
  that must not learn from weak signals.
