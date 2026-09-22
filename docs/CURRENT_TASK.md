# Current Task

## Status: COMPLETE - no active implementation task

Goal 1, deterministic and diverse feed selection, was completed on
2026-09-22. The next task (Goal 2 in `NEXT_GOALS.md`) has **not** been
started and needs the user to open it. React UI refinement continues in
another session; avoid `frontend/src/` unless an API contract change requires
explicit coordination.

## Completed task: deterministic, diverse feed selection

Replaced uniform random sampling from a ranked pool with one shared,
deterministic selection policy for the heuristic, ONNX, and fallback paths.

**Owner:** `AniRec/scoring/selection.py`, called once in
`RecommendationService.recommend`.

**Decisions:** `DECISIONS.md` D-007, D-011.

### Final state

- No random source remains in feed selection. The same candidates, scores,
  settings and account state produce the same ordered feed across runs, seeds
  and Python processes.
- Engines return their ordered, final-eligible pool. The service selects once,
  whichever engine answered. Fallback is therefore never selected twice.
- The top-ranked title is always served. Adventurousness `a` allows a title to
  move at most `2 * (a - 1)` positions for variety, within the top
  `count + 2 * (a - 1)`. `a = 1` is exactly rank order.
- Redundancy uses genres, studios, source and media type, compared only over
  facets both rows carry. A pair with no comparable facet earns no novelty;
  partial metadata is compared over shared facets only.
- No franchise diversity is claimed. Serving rows carry no verified franchise
  identifier.
- Scores, match availability, contributions, reasons, engine and catalogue
  provenance, and the ONNX original candidate rank are unchanged by selection.
- No API, persisted format, or frontend contract changed.

See `TASK_HISTORY.md` for tests, the reviewer's result, and limits.

## Next tasks (not started)

1. Make the displayed personal-match claim honest (`DECISIONS.md` D-008).
2. Audit existing activity logging against the selection result and close
   attribution gaps.
3. Before any retraining, ask the user to pull the latest verified snapshot.

See `NEXT_GOALS.md` for outcomes, evidence requirements, estimates, and the
later training gate. That roadmap does not authorize starting a task.
