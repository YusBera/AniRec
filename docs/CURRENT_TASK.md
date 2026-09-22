# Current Task

## Status: PAUSED by the user

Do not start implementation until the user resumes this task. React UI
refinement is happening in another session; avoid `frontend/src/` unless an API
contract change requires explicit coordination.

## Task: deterministic, diverse feed selection

Replace uniform random sampling from a ranked pool with one shared,
deterministic selection policy for the heuristic and ONNX engines.

**Owner:** `AniRec/scoring/` and `AniRec/recommendation_system.py`.

**Decision:** `DECISIONS.md` D-007.

### Acceptance

- The same candidates, scores, settings, and account state produce the same feed.
- Strongly ranked titles are not silently discarded by random sampling.
- The first screen avoids unnecessary repetition using verified catalogue
  metadata; franchise rules use relation evidence only when it exists.
- The existing adventurousness control changes breadth in a defined way.
- Heuristic, ONNX, and fallback paths use the same selection policy.
- Tests cover reproducibility, ranking preservation, diversity, missing
  metadata, and both engines.

### Boundaries

- Do not retrain or select a winning ranking engine.
- Do not request a new collector snapshot for this task.
- Do not change the match figure; that is the next task.
- Use one specialized adversarial review after focused and broader tests. Ask
  for another review only if it finds a blocking defect.

## Next tasks

1. Make the displayed personal-match claim honest (`DECISIONS.md` D-008).
2. Audit existing activity logging against the selection result and close
   attribution gaps.
3. Before any retraining, ask the user to pull the latest verified snapshot.

See `NEXT_GOALS.md` for outcomes, evidence requirements, estimates, and the
later training gate. That roadmap does not authorize starting a paused task.
