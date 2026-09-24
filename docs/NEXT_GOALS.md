# Next Goals

This is the working order after the completed eligibility, scoring-correction,
and installed-catalogue slices. `CURRENT_TASK.md` remains the authority for what
may be implemented now. Goals 1-3 are complete. Goal 4 waits for the user to
pull the latest verified collector snapshot.

React UI refinement is happening separately. Backend work should avoid
`frontend/src/` unless an API contract must change; in that case, document the
contract and give the UI agent a focused handoff.

## Completed foundation

- One final eligibility policy covers heuristic, ONNX, and fallback ranking.
- The heuristic content cosine applies feature rarity once rather than twice.
- An installed model catalogue supplies one recorded candidate population to
  full generation, “more”, and single-step generation.
- Missing MAL score, rank, and episode count remain unavailable rather than zero.
- Local recommendation activity collection already exists and is opt-in.
- Deterministic, diverse feed selection (Goal 1) is shared by every engine path.

## Goal 1 - Deterministic, diverse feed selection

**Status:** complete (2026-09-22). See `TASK_HISTORY.md`.

Replace random sampling from the ranked pool with one shared selection policy
for the heuristic and ONNX engines.

The selector should retain the strongest ranked choices, then use verified
metadata to avoid unnecessary repetition. Adventurousness controls how much
ranking strength may be traded for useful variety. Franchise behavior may use
relation evidence only when that evidence exists.

**After this goal:** the same inputs produce the same feed, strong results are
not lost by chance, and the first screen is intentionally varied.

**Evidence required:** focused tests for reproducibility, ranking preservation,
diversity, missing metadata, adventurousness, and both engines; one broader
backend run; one final adversarial reviewer after tests.

**Estimate:** 2-4 active hours. No retraining or new snapshot.

## Goal 2 - Honest personal-match presentation

**Status:** complete (2026-09-22). Personal fit is now a rank and each pick
carries an engine-specific explanation (D-008, D-012). See `TASK_HISTORY.md`.

Resolve `DECISIONS.md` D-008. The current model output is not a probability and
must not be presented as a trustworthy percentage.

Start with the cheapest honest contract: keep MAL community score separate and
represent personal fit as a rank, tier, or clearly named strength unless a
future evaluation calibrates it. Preserve exact heuristic contribution
reconciliation and keep unavailable model explanations unavailable.

**After this goal:** every displayed number has one clear meaning, ONNX output
does not pretend to be a calibrated percentage, and the UI agent receives an
exact response-field and empty-state handoff.

**Evidence required:** service and API contract tests, generated-type checks if
the response model changes, and frontend CI only when frontend or generated API
files change.

**Estimate:** 1-3 active hours. No retraining.

## Goal 3 - Close activity-attribution gaps

**Status:** complete (2026-09-22). See `TASK_HISTORY.md`.

Audit the existing impression and action logging against the new selector. Do
not rebuild logging that already exists.

Confirm that a presentation records the engine and catalogue versions, ordered
feed fingerprint, original rank, selected position, and the setting that shaped
selection. Known gap from the Goal 1 review: activity `model_rank` currently
records the feed position after selection, not the original model rank, and
neither the adventurousness value nor `SELECTION_POLICY_VERSION` is recorded.
Also check that single-step generation (`run_step`) honours hidden titles and
feedback; today it passes neither to ranking. Verify impression, detail-open, external-open, save, dismiss, and
restore meanings remain distinct and privacy-bounded.

**After this goal:** AniRec can connect what it showed with what the reader did,
so later model decisions can use real behavior rather than guesses.

**Evidence required:** attribution, retry/deduplication, opt-in, retention,
profile-isolation, and failure-path tests.

**Estimate:** 2-4 active hours. No retraining.

## Goal 4 - Chronological evaluation and model decision

**Status:** complete (2026-09-24). The reference config `sasrec-typed-d256`
stays, and patience 6 is not adopted; see `RECOMMENDER_EVALUATION.md`. That
config was retrained on data through August, exported, parity-checked and
inspected through AniRec. It is now the verified bundle in
`ONNX_MODEL_SERVING.md`. Still open: a confirmation window once the collector
has caught up. It can confirm or withdraw the decision, never re-select.

Before this goal starts, stop and ask the user to pull the latest verified
collector snapshot. Do not train against an older or assumed snapshot.

Validate the real meaning and missing-value behavior of every field used by the
catalogue or model. Build a global date cutoff so training cannot see future
events or future catalogue facts. Compare reproducible baselines, EASE, the
current transformer, and a blend only where the evidence supports it. Use
multiple seeds and retain configs, metrics, candidate populations, and reports.

Re-export the selected model to ONNX, verify PyTorch/ONNX agreement, and inspect
actual recommendations in AniRec before changing model size.

**After this goal:** AniRec has a defensible answer for which ranker to serve and
why, plus a repeatable evaluation that future daily data can rerun.

**Estimate:** data checking plus several training runs may take 1-3 days,
depending on snapshot size and hardware.

## Before a public launch

Recorded 2026-09-24. Not ordered goals yet; each needs scoping before work.

**Blocking**
1. **Accounts.** Sign-up, sessions and account-scoped storage (D-014). It
   waits on the local-mode choice.
2. **Easy import.**
   - Username-only import through a server-held MAL Client ID.
   - A request queue with automatic retry on HTTP 429, so a burst of imports
     waits in line instead of failing.
   - MAL XML export upload as a fallback that uses no API calls.
3. **First-run and regeneration flow.** Offer a clear "generate a feed" action.
   When a saved feed predates the current model, prompt for a new one instead
   of showing "Personal fit unavailable" on every card.
4. **Sparse-history state.** Below the evidence threshold, say the system does
   not know enough yet (`DOMAIN_RULES.md`, "Scoring Honesty").
5. **Hosting and security.**
   - A deployment with TLS and authentication on every route.
   - Per-user rate limits and secret management.
   - A security review before the API leaves loopback.
6. **Legal and data.**
   - Stay non-commercial under the MAL API agreement.
   - Resolve where the training data comes from (the collector reads MAL's
     website, not the API).
   - A privacy policy covering KVKK/GDPR, with consent at import, export and
     deletion.
   - Rules for how covers and synopses are shown.
7. **Feedback after watching (D-015).** Library-side reporting and
   observation on return; retire the card vote buttons.

**Needed, not blocking**
8. A 375px, keyboard and screen-reader pass across all five pages.
9. Operations: bundle deploy and rollback, backups, error monitoring,
   retention jobs.
10. Known debt: the intermittent API shutdown test, and stale whole-state
    `save()` calls.
11. **Design fidelity to the desktop client.** The user considers the web
    client to have lost the PySide design language and widget structure. A
    comparison against the released 1.3.0 is in progress; its findings decide
    what is restored.

## Decisions that wait for Goal 4 evidence

Do not schedule these merely because they sound useful:

- EASE and transformer blending
- content encoder and cold-start features
- per-user score normalization
- a larger `d=384` transformer
- broader relation-graph or franchise-classifier changes

Choose among them from observed failures, chronological metrics, and activity
data. A larger model is justified only if capacity, rather than data or serving
policy, is the demonstrated limit.

## Review cadence

- Goals 1-3: implement and test locally, then use one final specialist review.
- Re-review only a blocker found by that review.
- Goal 4: use one early evaluation-design review and one final evidence review.
- Routine docs, copy, and narrow internal fixes use no sub-agent.

