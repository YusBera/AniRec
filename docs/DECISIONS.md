# Decisions

Durable decisions and the reasoning behind them. Newest first. Do not reopen an
accepted decision without a new reason from the user.

---

## D-014 - AniRec account data isolation (direction accepted; local mode open)
**2026-09-23 - Hosted direction accepted; account implementation pending local-mode choice**

D-002 already chooses AniRec-owned accounts. This decision is about how one
signed-in reader's data is separated from another's. The current shared active
profile cannot serve as account scope. Request-supplied profile IDs could once
choose local state, which the same-day API fix closed; see
`ACCOUNT_SCOPE_INVENTORY.md`.

Across every storage option, the AniRec account ID is assigned by the server.
A MAL identity is an attribute of an import, never an account ID or a storage
key. A hosted deployment requires server-side sessions, checked ownership of
each imported MAL list, and a migration/claim step for existing local profiles.
MAL login remains optional for public-list imports.

1. **Account directories (smallest transition).** Store each reader's settings,
   imports, results, decisions and activity under an account-specific root.
   Bind requests to that root from the session, with imports keyed beneath it.
   Existing file services can mostly remain, but cross-process writes, backup,
   deletion and multi-worker coordination stay our responsibility.
2. **Account-scoped database (accepted hosted direction).** Store account-owned
   *records* there: identity, import ownership, settings, saved decisions, votes
   and activity. The existing activity SQLite store already demonstrates schema
   migration for one record type. Scope mutable records by the server-assigned
   account ID and use transactions. Keep catalogue/model artefacts shared; bulk
   ranking snapshots, per-ranking archives and generated feeds remain files
   addressed by IDs owned by database records. Export and deletion must cover
   both records and referenced files; activity remains opt-in and retention-
   bounded.
3. **One isolated runtime/data root per account (ruled out for hosting).** It
   would reuse the single-user application but incur a runtime and deployment
   cost for every reader.

**Open before login or migration code:** decide whether the current local
loopback product stays a file-backed single-user mode, or runs the same database
schema as a one-account hosted deployment. This choice changes the migration
and claim path, so no account, login, session or migration code starts until it
is made. Preserve existing local profiles until their owner explicitly claims
or exports them.

**Independent present-tense fixes:** API request fields no longer select a
profile for feedback or operations; they are checked against the active local
profile. `RecommendationStateService.save()` remains a whole-state replacement
and can erase a newer field change when given an old snapshot. A later
implementation must give that operation an expected-version check or make it
private; no change to its persisted schema is authorized here.

---

## D-011 - Adventurousness is a bounded, deterministic rank leap
**2026-09-22 - Accepted**

Feed selection is deterministic and happens once, after ranking and final
eligibility, in one shared policy (`AniRec/scoring/selection.py`). The top
title is always served. Adventurousness `a` (stored as `randomness_factor`)
lets a title move at most `2 * (a - 1)` rank positions ahead when it is less
redundant with titles already chosen; `a = 1` is rank order. Redundancy uses
only verified catalogue facets present on both titles. A pair with no
comparable facet earns no novelty, partial metadata is compared over shared
facets only, and no franchise identity is inferred.

*Why:* D-007 requires the random sampler to be replaced with an explicit
diversity mechanism. A bounded, rank-position leap keeps the control's meaning
checkable and independent of engine score scales. It never changes
eligibility or any score.

---

## D-010 - Final eligibility is shared across ranking engines
**2026-09-21 - Accepted**

Every primary and fallback candidate pool passes through one versioned final
eligibility policy immediately before scoring. The policy records aggregate
exclusion reasons and catalogue provenance; rankers may retain defensive checks
but do not define different product eligibility rules.

When both a candidate row and the verified catalogue contain release, airing,
rating, or media-type facts, either source may make the title ineligible. A
candidate overlay cannot weaken a catalogue restriction.

*Why:* model availability must not decide whether AniRec can recommend a future,
restricted, unsupported-media, already-known, or prerequisite-blocked title. A
shared boundary also lets offline replay measure what the product can serve.

---

## D-009 - Scoring input is a generic interaction list
**2026-09-20 - Accepted**

The scoring stage takes `(item_id, signal, weight, timestamp)` rather than a
MyAnimeList list payload.

*Why:* it is the only concession the third-priority partner API needs now, and it
costs nothing. A hosting platform's users have no MyAnimeList account, so a
scorer that assumes one cannot serve them. Everything else partner-facing
(multi-tenancy, owned catalogue, stateless scoring) is already required by
web-first.

---

## D-013 - Likes and dislikes are collected, not fed
**2026-09-22 - Accepted (user decision). Revises the schema 3 retirement.**

Explicit likes and dislikes are collected again. Each vote is stored in the
profile's `recommendation_state.json` with:
- when it was cast;
- what was shown: the ranking ID, the engine's rank, the feed position, the
  engine and catalogue versions, and the selection policy and
  adventurousness;
- the served row's genres and title.

Attribution, genres and title are taken on the server from the served row,
but only when the vote names the feed it was cast on (`feed_id`) and that
feed is still the one served. A vote from a stale screen, or for a title
outside the feed, is kept unattributed with the client's genres and title.
Only the latest vote per title is kept; re-voting replaces its attribution.

Votes do not influence ranking, selection or explanations anywhere:
- the web API passes no taste adjustments;
- the desktop client no longer re-sorts its feed by votes;
- a test fixes that a generated feed is identical with and without votes.

