# AniRec documentation

New agents start with [START_HERE.md](START_HERE.md), then read
[CURRENT_TASK.md](CURRENT_TASK.md) and [DOMAIN_RULES.md](DOMAIN_RULES.md).
Do not begin with a handoff document.

## Core documents

| Document | Purpose |
| --- | --- |
| [START_HERE.md](START_HERE.md) | Short project orientation and conditional reading order |
| [CURRENT_TASK.md](CURRENT_TASK.md) | The only active or paused implementation scope |
| [NEXT_GOALS.md](NEXT_GOALS.md) | Ordered backend roadmap, outcomes, estimates, and gates |
| [DOMAIN_RULES.md](DOMAIN_RULES.md) | Product invariants that implementation must preserve |
| [CODEMAP.md](CODEMAP.md) | Routes from a concern to its owning code and tests |
| [ARCHITECTURE.md](ARCHITECTURE.md) | Implemented state separated from target state |
| [DECISIONS.md](DECISIONS.md) | Durable decisions and their reasons |
| [TASK_HISTORY.md](TASK_HISTORY.md) | Completed tasks, evidence, and remaining limits |
| [PROJECT_DEFINITION.md](PROJECT_DEFINITION.md) | Product, platform order, audience, and external constraints |

Only `START_HERE.md`, `CURRENT_TASK.md`, and `DOMAIN_RULES.md` are required at
the beginning of ordinary work. Open the rest when the current task points to
them.

## Feature references

| Document | Read it for |
| --- | --- |
| [MAL_DATA_SEMANTICS.md](MAL_DATA_SEMANTICS.md) | MAL field mapping, unknown values, and scoring use |
| [ONNX_MODEL_SERVING.md](ONNX_MODEL_SERVING.md) | Bundle verification, model catalogue, and fallback behavior |
| [RECOMMENDATION_ACTIVITY.md](RECOMMENDATION_ACTIVITY.md) | Activity events, privacy, retention, and attribution |
| [UI_ENGINE_INTEGRATION.md](UI_ENGINE_INTEGRATION.md) | This checkout, launch commands, and last integration evidence |
| [design/RECOMMENDER_EVALUATION.md](design/RECOMMENDER_EVALUATION.md) | Existing ranker measurements and what they do not prove |
| [CHANGELOG.md](CHANGELOG.md) | Released desktop-version history |

## UI and historical design records

The files under `design/` preserve earlier UI decisions, measurements, and
handoffs. Most were written during the desktop-to-web transition. They are
optional evidence, not current task instructions.

- Use `REACT_PRESERVATION_AUDIT.md` and the workspace specifications when a
  current UI decision needs historical evidence.
- Use `ICON_HANDOFF.md` only when changing the icon system.
- `LATEST_AGENT_HANDOFF.md`, `MIGRATION_HANDOFF.md`, `FRONTEND_HANDOFF.md`, and
  `BACKEND_HANDOFF.md` contain useful history but have superseded status or
  desktop-first assumptions. Never treat “latest” in a filename as authority.
- Git history is the archive. Do not create another session handoff when
  `CURRENT_TASK.md`, `TASK_HISTORY.md`, or a subject reference can hold the fact.

## Maintenance rule

Each fact has one owner. Link to that owner instead of restating it. Current
scope belongs in `CURRENT_TASK.md`; completed evidence belongs in
`TASK_HISTORY.md`; durable rationale belongs in `DECISIONS.md`; file locations
belong in `CODEMAP.md`.
