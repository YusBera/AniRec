# Task History

Completed tasks, newest first. Not imported by `AGENTS.md`; read it only when the
history of a previous task is relevant.

Each entry records what changed, how it was verified, and what was left open.

---

## 2026-09-24 - Workspace reorganised; this repository moved

- **Moved.** The application moved from `AniRecTrainer/work/anirec-ui` to
  `projects/AniRec` and now has its own `.venv`.
- **Old checkout archived.** The older checkout that sat at `projects/AniRec`
  was zipped, with its `.git`, to
  `projects/_archive/AniRec-old-checkout-2026-09-24.zip`, then removed. Before
  that, every branch in it was confirmed present here, and its uncommitted
  edits were confirmed either preserved in `b1b3007` or superseded (the live
  MAL candidate overlay replaced by installed-catalogue candidates and D-010).
- **Design records archived.** `docs/design/` became `docs/archive/` with an
  index. `RECOMMENDER_EVALUATION.md` moved to `docs/`.
  `UI_ENGINE_INTEGRATION.md` was split into `UI_CONTRACT.md` and an archived
  20 September integration record. The launch steps are now in
  `START_HERE.md`.
- **Generated files untracked.** `.impeccable/`, `output/` and `reports/`
  were removed from git but kept on disk. Only the nine files cited by
  `DESIGN.md` or used as Impeccable's checkpoint remain tracked.
- **Specs stay at the root.** The PyInstaller specs resolve paths from their
  own location, so moving them would need an unverified packaging change.

*Verification:* `git fsck` clean after the move; see the completion report
for tests.

---

## 2026-09-24 - Goal 4 model decision

Chronological evaluation on the 22 September snapshot, under rules fixed
before any SASRec result existed.
- **Verdict:** the reference `sasrec-typed-d256` config stays, and patience 6
  is not adopted.
- **Figures and limits:** in `RECOMMENDER_EVALUATION.md`.
- **Full record:** in `AniRecTrainer/reports/GOAL4_DECISION_RECORD_24SEP.md`.
- **Nothing in this repository changed.**

---

## 2026-09-23 - Local API request fields cannot choose another profile

Feedback and operation requests now derive their profile from the server-side
active local profile and reject a supplied ID or MAL username that disagrees.
The API binds that captured profile and its MAL credentials through queued
sync/generate work, even if the machine-wide active profile changes later.
Public `profile-lookup.target` remains a separate comparison target. No account,
session, schema or ranking behavior changed. D-014 now records the accepted
hosted database direction and the unresolved local-mode choice.

*Verification:* eight new API regression cases failed before the route fix;
59 focused API/service/pipeline tests passed after binding the operation's
profile and credentials, including real sync/full/more runs after an active
profile switch. A reviewer identified the queued-operation identity split that
the route-only fix would have left open.

*Left open:* local loopback still has a machine-wide active profile, and
account/session/migration work waits for the local-mode choice. Stale
whole-state `save()` calls remain a separate data-loss risk.
The pre-existing `list-sync` handler omits the sync service's required
`synced_at` argument and needs a separate repair.

---

## 2026-09-23 - Cross-process recommendation state writes and account-scope inventory

`RecommendationStateService` now serializes each profile's read, mutation and
atomic write across processes through a persistent `.lock` sidecar. Busy or
unavailable locks fail closed. The JSON state schema and field-setter behavior
are unchanged. `ACCOUNT_SCOPE_INVENTORY.md` maps where the current local profile
is chosen; D-014 proposes isolation options for a user decision, with no login
or account implementation.

*Verification:* a real two-process write test failed against the previous code;
after the change, 22 targeted service tests and 56 state/activity/workspace
tests pass, including lock timeout and corrupt-file cases. A final persistence
review identified and resolved a
contention-fixture weakness.

*Left open:* `save()` is an explicit whole-state replacement and can overwrite
a newer field-setter change if called with an old snapshot; production actions
use field setters. Existing local profile IDs are not AniRec account IDs. The
user must choose D-014 before account migration or hosted access.