How votes feed the ranker is decided right before production, using this
attributed data.

*Why:* the user wants the signal collected now so it can be evaluated later.
The schema 3 concern still stands: a like is an opinion formed before
watching, and a vote kept without context cannot be weighed. Attribution
supplies that context. Keeping votes out of ranking until then means an
unvalidated signal cannot quietly change what readers see.

---

## D-012 - Explanations come from the engine that ranked
**2026-09-22 - Accepted**

"Why was this recommended to me?" is answered from the ranking that produced
the pick, after selection, for the rows served:

- The heuristic returns its exact additive score parts. Taste parts are backed
  by the reader's genuine ratings; community rating and similar viewers are
  labelled as not about their taste.
- The sequence model is explained by counterfactual removal. It is rerun
  without each of the reader's history genres and each history title, and the
  pick's score drop and rank are measured among the same eligible candidates.
  The results are deterministic, overlapping, and never presented as shares.
- An engine that cannot explain says so.

Sampled Shapley attribution was measured and rejected. In a session
experiment against the installed bundle, at 16 orders the top genre agreed
between independent samples for only 35% of synthetic-history picks, and it
added about 27 s per feed. The experiment script was not retained in this
repository, so these figures are a recorded observation, not reproducible
evidence.

*Why:* D-006 and the domain rules forbid borrowing one engine's reasons for
another's ranking. Removal effects are checkable ("without this title, #4
becomes #337") and cheap enough (about 4 s) to compute at generation.

---

## D-008 - The match percentage is split or calibrated before launch
**2026-09-20 - Resolved 2026-09-22: replaced by a rank**

Resolution: the percentage is retired for every engine, and the API no longer
sends it. Personal fit is shown as the engine's rank among its eligible
candidates ("#4 of 13,458"; the pool size differs by engine). The MAL
community score stays separate. Calibration remains possible later, after the
Goal 4 evaluation. See D-012 for the explanation behind the rank.

The current "Personal match" figure cannot ship to the open web as is. Three
options: split it into separate taste and community figures; calibrate it against
held-out ratings so the number means something checkable; or drop the percentage
for ranks or tiers.

*Why:* measurement shows the displayed figure is substantially a restatement of
the community score printed beside it, with an unreachable ceiling. A local
application's odd number is a curiosity; a public product's is the thing people
screenshot. Splitting is the cheapest and can ship first. See
`docs/RECOMMENDER_EVALUATION.md`.

---

## D-007 - The selection sampler is replaced, not deleted
**2026-09-20 - Accepted**

The uniform random selection from the ranked pool is removed only together with
an explicit diversity mechanism.

*Why:* it discards most of the ranking, and it costs the better ranker more. But
it was also doing diversity work by accident, and next-item accuracy does not
penalise a feed of ten near-identical titles. Removing it alone improves the
metric and worsens the feed.

---

## D-006 - The engine choice stays open behind a three-stage contract
**2026-09-20 - Accepted**

Candidate generation, scoring, and explanation become separate stages. Both the
heuristic and the sequence engine stay pluggable. No engine is selected yet.

*Why:* the engine is roughly the fourth most important problem, behind candidate
generation, the selection policy, and the prerequisite gate, all of which are
engine-agnostic. The comparison also depends on an untested question about
whether the sequence model's advantage rests on genuine viewing order or on a
bulk-edit artifact in the training data. Deciding now would be deciding blind.

---

## D-005 - The API is a real contract from the start
**2026-09-20 - Accepted**

Versioned routes, pagination, compression, explicit auth, and no server-rendered
text duplicated alongside raw values.

*Why:* mobile second and partner API third both need the same discipline, and
retrofitting a contract onto component-shaped payloads is more expensive than
writing one. This is cheap now and not later.

---

## D-004 - PySide is deprecated
**2026-09-20 - Accepted. Supersedes prior "PySide holds visual authority".**

`AniRec/gui/` becomes a development and power-user tool. No new surfaces. The web
client is the product and its own visual authority.

*Why:* web-first. The prior arrangement made the browser a viewer for state
another application produced, which is why several web surfaces still instruct
the reader to install the desktop application.

---

## D-003 - AniRec owns its catalogue
**2026-09-20 - Accepted**

Candidates come from an AniRec-owned catalogue sourced from the existing
collector snapshot, not from a per-user, per-run fetch of a third-party top list.

*Why:* it removes the third-party popularity prefix from candidate generation
and most per-user catalogue traffic. The installed bundle supplies verified
direct prerequisite relations; the broader collaborative graph still uses
per-title MAL requests/cache until the collector relation graph replaces it.
Any recall effect requires a retained evaluation; the historical heuristic
candidate-pool figures are not reproducible.

---

## D-002 - AniRec owns accounts; MyAnimeList is one importer
**2026-09-20 - Accepted**

Readers have AniRec accounts. Importing a MyAnimeList list is one path in, with
AniList planned next.

*Why:* MyAnimeList-only login makes AniRec a client of one service, inherits its
terms and outages, turns every visitor without an account into a bounce, and
makes the third-priority partner API nearly impossible. Owning identity turns a
terms question into a per-source question. The cost is building accounts and
storage.

---

## D-001 - Web first, mobile second, partner API third
**2026-09-20 - Accepted**

*Why:* stated product direction. The ordering is binding when priorities
conflict: a desktop-only capability is not shipped, and partner-API work does not
begin before the public product works.
