# AniRec 1.2.2 — development-machine EXE smoke

Date: 2026-08-10 (Europe/Istanbul)
Artifact: `dist/AniRec/AniRec.exe`

All automated fixtures are synthetic. Do not record a Client Secret, authorization code, token, username, anime history, or unredacted log content here.

| Check | Status | Evidence |
|---|---|---|
| Windows GUI executable; no console | PENDING | Run `verify_windows_acceptance.ps1`. |
| File/product version is `1.2.2` | PENDING | Verify the EXE version resource. |
| Icon, QSS, placeholders, asset notice and GPL license | PENDING | Verify the frozen resource tree. |
| Public Client ID/profile validation followed by required OAuth | PASS (automated) | Setup wizard regression tests. |
| Advanced OAuth button opens authorization when token is missing | MANUAL | Requires a configured MAL app and browser callback. |
| Existing token reuse/refresh | PASS (automated) | Auth service regression tests. |
| Include NSFW and local-data deletion controls | PASS (automated) | Settings, MAL data and deletion regressions. |
| Full networkless suite | PASS | 364 tests passed. |
| Second Windows computer acceptance | PENDING | Complete `USER_ACCEPTANCE.md`. |