---

## 2026-09-23 - Recommendation import cycle removed

Deferred the heuristic engine's import of `rank_candidate_pool` until ranking
is invoked. `AniRec.recommendation_system` can now import first in a fresh
Python process; the engine's ranking logic and public exports are unchanged.

*Verification:* the clean import failed with a circular import before the
change and passed afterward. Standalone test files passed independently:
`test_feed_selection.py` 35, `test_recommendation_explanation.py` 32, and
`test_explainable_recommendations.py` 5.

*Left open:* none for this import boundary.

---

## 2026-09-23 - PySide detail uses honest personal fit

The deprecated detail dialog now visibly shows the engine rank from the view
model, or “Personal match unavailable” when there is no rank. Its retired
percentage readout, score rail, and sum are hidden. No response or persisted
format changed.

*Verification:* the new rank and unavailable-state checks failed before the
fix; 12 focused service/dialog tests passed afterward, including an offscreen
visible-dialog assertion that no percentage text is shown.

*Left open:* this is a maintenance fix for the deprecated PySide tool; React UI
work remains with its separate owner.

---

## 2026-09-23 - Recommendation state write safety

Serialized read, change, and atomic write per profile across state-service
instances. A write now refuses to replace a present state file that cannot be
parsed or read; ordinary reads still expose their prior safe fallback. The JSON
schema and older-file loading remain unchanged.

*Verification:* the new concurrent-write and corrupt-file tests failed against
the previous behavior, then 20 focused state/service tests and 47 related
state, activity, and workspace tests passed. A read-only backend review gave GO
after the race fixture and unreadable-file coverage were corrected.

*Left open:* this is process-local thread serialization; a second application
process would need an interprocess lock. Public `save()` remains an explicit
whole-state replacement for callers holding a valid snapshot; production routes
use the serialized setters.

---

## 2026-09-22 - Likes and dislikes collected, not fed (D-013)

Revived explicit like/dislike collection for later use, at the user's
request, without letting votes influence anything yet.

- `RecommendationFeedback` gains optional `recorded_at` and attribution:
  `ranking_id`, `model_rank`, `feed_rank`, `model_version`,
  `catalog_version`, `selection_policy` and `adventurousness`. The fields are
  stored in `recommendation_state.json`, and older schema 3 files still load.
- `POST /api/discover/feedback` (sentiment) derives attribution, genres and
  title server-side from the served row of the active profile's own feed. A
  vote for a title outside the feed is still kept, unattributed.
- Votes feed nothing. The web API passes no taste adjustments, and the
  desktop client no longer re-sorts its displayed feed by votes (it used
  `TasteFeedbackService.personalize`, which also rewrote ranks).
- The UI contract is in `UI_CONTRACT.md`; the web client has no
  vote buttons yet.

*Verification:*
- `tests/test_recommendation_events.py`:
  - a vote stored with its time and server-side attribution, ignoring
    client-claimed genres and title;
  - a dislike stored;
  - an out-of-feed vote kept unattributed;
  - clearing a vote;
  - legacy vote files loading.
- `tests/test_recommendation_explanation.py`: web generate and "more" produce
  identical rows, ranks, scores and explanations with and without votes.

---

## 2026-09-22 - Activity attribution (Goal 3)

Made every activity event attributable to exactly what was shown and why.

- **Schema 2 columns:** `ranking_id`, `feed_rank`, `selection_policy` and
  `adventurousness` are added to `recommendation_events.sqlite`. Existing
  stores are migrated in place with `ALTER TABLE`; old rows keep
  `schema_version` 1 and NULL attribution.
- **Correct rank:** `model_rank` now records the engine's rank before
  selection. It used to record the feed position.
- **Server-side attribution:** the API derives every attribution field from
  the served row. A client-supplied `model_rank` is ignored.
- **Per-row selection provenance:** each `Recommendation` records the
  selection policy version and adventurousness in force when it was selected.
  The pipeline stamps them for full, "more" and single-step generation.
