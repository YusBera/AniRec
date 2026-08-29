# Second-computer user acceptance

Do not include a Client ID, Client Secret, authorization code, token, username, anime history, profile data, or unredacted log content.

## Test environment

- Version under test:
- Tester:
- Date and timezone:
- Windows edition/version/build:
- Architecture:
- Package ZIP SHA-256:
- `verify_windows_acceptance.ps1` result: `PASS` / `FAIL`

## How to start

1. Extract the complete ZIP to a normal user-writable folder.
2. Open PowerShell in the extracted package root.
3. Run:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .erify_windows_acceptance.ps1 -Launch
   ```

4. Confirm the preflight is `PASS`, then complete every row below.

Rows below cover the current release. When a release adds or removes a
user-visible behaviour, edit this table in the same change — do not fork a
per-version copy of this file.

## Interactive acceptance matrix

Record `PASS`, `FAIL`, or `BLOCKED` for each row.

| Check | Result | Sanitized note |
|---|---|---|
| `AniRec.exe` opens without a console window |  |  |
| Icon, both themes, and placeholder artwork render |  |  |
| Navigation shows exactly Discover, My Library, and Settings |  |  |
| Look around with sample data fills every surface without an account |  |  |
| Sample banner stays visible and Connect my account reopens setup |  |  |
| Setup explains Client ID and links to the MyAnimeList API page |  |  |
| Redirect URI copy button places the exact value on the clipboard |  |  |
| Client ID and Client Secret are both enterable |  |  |
| Client ID plus public profile validates before the connection step |  |  |
| Connection step opens the browser and requires approval |  |  |
| Approving in the browser advances the setup window |  |  |
| A wrong Client ID reports inline, with no undismissable dialog |  |  |
| Cancelling the connection returns control immediately |  |  |
| Closing the setup window always closes it |  |  |
| First analysis completes and Discover shows recommendations |  |  |
| Each recommendation breakdown adds up to its match percentage |  |  |
| Why these? names the genres driving the feed |  |  |
| Love it and Not for me move titles into My Library |  |  |
| A rejected title does not return via Recommend 5 more |  |  |
| Match percentages stay stable across Recommend 5 more |  |  |
| Adventurousness slider changes how far results range |  |  |
| Developer tools switch reveals and hides the data steps |  |  |
| Theme, System theme, and font scale apply immediately |  |  |
| Context menus and the progress dialog are themed in light mode |  |  |
| Local data actions state their exact scope before deleting |  |  |
| Logs contain no credential or personal content |  |  |

## Outcome

- Overall result: `PASS` / `FAIL` / `BLOCKED`
- Blocking issues:
- Follow-up required:

Return only this completed Markdown file, and screenshots with personal
information removed. Do not return `ACCEPTANCE_STATIC_RESULTS.txt` if it
contains a Windows account name or extraction path you would rather not share.
