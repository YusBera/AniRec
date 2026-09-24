# Architecture

Two sections: what is implemented today, and what web-first requires. The gap
between them is the roadmap. Do not describe the target as if it were built.

---

## As Implemented Today

### Runtime topology

```
browser (Vite dev server, :5173)
  -> /api proxied to loopback :8770
       FastAPI (AniRec/api) -- single process, single user
         -> AniRec/application  (pipeline, operations)
         -> AniRec/services     (recommendation, sync, profile, settings, workspace)
         -> AniRec/scoring      (heuristic engine, optional ONNX engine)
         -> CSV + JSON files under %APPDATA%/AniRec/profiles/<profile_id>/
```

A PySide desktop application (`AniRec/gui`) calls the same service layer
in-process. It is deprecated; see `docs/DECISIONS.md`.

### Layers

| Layer | Owns |
| --- | --- |
| `AniRec/api` | HTTP routes, request/response models, error envelopes, SSE operation stream |
| `AniRec/application` | The recommendation pipeline and long-running operation handlers |
| `AniRec/services` | Recommendation, MAL sync, profile, settings, taste profile, workspace reads |
| `AniRec/scoring` | Ranking engines, taste profile construction, feature extraction |
| `AniRec/presentation` | View models shared by both clients |
| `AniRec/infrastructure` | MAL client, CSV and JSON storage, paths |
| `frontend/src` | React workspace, API client, platform abstraction |

### Identity

There is no account system. Identity is ambient process state: a single
"active profile" read from one JSON file, used by every route. No route takes a
caller identity, and `profile_id` on a request is a hint defaulted from that
global, not an authorisation subject.

### Persistence

CSV and JSON files in a per-profile directory. `CsvStorage.write_batch` is a
real local transaction with backups and rollback. There is no schema version on
any CSV, no migration path, and no locking around read-modify-write.

### Recommendation pipeline

Candidate generation, scoring, and explanation are fused in one pandas pipeline.
When `ANIREC_MODEL_BUNDLE` points at a verified ONNX bundle, full generation,
“more,” single-step generation and heuristic fallback share the bundle's frozen
model-aligned catalogue; the MAL ranking endpoint is not called. The exact rows
are persisted as `candidate_catalogue.csv` with source
`installed-model-catalogue`. A configuration with no usable installed catalogue
still uses the previous MAL ranking source for compatibility, but persists and
reports it as `mal-ranking-legacy` rather than treating it as owned data. “More”
uses the persisted candidate snapshot from the generation that created the feed;
installing a new bundle does not hot-swap an existing feed's population.

Immediately before scoring, `FinalEligibilityPolicy` now applies one versioned
boundary to the primary and fallback pools. It enforces known-item exclusions,
model coverage, release/status/rating/media rules and bundle prerequisites, then
records aggregate exclusion reasons. Engines then return their ordered,
eligible pool, and `RecommendationService.recommend` applies the shared
deterministic selector in `AniRec/scoring/selection.py` exactly once, for the
heuristic, ONNX and fallback paths alike. The legacy CSV entry point
`rank_recommendations` uses the same selector. After selection the service
explains the served rows with the answering engine's own method
(`AniRec/scoring/explanation.py`, D-012): exact score parts for the heuristic,
counterfactual history removal for the sequence model. The engine's rank
before selection is persisted as personal fit.

Measured behaviour of both engines is recorded in
`docs/RECOMMENDER_EVALUATION.md`. Read it before changing ranking.

---

## What Web-First Requires

### Identity and accounts

AniRec owns its accounts. MyAnimeList is one importer among several planned
(AniList next). This is a decision, not an aspiration; see `docs/DECISIONS.md`.

Consequences that are not yet built:

* Server-side account identity, derived from an authenticated session, never from
  a request field.
* Per-request scope replacing ambient process state. Every service currently
  holding mutable per-request state on a process singleton is a blocker.
* A credential store for per-user third-party tokens, with the ToS question in
  `docs/PROJECT_DEFINITION.md` resolved before it holds real tokens.

### Catalogue

AniRec owns a catalogue rather than fetching one per user, per run. The source is
the existing collector snapshot: 30,540 titles with complete synopsis and image
coverage, community score, rank, and a relation graph.

The installed serving bundle now removes per-user MyAnimeList catalogue traffic
for configured model deployments. Making the collector catalogue independent of
the model bundle, replacing MAL IDs as internal identity, and measuring the new
candidate population with retained evidence remain roadmap work.

Item identity must be internal, with MyAnimeList as one external mapping among
several. Using MAL IDs as the primary key is a dependency that cannot be removed
later without a migration.

### Recommender staging

Candidate generation, scoring, and explanation become three stages with a
contract between them, so the engine can be replaced without touching the other
two. The engine choice is deliberately open; see `docs/DECISIONS.md`.

The scoring input is a generic interaction list rather than a MyAnimeList list.
This is the single concession made to the third-priority partner API.

### API contract

The API is a real contract from the start, because mobile and partner clients
both need one: versioned routes, pagination, no duplicated `*_text` fields
alongside raw values, compression, and auth tokens rather than an implicit local
session.

### Concurrency

Every element of the current design assumes one user in one process: a frozen
container built once, mutable per-request state on shared services, one unbounded
thread per operation, and a single-instance lock that forbids a second process on
the same data root. Multi-user is a rebuild of the composition root, the identity
model, the operation registry, and the storage layer. The service layer itself is
reusable.