- **Feed fingerprint:** covers MAL ID, feed rank, model rank, ranking ID and
  selection settings. It no longer hashes the retired percentage.
- **Native path:** the PySide recording call passes the same fields.
- **Hidden titles:** full, "more" and single-step generation read the
  profile's saved hidden titles (`RecommendationStateService`) whenever a
  caller passes none. Before, the CLI single-step served hidden titles.
  `run_step` also accepts feedback adjustments, and the PySide worker passes
  hidden titles explicitly.
- **Catalogue attribution:** each event records `catalog_version`. Every
  ranking snapshot is archived immutably as
  `ranking_snapshots/<ranking_id>.csv`, pruned after 90 days with events, and
  resolved by `PipelineOrchestrator.ranking_snapshot`, so an event's ranking
  stays recoverable after later generations.

*Verification:*
- `tests/test_recommendation_events.py`:
  - API events attributed to engine rank, feed position, ranking and
    selection, ignoring a client-supplied rank;
  - in-place migration of a version 1 store;
  - invalid attribution values rejected;
  - fingerprint tracking ranking and selection, not the percentage.
- `tests/test_recommendation_explanation.py`: per-row selection provenance
  across "more" with a different adventurousness, and single-step honouring
  hidden titles with "more" continuing from it.
- `tests/test_advanced_operations_page.py`: the PySide single-step passes the
  profile's hidden titles.
- Saved hidden titles are honoured by CLI-shaped calls that pass none, and an
  older feed's ranking resolves after regeneration.
- An archive referenced by an event outlives the 90-day pruning window.
- Adversarial review, first pass: NO-GO. The catalogue was not recoverable
  per event, and the CLI single-step served hidden titles. Both fixed with
  regression tests, plus a self-found archive-retention gap. Second pass:
  **GO**. The desktop worker now passes "no hidden set" as None, so the
  pipeline reads saved state rather than ranking with an empty set.

*Left open:*
- The heuristic's `live-unversioned` catalogue is identified by the archived
  input digest but cannot be rebuilt, because the live MAL list is not
  retained. This matters for Goal 4.
- A pruning pass and a concurrent event can race within about a millisecond.
- Archives hold hidden-title IDs and outlive "clear activity" for up to 90
  days (local, non-textual).
- Version 1 event rows hold the feed position in `model_rank`; filter on
  `schema_version`.
- Existing activity tests (opt-in, deduplication, retention, privacy
  allowlist, stale feed and profile rejection, failure path, native
  visibility) still pass.
- Backend set: 271 passed. Frontend CI passed.

---

## 2026-09-22 - Honest personal fit and "why this pick" (Goal 2)

Retired the uncalibrated "personal match" percentage (D-008). Added personal
fit as the ranking engine's own rank, and an explanation built from the engine
that ranked each served row (D-012).

- **Rank:** engines record each title's rank before selection and the number
  of candidates ranked (`Model Rank`, `Ranked Candidate Count`). They are
  persisted on `Recommendation` and exposed as `fit_rank`, `fit_pool_size` and
  `fit_top_percent`.
- **Heuristic "why":** the raw score parts. They sum to the ranking score to
  within one float rounding step. Taste parts carry the reader's genuine rated
  titles (never the imputed file), their average, the affinity used, and any
  feedback adjustment. Community rating and similar viewers are separate
  parts, flagged when a neutral stand-in was used.
- **Sequence-model "why":** counterfactual removal. The model is rerun at
  batch size 1 without each genre group of the input-window history and
  without each single title. The pick's score drop and rank are measured among
  the exact candidates `rank()` ordered. It is deterministic and never
  presented as shares. A failure yields `unavailable`, never a lost feed.
  Sampled Shapley was measured first and rejected (see D-012).
