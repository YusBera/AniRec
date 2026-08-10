# AniRec 1.2.2 — second-computer user acceptance

Do not include a Client Secret, OAuth code, token, username, anime history, profile data, or unredacted log content.

## Test environment

- Tester:
- Date and timezone:
- Windows edition/version/build:
- Architecture:
- Package ZIP SHA-256:
- `verify_windows_acceptance.ps1` result: `PASS` / `FAIL`

## Interactive acceptance matrix

| Check | Result | Sanitized note |
|---|---|---|
| `AniRec.exe` opens without a console window |  |  |
| Icon, themes, QSS and placeholders render |  |  |
| Client ID plus public MAL profile validates before OAuth |  |  |
| First-run OAuth step opens the browser and requires approval |  |  |
| Advanced Operations OAuth button opens browser when no token exists |  |  |
| OAuth callback completes and status becomes Completed |  |  |
| Existing token is reused/refreshed on a later run |  |  |
| Public sync and initial analysis complete |  |  |
| Recommendations, filters, details and settings work |  |  |
| Include NSFW changes MAL history and Top Anime fetching |  |  |
| Confirmed local-profile and all-local-data deletion remove their targets |  |  |
| Offline/error flow is safe and contains no traceback/secrets |  |  |
| Unicode anime title and Turkish-character app-data path work |  |  |
| Closing during an operation leaves no orphan AniRec process |  |  |

## Final decision

- Overall result: `PASS` / `FAIL` / `BLOCKED`
- Personal data removed from this document: `YES` / `NO`
- Sanitized issue summary:
