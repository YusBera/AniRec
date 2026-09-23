# Current Task

## Status: Goals 1-3 committed; Goal 4 runs separately

As reported in the 2026-09-23 cross-session handoff, Goal 4's chronological
training grid is scheduled in `AniRecTrainer`/`AniRecTrainerWork` under another
owner. Do not alter its frozen trainer source or its scheduled task. The local
backend state lock and the local API request-field authority fix are complete.
D-014 records the accepted hosted database direction; the local single-user
mode is still undecided, so account/login/migration work remains paused.

Goals 1-3 and vote collection are committed (`4671326`, `fbda46e`, `911fe21`).
React UI refinement continues in another session and works from the UI
contract in `UI_ENGINE_INTEGRATION.md`. The Goal 2/3 record below is retained as
implementation history.

## Task: honest personal fit and "why was this recommended to me?"

**Decisions:** `DECISIONS.md` D-008 (resolved), D-012.

**Owner:** `AniRec/scoring/explanation.py`; ranks in `recommendation_system.py`
and `scoring/engines.py`; the service call site in
`services/recommendation_service.py`.

### Implemented

- The uncalibrated "personal match" percentage is retired for every engine.
  The API sends `personal_match: 0.0`, `personal_match_available: false` and no
  percentage-point breakdown.
- Personal fit is the engine's rank before diversity selection:
  `fit_rank`, `fit_pool_size` and `fit_top_percent`. Each generated feed
  records a ranking snapshot in `ranking_signals.csv`: similar-viewer scores,
  franchise and hidden exclusions, eligibility date, input digest and engine.
  "More" continues exactly that ranking, so ranks are unique across a feed and
  its batches, and refuses with "Generate a new feed" when the inputs changed.
- `why` explains each served row with the answering engine's own method:
  - heuristic: `exact-additive` score parts, with evidence from genuine
    ratings only;
  - sequence model: deterministic `counterfactual-removal` over the model's
    input window;
  - otherwise `unavailable`.
- Genre feedback touches only `genre:` features, including for never-rated
  genres.
- The API's sync, generate and "more" operations now save their results, so
  the web feed shows them. Before, a web "more" batch was computed but never
  shown. These three feed-writing operations never overlap for one profile.
- The UI contract is in `UI_ENGINE_INTEGRATION.md`. Generated API types are
  regenerated.

### Boundaries kept

No retraining, no new snapshot, no change to eligibility or selection. The
deprecated PySide client still renders its own legacy percentage from the
presentation model.

## Goal 3: activity attribution (complete)

- Activity events (schema 2) record, server-side from the served row:
  - the engine's rank before selection (`model_rank`, previously the feed
    position);
  - the feed position (`feed_rank`);
  - the ranking snapshot (`ranking_id`);
  - the selection policy and adventurousness that chose the row.
- Existing stores migrate in place.
- Each recommendation records the selection it was chosen under, so a "more"
  batch selected with a different adventurousness stays attributable.
- The feed fingerprint no longer hashes the retired percentage.
- Full, "more" and single-step generation read the profile's saved hidden
  titles themselves when a caller passes none, so the CLI, the desktop app and
  the API all exclude them. Single-step also accepts feedback adjustments,
  though no current client sends any.
- Each event also records the catalogue version, and every ranking snapshot
  is archived by `ranking_id`, so an event stays resolvable after later
  generations.

## Likes and dislikes (D-013)

Votes are collected with time and attribution, and are not fed into ranking.
The UI session adds the buttons from the contract in
`UI_ENGINE_INTEGRATION.md`.

## Next task

For account/login work, obtain the user's D-014 local-mode choice before writing
identity or migration code. The Goal 4 owner will complete evaluation and
decision; ONNX export and promotion are separate later work. A future state
service task must address stale whole-state `save()` calls.