- **One ranking across "more":** each generated feed writes a ranking snapshot
  (`ranking_signals.csv`): similar-viewer scores, franchise and hidden
  exclusions, eligibility date, a digest of the ranking input files and
  feedback, and the answering engine. "More" continues exactly that ranking.
  Shown titles and titles hidden since stay ranked and are skipped only at
  selection. Before this, "more" and single-step dropped the similar-viewer
  signal and franchise exclusion. If a sync, feedback change, eligibility
  filter change (NSFW, minimum MAL score), rebuilt input, or different engine
  or bundle catalogue changed the ranking inputs, "more" refuses with
  "Generate a new feed" rather than mixing rankings. Each recommendation
  carries the `ranking_id` of its snapshot, so an older feed next to a newer
  snapshot is refused too. Behaviour change for the deprecated PySide client:
  its feedback-aware "more" passes current votes, so voting and then asking
  for more now asks for a new feed.
- **Feedback scope:** genre feedback moves only `genre:` features. MAL reuses
  names across genre, source and media type.
- **Web results are saved:** the API's sync, generate and "more" operations
  now save their result as the desktop does (`ResultService.save_merged`).
  Before this, the web client reloaded an unchanged saved feed after
  "Recommend 5 more", so new titles were computed and never shown
  (pre-existing). The three feed-writing operations are mutually exclusive
  per profile (`OperationRegistry.start(exclusive_with=...)`, checked under
  one lock), so a concurrent generate and "more" cannot overwrite each other.
- **Web boundary:** the API sends no percentage or percentage-point breakdown.
  The UI contract is in `UI_CONTRACT.md`, and the generated API
  types are regenerated.

*Verification:*
- `tests/test_recommendation_explanation.py`, through the pipeline, the
  service, persistence, the view model and the strict API model, covers:
  - heuristic exactness and evidence honesty across full, "more" and
    single-step;
  - community stand-in flags and feedback attribution;
  - fit rank before selection;
  - ONNX removal effects checked exactly against an additive fake model and a
    brute-force re-sort, including exact score ties;
  - determinism and the failure path;
  - fallback explanations;
  - persistence and the strict contract, including legacy results;
  - a "more" batch ranking one population with the same signals;
  - restore-then-more and hide-then-more keeping one ranking;
  - "more" refusing after a sync, a feedback change, an eligibility-filter
    change, an engine change, or on a feed that is not the snapshot's;
  - single-step starting a ranking that "more" can continue;
  - genre votes never moving same-named source or type features;
  - web generate and "more" operations saved and shown, through the real
    API handlers;
  - feed-writing operations refused while another runs for the same profile,
    at the registry and through the HTTP route.
- Real bundle, the user's 200-title window: ranking plus explanations took
  about 3.9 s. Output was byte-identical across two processes with different
  hash seeds. `full_score` and `full_rank` equal the ranking exactly.
- Backend set: 240 passed. Frontend CI (type verification, typecheck, 61
  tests): passed.
- Adversarial review, first pass: NO-GO with three blockers: "more" ranked a
  smaller population and produced duplicate ranks; genre votes leaked into
  same-named source and type features; rejected-method wording remained. All
  are fixed with regression tests. Second pass: NO-GO. "More" still split
  the ranking after restoring a hidden title or after a MAL sync. This is now
  fixed by the ranking snapshot. A self-found divergence gap was closed with
  `ranking_id`. Third pass: NO-GO. Changed NSFW or minimum-score filters
  still split the ranking. They are now part of the snapshot and refused.
  Fourth pass: NO-GO on the same two filters, now in the snapshot. Fifth
  pass: **GO**. Its lost-update race between concurrent generate and "more"
  was then closed with per-profile exclusivity.

*Left open:*
- The deprecated PySide client still renders its legacy percentage in the
  detail dialog. Its feedback-aware "more" now asks for a new feed after any
  vote.
- An operation request naming `profile_id` without `username` takes the
  active profile's username (pre-existing identity handling). The React
  client sends neither field.
- Heuristic and sequence-model pool sizes differ, so `fit_top_percent` is not
  comparable across engines.
