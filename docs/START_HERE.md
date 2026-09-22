# Start Here

This is the shortest reliable orientation for a new AniRec agent. Read this,
`CURRENT_TASK.md`, and `DOMAIN_RULES.md` before opening implementation files.
Use `CODEMAP.md` to find the owner of a behavior. Open longer references only
when the task needs them.

## Project in one minute

AniRec is a web-first anime recommender. It imports a person's anime history,
ranks unseen titles, and shows evidence for each recommendation. The React web
client is the product. The PySide application remains a development tool.

The active checkout is the nested `AniRecTrainer/work/anirec-ui` repository. It
contains the current AniRec backend and frontend. The parent `AniRecTrainer`
repository owns training and evaluation. `AniRecDataCollector` owns collection
and catalogue snapshots. Do not edit either from this checkout unless the user
explicitly asks.

## What exists now

- FastAPI serves the local React workspace on a loopback-only boundary.
- Profiles, results, settings, and activity are stored locally.
- Candidate generation uses the installed model catalogue when available and
  records the exact population and source. A clearly labelled MAL ranking path
  remains only for configurations without a usable installed catalogue.
- One final eligibility policy protects heuristic, ONNX, and fallback ranking.
- Heuristic and ONNX ranking both work behind a shared engine contract.
- Recommendation activity logging exists, is opt-in, local, and bounded.
- There is no multi-user web account system yet.

## Work order

1. Read `CURRENT_TASK.md`. Its status decides whether work may start.
2. Read the cited decision or feature reference, if any.
3. Use `CODEMAP.md` to locate the owning code and tests.
4. Read only those files. Do not begin with historical handoffs.
5. Update `TASK_HISTORY.md` when a task is completed.

Goal 1 (deterministic, diverse feed selection) is complete; no next
implementation task has been started. React interface refinement continues in
another session. Backend work must avoid `frontend/src/` unless a contract
change makes coordination necessary.

## Non-negotiable product rules

- Missing values stay unavailable; zero is not a substitute.
- Never recommend an already-known, blocked, unreleased, restricted, or
  prerequisite-dependent title that the reader cannot safely start.
- A reason must come from the engine that produced the ranking.
- An uncalibrated score is not a percentage.
- The same eligibility and selection rules apply to primary and fallback paths.
- Do not scrape MyAnimeList or expose credentials.

`DOMAIN_RULES.md` contains the full wording.

## Open references only when needed

| Need | Read |
| --- | --- |
| Implemented and target architecture | `ARCHITECTURE.md` |
| Accepted product and engineering decisions | `DECISIONS.md` |
| File, route, service, and persisted-data ownership | `CODEMAP.md` |
| MAL fields and unknown-value meanings | `MAL_DATA_SEMANTICS.md` |
| ONNX bundle and fallback behavior | `ONNX_MODEL_SERVING.md` |
| Activity event meanings and privacy boundary | `RECOMMENDATION_ACTIVITY.md` |
| Measured ranker evidence and limits | `design/RECOMMENDER_EVALUATION.md` |
| Completed work and verification | `TASK_HISTORY.md` |
| Ordered next goals and estimates | `NEXT_GOALS.md` |
| Current local integration and launch notes | `UI_ENGINE_INTEGRATION.md` |

Files under `docs/design/` other than `RECOMMENDER_EVALUATION.md` are design
records or older handoffs. They can explain why something looks as it does, but
they do not override `CURRENT_TASK.md`, `DOMAIN_RULES.md`, or `DECISIONS.md`.
The risk-based sub-agent review cadence is defined once in `AGENTS.md`.
