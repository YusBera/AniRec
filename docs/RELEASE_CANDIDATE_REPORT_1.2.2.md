# AniRec 1.2.2 release report

## Scope

This release packages OAuth connect/refresh corrections, required first-run OAuth approval,
complete optional NSFW fetching, and reliable local-data deletion on top of 1.2.0.

## Included changes

- `AuthService.get_access_token(..., interactive=True)` forwards OAuth status callbacks.
- Advanced Operations starts interactive OAuth when a profile has no stored token.
- Existing tokens are reused or refreshed when possible.
- Advanced OAuth status text is relayed to the operation card.
- Regression coverage verifies interactive authorization and Advanced Operations wiring.
- First-run setup requires OAuth approval after public Client ID/profile validation.
- Include NSFW is persisted and applied to both Top Anime and completed-list requests.
- Completed rewatches remain in the completed dataset when NSFW inclusion is enabled.
- Qt confirmation values now trigger local-profile and all-local-data deletion reliably.

## Automated verification

| Check | Result |
|---|---|
| Targeted auth/worker/advanced tests | PASS — 13 passed |
| Full networkless pytest suite | PASS — 364 passed |
| `git diff --check` | PASS |
| Public Client ID/profile validation precedes OAuth | PASS — covered by setup tests |
| Real OAuth browser/callback | MANUAL — requires user account and MAL app |
| Second Windows computer acceptance | PENDING |

## Package contents

The release is a Windows x64 PyInstaller `onedir` bundle. Keep the complete `AniRec` directory and `_internal` directory together. Verify the package with `verify_windows_acceptance.ps1` before manual acceptance.

## Known limitations

- The package is unsigned and has no installer, auto-update, or `onefile` artifact.
- Client secrets/tokens rely on the Windows user account and filesystem permissions rather than an encrypted credential vault.
- Real OAuth and a second-computer run are manual acceptance items.