- Removal effects cover only the model's input window.
- A removal that empties the window measures the new-reader rank.
- `Recommendation` is no longer hashable because it holds a dict.
- The Shapley rejection figures come from an unretained session experiment.

---

## 2026-09-22 - Feedback on never-rated genres reaches their titles

Fixed a pre-existing heuristic scoring defect in
`AniRec/recommendation_system.py::_apply_adjustments`. Explicit feedback on a
genre the reader had never rated created a profile feature under the
casefolded label (`genre:horror`), but candidate tokens keep the catalogue's
spelling (`genre:Horror`). The like therefore matched no title. It only
enlarged the profile norm, lowering every other title's cosine. New features now
take the catalogue's spelling (falling back to the vote's own spelling), chosen
deterministically; matching stays case-insensitive.

This changes ranking output for readers who voted on a never-rated genre. With
an Action-only profile, liking Horror now moves a Horror title from 0.139286 to
0.813030 (from second place to first). The Action title's move to 0.543532 is
unchanged by the fix; it is the documented cosine normalisation from the
profile gaining a feature.

*Verification:*
- Regression test
  `tests/test_explainable_recommendations.py::test_liking_a_never_rated_genre_raises_titles_that_carry_it`
  runs through `RecommendationService.recommend`. It failed before the fix
  (`0.139286 > 0.139286`) and passes after. It also checks that the vote's
  spelling does not matter, and that the explanation shows a positive Horror
  taste part carrying the feedback adjustment.
- Focused suite (services, feed selection, recommendation explanation,
  explainable recommendations, scoring invariants, collaborative graph):
  91 passed. Taste-feedback, pipeline, engine-contract and legacy
  recommendation-system tests: 33 passed.

*Left open:* no retained evaluation of the ranking change. The deprecated
PySide `TasteFeedbackService.personalize` still adjusts the display percentage
after scoring; it is not on the web path.

---

## 2026-09-22 - Deterministic, diverse feed selection (Goal 1)

Replaced both uniform random samplers with one deterministic selector,
`AniRec/scoring/selection.py::select_feed`. The heuristic sampler was in
`rank_recommendations`; the ONNX sampler was in `OnnxSequenceRankingEngine.rank`.
`rank_candidate_pool` now returns the heuristic's ordered pool, and the ONNX
engine returns its ordered eligible pool. `RecommendationService.recommend`
applies the selector exactly once, after final eligibility and ranking, whichever
engine answered. Full generation, "more" and single-step generation all route
through it. The legacy CSV entry point `rank_recommendations` uses the same
selector. `random_int`, `random_seed` and `seed` are still accepted for
compatibility but no longer affect output. The CLI prompt and the deprecated
PySide label now read "Adventurousness". Recorded as D-011.

Rule: the top title is always served. Adventurousness `a` (stored
`randomness_factor`, 1-10) allows a leap of `2 * (a - 1)` positions within the
top `count + 2 * (a - 1)`. Rows are chosen greedily by
`-position - leap * redundancy`, with ties kept in rank order. Redundancy is the
highest similarity to an already chosen title: a weighted Jaccard over genres
(0.5), studios (0.2), source (0.15) and media type (0.15). It is computed only
over facets both rows carry and renormalised over those facets. A pair with no
comparable facet counts as fully redundant, so it earns no novelty. Labels use
the production `parse_genres` path plus case and whitespace normalisation;
`unknown`/NaN/`pd.NA` count as missing. Selected rows keep their original
order and values.

*Verification:*
- `tests/test_feed_selection.py` (new, 41 cases, through `RecommendationService`
  with the real heuristic and ONNX engines) covers:
  - determinism across seeds, repeated calls, reversed input order and three
    `PYTHONHASHSEED` subprocesses;
  - top-title retention at every level, exact rank order at `a = 1`, and bounded
    variety at `a = 10`;
  - the window bound, and same-genre titles not treated as duplicates;
  - per-facet lifts for studios, source and media type;
  - bare and mixed-metadata pools, CSV-encoded and malformed labels, and
    case/whitespace variants;
  - pools smaller than the request, and exact-score ties;
  - one selector call for the heuristic, ONNX and fallback paths;
  - eligibility exclusions held at `a = 10`;
  - unchanged heuristic contributions, and ONNX scores, availability and
    original candidate ranks.
