# Bundle recommendations — handoff

Series bundles: when a franchise has several entries (seasons, movies, OVAs,
specials), recommend it once as a stacked card that expands to show its
members, instead of as several unrelated cards or not at all.

The **presentation** is designed, prototyped and measured. This document is
about the one thing that is not solved: the app cannot currently tell whether
a franchise is one the user has already started, for exactly the franchises a
bundle would want to show.

---

## The product rule

> A bundle is recommended only if the user has not watched **any** entry in
> the series.

This is the right rule, and it is worth understanding why it fits rather than
fights the existing scoring.

`AniRec/scoring/collaborative.py` already withholds continuations:

```python
SEQUEL_RELATIONS = frozenset({
    "sequel", "prequel", "side_story", "parent_story",
    "alternative_version", "alternative_setting", "full_story", "summary",
})
```

with the stated reasoning that *"the user almost certainly knows these
already, so they are withheld from recommendations instead of being boosted."*

That reasoning holds only once the user has seen something in the franchise.
If they have seen none of it, the whole series is new to them and the argument
does not apply. So the rule extends the existing logic rather than overriding
it: **known franchise → withhold the rest; unknown franchise → offer the whole
thing, once, as a bundle.**

---

## What the code does today

`franchise_exclusions(graph)` (`collaborative.py:61`) walks a relation graph
and collects every `mal_id` reachable by a `SEQUEL_RELATIONS` edge.

The graph it walks is built in `AniRec/application/pipeline.py:598`:

```python
seeds = select_seeds(rated)                     # rated = completed, User Score > 0
graph = self._anime_graph.build_graph([mal_id for mal_id, _weight in seeds], ...)
return collaborative_scores(seeds, graph), franchise_exclusions(graph)
```

And `select_seeds` (`collaborative.py:40`) keeps only titles the user rated
**above their own mean** (`weight > 0`), capped at `DEFAULT_SEED_LIMIT = 40`.

So the exclusion set today means, precisely:

> continuations of the up-to-40 titles the user completed **and rated above
> their personal average**.

That is narrower than "everything related to anything you have watched", in
two ways that both matter here.

---

## Blocker 1 — no relation edges exist for unwatched franchises

`AnimeGraphService.build_graph` (`anime_graph_service.py:97`) fetches detail
only for the ids it is given:

```python
wanted  = [int(value) for value in seed_ids if value is not None]
missing = [mal_id for mal_id in wanted if mal_id not in graph]
```

Seed ids are the user's own highly-rated titles. Nothing anywhere fetches
`related_anime` for a **candidate**.

This is the blocker. The franchises the product rule wants to bundle are
exactly the ones the user has *not* watched — so they are never seeds, so
their relation edges are never fetched, so the app has no idea those
candidates belong to one another.

The data shape is fine when it exists (`anime_graph.json`, keyed by mal_id):

```json
{ "fetched_at": "...", "recommendations": [...],
  "related": [{"mal_id": 9253, "relation": "sequel"}, ...] }
```

`GRAPH_FIELDS = "id,recommendations,related_anime"` already requests it. The
gap is *which ids get fetched*, not what comes back.

### Cost of closing it

Fetching is rate-limited to `REQUESTS_PER_SECOND = 4.0`, one detail call per
id, cached in `anime_graph.json` and reused across runs.

| approach | extra calls per run | verdict |
|---|---|---|
| bundle only within the existing pool | 0 | nearly free, catches almost nothing — edges only radiate from seeds |
| fetch relations for the top N candidates | N (N/4 seconds) | the plausible option; N = 20 costs ~5s on a cold cache, ~0s warm |
| fetch for the whole candidate pool | `candidate_pool_size` = 150 | ~38s cold. Too slow for a feed refresh |

Recommendation: the middle row, N configurable, cache-first so the cost is
paid once per franchise rather than once per run.

---

## Blocker 2 — the watched check must not use the exclusion set

It is tempting to reuse `franchise_exclusions` to answer "has the user watched
part of this series". It does not answer that question:

- it only covers titles rated **above** the user's mean, so a franchise the
  user watched and disliked is absent from it;
