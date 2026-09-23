# Code Map

Where things live. Consult this before searching. Keep it accurate: a change that
adds, moves, or renames a public endpoint, service, engine, route, or persisted
file updates the matching row in the same change.

---

## HTTP Endpoints

| Route | Handler file |
| --- | --- |
| `GET /api/health`, `GET /api/system/state`, `POST /api/system/shutdown` | `AniRec/api/app.py` |
| `GET /api/discover/feed` | `AniRec/api/app.py` |
| `POST /api/discover/feedback` | `AniRec/api/app.py` |
| `GET|POST|DELETE /api/discover/activity`, `POST /api/discover/activity/settings` | `AniRec/api/app.py` |
| `GET /api/operations`, `GET|DELETE /api/operations/{id}`, `GET /api/operations/{id}/events` | `AniRec/api/app.py` |
| `POST /api/operations/{kind}` | `AniRec/api/app.py`, handlers in `_build_handler` |
| `GET /api/workspace/library`, `POST /api/workspace/library/resolve` | `AniRec/api/workspace.py` |
| `GET /api/workspace/profile` | `AniRec/api/workspace.py` |
| `GET /api/workspace/compare` | `AniRec/api/workspace.py` |
| `GET|POST /api/workspace/settings` | `AniRec/api/workspace.py` |

Request and response models: `AniRec/api/models.py`. Error envelopes and
exception handlers: `AniRec/api/app.py`. Token and origin enforcement:
`AniRec/api/security.py`. Dependency wiring: `AniRec/api/container.py`.
OpenAPI export for type generation: `AniRec/api/openapi_export.py`.

---

## Recommendation Path

| Concern | File |
| --- | --- |
| Pipeline orchestration, candidate assembly, ranking catalogue | `AniRec/application/pipeline.py` |
| Persisted candidate population and source label | per-profile `candidate_catalogue.csv`; constants in `AniRec/application/pipeline.py` |
| Long-running operation handlers and cancellation | `AniRec/application/operations.py` |
| Engine selection and bundle wiring | `AniRec/services/recommendation_service.py` |
| Heuristic engine, ONNX sequence engine, fallback router | `AniRec/scoring/engines.py` |
| Scoring formula, contributions, calibration | `AniRec/scoring/ranking.py` |
| Taste profile construction, affinity, shrinkage, idf | `AniRec/scoring/taste.py` |
| MAL field meanings and heuristic use | `docs/MAL_DATA_SEMANTICS.md` |
| Feature tokens and namespaces | `AniRec/scoring/features.py` |
| Relation graph, franchise exclusion, collaborative scores | `AniRec/scoring/collaborative.py` |
| Engine contract and metadata | `AniRec/scoring/contracts.py` |
| Shared final eligibility policy and aggregate audit | `AniRec/scoring/eligibility.py` |
| "Why this pick": explanation builders and shared row columns | `AniRec/scoring/explanation.py`; heuristic parts from `recommendation_system.py`, sequence-model removal in `engines.py::OnnxSequenceRankingEngine.explain` |
| Shared deterministic feed selection (adventurousness, diversity) | `AniRec/scoring/selection.py`; called once in `AniRec/services/recommendation_service.py` |
| Heuristic ranked pool (`rank_candidate_pool`) and legacy CSV entry point | `AniRec/recommendation_system.py` |
| Pipeline tuning defaults | `AniRec/models/domain.py` |

Measured behaviour of both engines: `docs/design/RECOMMENDER_EVALUATION.md`.
ONNX bundle contract: `docs/ONNX_MODEL_SERVING.md`.

---

## Services

| Concern | File |
| --- | --- |
| MyAnimeList list sync | `AniRec/services/mal_sync_service.py` |
| Anime metadata fetch | `AniRec/services/anime_data_service.py` |
| Relation/recommendation graph cache | `AniRec/services/anime_graph_service.py` |
| OAuth and token storage | `AniRec/services/auth_service.py`, `AniRec/services/token_store.py` |
| Account/profile records | `AniRec/services/profile_service.py` |
| Saved decisions (watch later, set aside) | `AniRec/services/recommendation_state_service.py` |
| Settings load and save | `AniRec/services/settings_service.py` |
| Taste profile statistics | `AniRec/services/taste_profile_service.py` |
| Library, compare, settings reads for the workspace | `AniRec/services/workspace_service.py` |
| Activity events | `AniRec/services/recommendation_event_service.py` |
| Explicit taste feedback | `AniRec/services/taste_feedback_service.py` |
| Result persistence | `AniRec/services/result_service.py` |
| Sample library and demonstration payloads | `AniRec/services/sample_data_service.py` |
| First-run flow | `AniRec/services/onboarding_service.py` |
| Cover image fetch and cache | `AniRec/services/cover_image_service.py` |
| Folder and cache management | `AniRec/services/data_management_service.py` |
| Connection test | `AniRec/services/api_connection_service.py` |

