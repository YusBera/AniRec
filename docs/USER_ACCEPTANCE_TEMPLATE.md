# AniRec 0.1.0 — second-computer user acceptance

Do not include a Client Secret, OAuth code, token, username, anime history, profile data, or unredacted log content in this document.

## Test environment

- Tester:
- Date and timezone:
- Windows edition:
- Windows version/build:
- System architecture:
- Package ZIP SHA-256:
- `verify_windows_acceptance.ps1` result: `PASS` / `FAIL`

## How to start

1. Extract the complete ZIP to a normal user-writable folder.
2. Open PowerShell in the extracted package root.
3. Run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\verify_windows_acceptance.ps1 -Launch
   ```

4. Confirm the preflight is `PASS`, then complete every row below.

## Interactive acceptance matrix

Use only `PASS`, `FAIL`, or `BLOCKED`. Add a short sanitized note for every `FAIL` or `BLOCKED` result.

| Check | Result | Sanitized note |
|---|---|---|
| `AniRec.exe` opens without a console window |  |  |
| Application icon, dark/light theme, QSS, and original placeholders render |  |  |
| Three-step first-run wizard opens and required steps cannot be skipped |  |  |
| Client ID plus public MAL profile URL validates in one operation |  |  |
| No browser OAuth or MAL password entry is required for the public list |  |  |
| Public MyAnimeList history loads and initial analysis completes |  |  |
| Home metrics and recommendation results appear |  |  |
| Recommendation card/table, details, filters, and all sort modes work |  |  |
| Hidden and Watch Later state persist after restart |  |  |
| Genre Analysis and Advanced Operations open and show prerequisites/results |  |  |
| Theme, font scale, cover preference, settings, and active profile persist after restart |  |  |
| Disconnecting the network produces a safe retryable error without traceback or secret text |  |  |
| Reconnecting allows retry without a duplicate operation |  |  |
| A Unicode anime title renders correctly |  |  |
| A Windows user/app-data path containing Turkish or other Unicode characters works |  |  |
| Closing during a running operation exits safely without an orphan AniRec process |  |  |

## Final decision

- Overall result: `PASS` / `FAIL` / `BLOCKED`
- AniRec process remaining after close: `YES` / `NO`
- Personal data reviewed and removed from this report: `YES` / `NO`
- Sanitized issue summary:

Return only this completed Markdown file and, if needed, screenshots with personal information removed. Do not return the generated `ACCEPTANCE_STATIC_RESULTS.txt` if it contains a Windows account or extraction path the tester does not want to share.