- it is capped at 40 seeds, so a franchise outside the cap is absent from it;
- it is keyed on relations *from* seeds, not on membership.

Using it would produce the worst failure this feature can have: presenting
"a series you have not started" to someone who has seen half of it and rated
it poorly.

The check must be against the **full completed list** — every `Anime ID` in
`completed_anime.csv`, regardless of score — intersected with the franchise's
membership.

---

## Blocker 3 — relations are pairwise, franchises are not

`related` is a flat list of `(mal_id, relation)` pairs per title. A franchise
is the connected component containing them, so grouping needs a union-find or
equivalent over `SEQUEL_RELATIONS` edges.

Two consequences:

- **Partial bundles are the normal case, not the edge case.** A component is
  only as complete as the edges fetched for it, so a five-entry franchise with
  two fetched members looks like a two-entry franchise.
- **Ordering is not given.** `relation_type` says "sequel", not "season 2".
  Presentation order has to come from something else — `start_date`, or
  `media_type` grouping with TV first — because a bundle that lists the movie
  before the first season is worse than no bundle.

---

## What is already settled

The presentation side is done and measured; a runnable prototype lives in the
scratchpad (`bundle_prototype.py`) with these decisions baked in.

- **The collapsed bundle occupies exactly one cover's footprint** — 132x198,
  the canonical 2:3 frame, with the stack's shingles folded into the artwork
  so every title on the row shares a baseline. A bundle pins that frame even
  though single covers now float 108–176 wide with their artwork: a 2x2 tile
  block only stays poster-shaped at 132 (tiles measure 61x92, aspect 0.66).
- **Three covers and a count, or four covers at exactly four.** Three plus a
  "+1" is worse than showing all four, so the count starts at five.
- **The bundle's number is the mean of its members**, not the best. Best-of
  would rank every bundle by its strongest entry and make bundles
  systematically outscore the single cards beside them. The spread is printed
  next to it (`RANGE 61–94%`) so the mean cannot quietly mislead.
- **Entries are evidence; the info block decides.** Inside the panel the
  entry cards are poster, title, meta and score only. Every action lives in
  the info block, which is two cells wide and one cell tall and carries the
  mean, the `ScoreTrack` rail decomposing it, the explanation, and
  `Not for me` / `Later` / `Hide` / `Like the franchise`.
- **The expansion is its own full-width row** inserted after the bundle's row.
  Nothing above it is touched, so the clicked card measures 0px of movement
  without any scroll-anchor correction.

### Motion, and what it costs

Profiled per reveal frame, with fourteen cards on screen:

```
container layout invalidate + activate     0.11 ms
repaint of the visible viewport           14.76 ms
a whole reveal frame                      15.62 ms
```

Layout is not the cost; **painting is**, at ~96% of a 60fps budget. The real
app's feed measures 11.66ms for the same card count, so this is inherent to
the widget tree rather than to the prototype.

Two mitigations are in the prototype and should carry over:

- the content below the panel is photographed once and blitted at a moving
  offset while the real rows have `setUpdatesEnabled(False)`, and the panel
  itself is revealed as a cached pixmap slice — 16.05 → 13.41 ms per frame;
- the reveal runs 150ms, linear. Shorter means fewer frames to drop, and
  260ms of linear travel over a 734px panel simply read as slow.

Panels are built during layout and kept at zero height, so a click only starts
an animation: the click handler went from 44ms to 2ms, and the first frame
from 64ms to 19ms after the press.

If it still reads as heavy once integrated, the next move is design, not
optimisation: reveal less at once.

---

## Still undecided

**What `Like the franchise` does to the model.** `taste_feedback_service`
records feedback per anime. A franchise-level Like has to either fan out to
every member, apply only to the best match, or the model needs a new
franchise-level signal. Nothing in the UI can settle this.

---

## Order of work

1. Presentation, driven by a bundle input the pipeline can supply later.
   Nothing here depends on the blockers.
2. Grouping: connected components over `SEQUEL_RELATIONS`, plus ordering.
3. The watched check against the full completed list (Blocker 2).
4. Candidate relation fetching (Blocker 1) — the piece with a real cost.
