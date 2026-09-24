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
| [ACCOUNT_SCOPE_INVENTORY.md](ACCOUNT_SCOPE_INVENTORY.md) | Current identity and profile-scope entry points; proposed account isolation boundary |
| [UI_CONTRACT.md](UI_CONTRACT.md) | What the web client may show from the recommendation API, and what it must not |
| [RECOMMENDER_EVALUATION.md](RECOMMENDER_EVALUATION.md) | Ranker measurements, the Goal 4 model decision, and what they do not prove |
| [CHANGELOG.md](CHANGELOG.md) | Released desktop-version history |

## Archive

[`archive/`](archive/README.md) holds earlier UI decisions, handoffs and
integration records, mostly from the desktop-to-web transition. They are
optional evidence, never current instructions; its README says when each one is
still worth opening. Do not create another session handoff when
`CURRENT_TASK.md`, `TASK_HISTORY.md`, or a subject reference can hold the fact.

## Maintenance rule

Each fact has one owner. Link to that owner instead of restating it. Current
scope belongs in `CURRENT_TASK.md`; completed evidence belongs in
`TASK_HISTORY.md`; durable rationale belongs in `DECISIONS.md`; file locations
belong in `CODEMAP.md`.
