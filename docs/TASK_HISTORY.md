# Task History

Completed tasks, newest first. Not imported by `AGENTS.md`; read it only when the
history of a previous task is relevant.

Each entry records what changed, how it was verified, and what was left open.

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
handoff documents under `docs/design/`.

*Verification:* documentation only. No code changed.

*Left open:* decisions D-008 (match figure) and the engine selection behind
D-006. No implementation task opened.

---

## 2026-09-20 - Recommender evaluation

Measured every ranking engine on one split through the training harness,
including the heuristic engine, which had never been evaluated. Recorded in
`docs/design/RECOMMENDER_EVALUATION.md`.

*Verification:* the vectorised heuristic was proved equal to the shipped scoring
functions to within 8.3e-17 before being run.

*Left open:* the tie-block ablation that would confirm or undermine the sequence
model's margin. Evaluation scripts are not yet landed in a repository.
