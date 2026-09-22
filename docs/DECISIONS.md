# Decisions

Durable decisions and the reasoning behind them. Newest first. Do not reopen an
accepted decision without a new reason from the user.

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

## D-008 - The match percentage is split or calibrated before launch
**2026-09-20 - Open, decision required**

The current "Personal match" figure cannot ship to the open web as is. Three
options: split it into separate taste and community figures; calibrate it against
held-out ratings so the number means something checkable; or drop the percentage
for ranks or tiers.

*Why:* measurement shows the displayed figure is substantially a restatement of
the community score printed beside it, with an unreachable ceiling. A local
application's odd number is a curiosity; a public product's is the thing people
screenshot. Splitting is the cheapest and can ship first. See
`docs/design/RECOMMENDER_EVALUATION.md`.

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
