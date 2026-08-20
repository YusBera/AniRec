# AniRec 2.0.0 second-computer user acceptance

Do not include a Client ID, Client Secret, authorization code, token, username, anime history, profile data, or unredacted log content.

## Test environment

- Tester:
- Date and timezone:
- Windows edition/version/build:
- Architecture:
- Package ZIP SHA-256:
- `verify_windows_acceptance.ps1` result: `PASS` / `FAIL`

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