- `tests/test_pipeline.py::test_full_more_and_single_step_share_one_deterministic_selection`
  runs full generation, single-step (after the CSV round trip) and repeated
  "more" through production service construction, with one selector call each.
- Updated `test_seed_has_no_effect_on_the_deterministic_feed` and the ONNX engine
  pool assertion.
- On the pre-change code, eight identical-input runs gave eight different feeds
  and five dropped the top title. The pipeline test and the mixed-pool test fail
  on the old behavior.
- Focused suite (10 files): 120 passed.
- Full `tests/`: 807 passed, 3 failed, none in the selection path. Two
  `test_security_audit` cases scan `frontend/node_modules`. The PySide
  `test_native_visible_impressions_and_saved_actions` passes when run alone and
  with its file.
- The specialized adversarial reviewer gave NO-GO on its first pass: a missing
  facet counted as zero similarity, so undescribed rows were promoted as novel.
  After the fix, a narrow re-review gave GO. It checked real-bundle determinism
  across processes and a 12-user promotion audit.
- After the commits (`b1b3007` earlier work, `4671326` Goal 1), a fresh,
  independent reviewer gave GO with no blockers. It checked:
  - clean exports of both commits: 84 and 120 focused tests passed;
  - that restoring the old random sampler makes 20 tests fail;
  - a 20,000-pool fuzz of the selection invariants;
  - real-catalogue determinism across hash seeds;
  - a 15-user real ONNX check.

*Left open:*
- No franchise diversity: serving rows carry no verified franchise identifier.
- A partly described title is compared only over the facets it shares, so one
  verified differing fact can count as full novelty.
- Selection works on rank position, not score size.
- "More" does not consider titles already on screen.
- On real data, `a = 10` changes about 1-2 of 10 slots; no evaluation shows the
  feed is better.
- `SELECTION_POLICY_VERSION` and the adventurousness value are not persisted,
  and activity `model_rank` records feed position. Both are recorded under
  Goal 3.
- Determinism assumes unique MAL IDs. For duplicate IDs with different data,
  final eligibility keeps the first row, so input order decides the copy
  served. This is pre-existing and happens before selection.
- A fractional stored `randomness_factor` (hand-edited settings only) is
  truncated to an integer.
- Single-step generation (`run_step`) does not pass hidden titles or feedback
  adjustments to ranking. This is pre-existing and not caused by selection.
- Some sibling-import test files fail collection when run alone
  (pre-existing).

---

## 2026-09-22 - Agent documentation entry point

Reduced the required startup context to `START_HERE.md`, `CURRENT_TASK.md`, and
`DOMAIN_RULES.md`. Replaced the stale documentation index, made the completed
catalogue slice historical, recorded the paused deterministic-selection task,
and added `NEXT_GOALS.md` for outcomes, estimates, review cadence, and the
snapshot gate. Marked desktop-era handoffs as optional evidence and corrected
stale statements about prerequisite enforcement, web authority, and MAL
semantics.

Added a risk-based reviewer cadence: routine documentation and small internal
changes use no sub-agent; ranking and contract changes receive one final review;
only training, migration, authentication, security, or release work receives an
early and final review.

*Verification:* link and stale-phrase checks, diff check, and a fresh-agent
read-through of the new mandatory entry path.

*Left open:* historical release and design records intentionally remain in place
for evidence. They are indexed as optional rather than rewritten.

---

## 2026-09-22 - Installed catalogue routing

Routed full generation, “more”, single-step generation, and heuristic fallback
through the installed model-aligned catalogue when available. Persisted the
exact population in `candidate_catalogue.csv` with its source, kept the legacy
MAL ranking path clearly labelled for configurations without a usable provider,
and made an installed provider that returns no rows fail closed.

