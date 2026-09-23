# Account and profile scope: current implementation

This is an inventory, not an account design approval. D-002 requires AniRec-owned
accounts, but no AniRec account or browser session exists yet. The current
`profile_id` names a local MyAnimeList import/profile, not a signed-in AniRec
person. The local API's optional per-launch bearer token authenticates one
process, not a reader; development mode can run without that token. Origin and
loopback checks protect the local service but cannot establish account ownership
on a hosted server (`AniRec/api/security.py`, `AniRec/api/app.py`).

## Where the current scope comes from

| Path | Scope chosen today | Consequence for accounts |
| --- | --- | --- |
| `ProfileService.create_profile`, `resolve_profile` | MAL numeric ID when available, otherwise a username-derived slug; `resolve_profile` searches existing profiles by MAL username | An imported MAL identity is being used as the storage identity. Two AniRec readers importing the same public list would collide. |
| `ProfileService.set_active`, `active_profile` | One machine-wide `config/profile_state.json` points to one profile | Concurrent web readers would share or switch this pointer. It is not a session. |
| `paths.profile_dir`, `token_file` | Caller-supplied `profile_id` selects a validated direct child of `profiles/` or `tokens/` | Traversal is rejected, but a valid ID is not proof of ownership. Profile content, result, state, activity, sync and MAL tokens live behind this boundary. |
| `ApiContainer.active_profile_id`, `active_username`, `access_token_provider` | The machine-wide active profile | Reads and MAL token refresh follow global state, not a requesting account. |
| `OnboardingService` and desktop setup | Creates or selects a MAL-backed local profile and sets the active one | Import/setup currently changes machine-wide context, not one reader's account. |
| `GET /api/system/state`, `GET /api/discover/feed` | The machine-wide active profile, or labelled sample data | Any future session would see the same active person's feed until scope is changed. Sample data is deliberately ephemeral. |
| `GET|POST|DELETE /api/discover/activity`, activity settings | Active profile is selected on the server; event POST checks payload profile and current feed | Better than an arbitrary path, but still shared global identity; the event service writes in that profile directory. |
| `POST /api/discover/feedback` | Request `profile_id` is passed directly to the state service; vote attribution only checks the active feed | A well-formed ID can choose another local profile's hidden, Watch Later or vote state. The attribution check does not authorize the write. |
| `POST /api/operations/{kind}` | Request `profile_id` and `username` override the active values; operation key and result path use that ID; pipeline resolves profile again from username | The requested ID and resolved MAL profile may differ. For hosted accounts, both the work and persisted result require a server-derived owner and a checked import binding. |
| `GET /api/workspace/library`, `POST /library/resolve` | Request profile ID must equal the machine-wide active ID; checked again after reads | Active-profile equality helps local consistency but is not account authorization. |
| `GET /api/workspace/profile`, `/compare`, `/settings` | Profile statistics and comparison read the global active profile; settings are global `config/settings.json` | Settings, source credentials and current profile would be shared by hosted readers. Comparison's other MAL username is a public comparison target, not the reader's identity. |
| PySide (`gui/main_window.py`, `gui/settings_page.py`, `gui/recommendation_page.py`) | Loads or switches the global active profile; actions pass its ID to services | Valid for one local operator, but switching affects the API process using the same data root. |
| Service and pipeline calls | `profile_id` selects state/result/sync/activity/token paths; pipeline also resolves a profile by username | Services trust their caller to supply authorized scope. They are not an account boundary. |

## Required boundary before multi-reader hosting

Authenticate an AniRec reader, derive the AniRec account ID from a server-side
session, then resolve an import/profile **owned by that account**. Never accept
an account ID or storage path from a request as authority. A MAL username or ID
is source data and can identify a public list; it cannot identify its AniRec
owner. Keep sample reports outside real account storage. Decide ownership and
migration for existing `profiles/<mal-derived-id>/` directories and global
`config/settings.json`, `config/profile_state.json` and `tokens/<id>.json`
before enabling a second reader. See proposed D-014 in `DECISIONS.md`.