---

## Infrastructure and Shared

| Concern | File |
| --- | --- |
| MyAnimeList HTTP client, pagination, rate errors | `AniRec/infrastructure/mal_client.py` |
| CSV read/write and batch transactions | `AniRec/infrastructure/csv_storage.py` |
| JSON read/write | `AniRec/infrastructure/json_storage.py` |
| Log redaction set | `AniRec/infrastructure/logging_config.py` |
| Data root and resource paths | `AniRec/infrastructure/paths.py` |
| Single-instance lock | `AniRec/infrastructure/single_instance.py` |
| OAuth redirect handling | `AniRec/infrastructure/oauth_callback.py` |
| MAL payload to domain mapping, CSV columns | `AniRec/core/mal_mapping.py` |
| View models shared by both clients | `AniRec/presentation/` |

---

## Frontend

| Concern | File |
| --- | --- |
| Entry point and provider wiring | `frontend/src/main.tsx` |
| Workspace shell, hash routing, nav | `frontend/src/workspace/Workspace.tsx` |
| My Library | `frontend/src/workspace/LibraryPage.tsx` |
| Profile | `frontend/src/workspace/ProfilePage.tsx`, `ProfileSections.tsx` |
| Compare | `frontend/src/workspace/ComparePage.tsx` |
| Settings | `frontend/src/workspace/SettingsPage.tsx` |
| Shared workspace pieces (read state, poster, scores) | `frontend/src/workspace/common.tsx` |
| Discover feed, votes, operations | `frontend/src/discover/DiscoverPage.tsx` |
| Recommendation card | `frontend/src/discover/RecommendationCard.tsx` |
| Inspector dialog | `frontend/src/discover/RecommendationDetails.tsx` |
| Score rail and breakdown | `frontend/src/discover/ScoreRail.tsx` |
| Filters and sort controls | `frontend/src/discover/Controls.tsx`, `filtering.ts` |
| Empty, error, loading states | `frontend/src/discover/states.tsx` |
| Activity opt-in and recording | `frontend/src/discover/useRecommendationActivity.ts` |
| Fetch client and error type | `frontend/src/api/client.ts` |
| Feed and operation hooks | `frontend/src/api/hooks.ts` |
| Hand-written types | `frontend/src/api/types.ts` |
| Generated OpenAPI types (do not hand-edit) | `frontend/src/api/generated/schema.d.ts` |
| Browser vs desktop shell abstraction | `frontend/src/platform/` |
| Design tokens, base, instrument styles | `frontend/src/styles/` |
| Dev server and `/api` proxy config | `frontend/vite.config.ts` |

---

## Persisted Files

Per-account directory under the data root:

| File | Written by | Holds |
| --- | --- | --- |
| `profile.json` | `profile_service.py` | Account record, last sync |
| `completed_anime.csv` | `pipeline.py` | Synced list with user scores |
| `candidate_catalogue.csv` | `pipeline.py` | Exact candidate population plus owned/legacy source label |
| `ranking_snapshots/<ranking_id>.csv` | `pipeline.py` | Immutable archive of each ranking snapshot, pruned after 90 days; resolves an activity event's ranking |
| `ranking_signals.csv` | `pipeline.py` | Ranking snapshot of the last generated feed: similar-viewer scores, franchise and hidden exclusions, eligibility date, input digest, engine and the `ranking_id` stamped on each recommendation; "more" continues it or refuses when inputs or the feed changed |
| `top_anime.csv` | legacy pipeline/CLI compatibility | Historical MAL ranking candidate metadata |
| `recommendation_candidates.csv` | `pipeline.py` | Filtered candidate pool |
| `genre_importance.csv` | `pipeline.py` | Serialised taste profile |
| `latest_result.json` | `result_service.py` | Last generated recommendations |
| `recommendation_state.json` | `recommendation_state_service.py` | Saved decisions: hidden, Watch Later, and likes/dislikes with time and attribution (collected, not fed; D-013) |
| `anime_graph.json` | `anime_graph_service.py` | Cached relation/recommendation graph |
| activity database | `recommendation_event_service.py` | Opt-in local activity events |

Application-wide settings, including credentials, live in `config/settings.json`
under the data root. No CSV carries a schema version; changing a column layout
has no migration path today.

---

## Deprecated

`AniRec/gui/` and `AniRec/gui_main.py` are the retired PySide application. They
still call the same service layer. Do not add surfaces there, and do not treat
their layout as authority for web work. See `docs/DECISIONS.md` D-004.

---

## Out of Repository

| What | Where |
| --- | --- |
| Model training, evaluation harness, baselines | `AniRecTrainer` |
| Scraper, coordinator snapshot, catalogue source | `AniRecDataCollector` |
| Older branch checkout without the workspace surfaces | `projects/AniRec` |