Separated the complete persisted catalogue count from the filtered candidate
snapshot count and kept both stable across full, “more”, and single-step flows.

*Verification:* 14 focused pipeline tests and 159 broader backend, workspace,
and native tests passed; Python byte-compilation and diff checks passed. The
specialized backend reviewer gave a final GO after checking provenance across
all generation paths.

*Left open:* the broader franchise graph is not part of the installed candidate
rows. Only verified direct prerequisite evidence is available to the current
eligibility policy.

---

## 2026-09-22 - Single-IDF heuristic content cosine

Corrected the heuristic content score to use an IDF-weighted user vector and a
binary candidate feature vector. The old implementation multiplied the
already-IDF-weighted user component by IDF again on the candidate side. Added a
numeric regression that fails under the old formula while preserving exact
explanation reconciliation and score bounds.

Documented the verified local MyAnimeList mapping path and separated it from
upstream meanings that could not be independently retrieved in the current
environment. Direct tests cover mapped scoring fields, the release-year
fallback and the absence of MAL rank/popularity from the requested field set.
Historical heuristic results were rewritten as nonreproducible observations;
they no longer claim the IDF defect caused a quality change.

*Verification:* 53 focused mapping/scoring tests and 116 broader
recommendation/backend tests; Python byte-compilation; diff check. The
specialized adversarial backend reviewer gave a final GO after the evidence and
external-semantics claims were corrected.

*Left open:* recommendation quality and metadata-completeness sensitivity need a
retained evaluator run before the owned catalogue rollout can claim improvement.
The supplied MAL reference findings are recorded in `MAL_DATA_SEMANTICS.md`;
fields beyond that boundary still require official-reference verification.

---

## 2026-09-21 - Shared final eligibility policy

Routed full generation, “more”, single-step generation and model fallback
through one versioned eligibility boundary before scoring. It rechecks history
and explicit exclusions, scorer coverage, release and airing state, rating,
media type and the installed bundle's direct prerequisites. Candidate overlays
cannot weaken verified catalogue restrictions. Bundle policy remains available
when ONNX Runtime cannot start, and each result owns its aggregate policy audit
and catalogue provenance.

*Verification:* 27 focused eligibility, pipeline and ONNX tests; 97 broader
recommendation/backend tests; Python byte-compilation; diff check; frontend API
contract, TypeScript and 61 frontend tests. A specialized adversarial backend
reviewer gave a final GO after the result-provenance race was fixed and covered
at the former interleaving point.

*Left open:* the current bundle's prerequisite export is limited to its verified
direct relation map. A heuristic-only configuration has no independent owned
catalogue relation context. Recap and full-story coverage must be demonstrated
from retained relation evidence before claiming the broader franchise rule is
complete.

---

## 2026-09-20 - Web-first direction and documentation set

Established the platform ordering (web, then mobile, then a third-party
recommendation API) and wrote the agent documentation set: `AGENTS.md`,
`docs/PROJECT_DEFINITION.md`, `docs/ARCHITECTURE.md`, `docs/DOMAIN_RULES.md`,
`docs/DECISIONS.md`, `docs/CURRENT_TASK.md`, `docs/CODEMAP.md`, and this file.

Superseded the prior desktop-first framing in `PRODUCT.md`, `DESIGN.md`, and the
handoff documents under `docs/archive/`.

*Verification:* documentation only. No code changed.

*Left open:* decisions D-008 (match figure) and the engine selection behind
D-006. No implementation task opened.

---

## 2026-09-20 - Recommender evaluation

Measured every ranking engine on one split through the training harness,
including the heuristic engine, which had never been evaluated. Recorded in
`docs/RECOMMENDER_EVALUATION.md`.

*Verification:* the vectorised heuristic was proved equal to the shipped scoring
functions to within 8.3e-17 before being run.

*Left open:* the tie-block ablation that would confirm or undermine the sequence
model's margin. Evaluation scripts are not yet landed in a repository.
