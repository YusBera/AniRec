# AniRec 1.2.0 release report

Status: **READY FOR RELEASE**
Prepared: 2026-08-10 (Europe/Istanbul)
Development host: Windows 11 23H2 (`10.0.22631`), x64

## Deliverable

- Windows x64 ZIP: `release/AniRec-1.2.0-Windows-x64.zip`
- Acceptance ZIP size and SHA-256 are recorded in the external release handoff after the archive is finalized. Verify that handoff value before extraction.
- Previous ZIPs are superseded by the visible, editable recommendation-library and modern operation-UX build.
- Executable: `dist/AniRec/AniRec.exe`
- Distribution directory: `dist/AniRec`
- Package type: PyInstaller 6.21 `onedir`, Windows GUI subsystem, unsigned
- Version resource: file/product version `1.2.0`
- Architecture: x64 (`0x8664`)
- Files: 901
- Total directory size: 166,954,194 bytes (159.22 MiB)
- EXE SHA-256: `8C7E1AA0897EFE5C7321BCD16DEF28F9E263D81C69CF23E6E2CF6A333C02569D`

The whole `dist\AniRec` directory is the artifact. `AniRec.exe` must not be separated from `_internal`.

For transfer to another computer, use the versioned acceptance ZIP. It contains the complete onedir artifact, a non-destructive PowerShell preflight, a 905-file SHA-256/size manifest, development-machine evidence, and the user acceptance form.

## Implemented release scope

- Reusable service/domain/infrastructure pipeline shared by GUI and CLI
- MAL-ID-based filtering and deterministic, explainable recommendations
- Versioned settings, profile, token, result, and recommendation-state persistence
- Public MyAnimeList access using a Client ID plus profile URL or username;
  no OAuth token is required or stored by the normal onboarding flow
- Six-page English PySide6 desktop shell and three-step first-run wizard
- Modern Home dashboard with working sync/generation actions, genre bars, and rectangular cover cards
- Modern, compact card/table Recommendation Explorer with a hero surface, layered OLED-black styling, contextual controls, and bounded empty states
- Always-visible For You, Liked, Disliked, and Watch Later tabs with live counts and directly editable saved states
- Profile-local adaptive genre affinities, immediate explainable reranking, **Recommend 5 more**, and a 10-pick exhausted-feed refill
- Near-black OLED dark surfaces with preserved focus, text, feedback, and disabled-state contrast
- Genre Analysis, seven Advanced Operations, full Settings, appearance, and safe data management
- Background worker ownership, progress, cancellation, successful-operation auto-close, guarded retry, redacted error UX, and cleanup
- Fault-injection, GUI lifecycle, path/link/deletion, secret, packaging, and full regression coverage
- Tracked Windows icon/version/spec/build script and verified screenshots/documentation

## Automated verification

| Gate | Result |
|---|---|
| Full networkless regression | PASS — 358 tests in 120.16 seconds |
| Clean PyInstaller build | PASS — 47.5 seconds |
| Packaging/README/security contract | PASS |
| PE subsystem/version/icon/resources | PASS |
| GPL-3.0 at dist root | PASS |
| Asset license notice in dist | PASS |
| Root README in dist | PASS |
| Source/repo credential and developer-path audit | PASS |
| Dist AWS/GitHub/OpenAI-style key, full private-key block, and developer-path audit | PASS — 0 findings |
| `git diff --check` | PASS; CRLF conversion notices only |
| Final packaged launch and normal close | PASS — window `AniRec`, exit code `0` |
| Orphan AniRec/pytest process after checks | PASS — none |
| Acceptance ZIP path/duplicate/integrity audit | PASS — 914 ZIP entries; all 905 manifested files re-hashed from the archive; 0 duplicate/unsafe paths |
| Acceptance preflight on development host | PASS — Windows/x64/files/hashes/version/PE subsystem |

PyInstaller's warning file was reviewed. Its unresolved entries are conditional/platform-specific or unused optional pandas integrations. The `jinja2` warning belongs to optional pandas styling; AniRec does not use that feature. The packaged application launch and exercised recommendation views do not require it.

The Qt network DLL contains literal PEM *parser marker* strings. The final distribution audit therefore checks for a complete private-key block with encoded body, not a standalone parser constant; no key block or credential was found.

## Development-machine EXE verification

The detailed matrix is in [EXE_SMOKE.md](EXE_SMOKE.md).

- First-run packaged EXE: PASS
- Modal setup wizard and dark resources: PASS
- Wizard cancellation followed by main-window close: PASS, exit code `0`
- Writable log under isolated `%APPDATA%`: PASS
- Persisted light theme/profile/token/result state after reopen: PASS
- Turkish profile and Japanese/Turkish anime titles: PASS
- Turkish-character app-data parent path: PASS
- Final clean-build launch: PASS, exit code `0`
- Physical network-disconnect test: not performed; controlled offline behavior is fault-injection tested
- Real public-profile integration: PASS — profile URL, ranking data, and the
  completed-anime list loaded with Client ID authentication and no OAuth token;
  no anime titles or profile records were printed by the integration check
- Real public sync worker: PASS — 165 completed and 165 rated entries persisted;
  Home displayed the successful update count and `MAL: Connected`
- Five-more service smoke: PASS — five unique picks appended with zero overlap
  against the ten persisted recommendations

Screenshots:

- [First-run wizard](images/anirec-first-run-wizard.png)
- [Modern Home](images/anirec-modern-home.png)
- [Modern recommendation library](images/anirec-s15-modern-for-you.png)
- [Editable Liked collection](images/anirec-s15-editable-liked.png)
- [Modern exhausted-feed prompt](images/anirec-s15-modern-empty.png)
- [Modern Settings](images/anirec-modern-settings.png)

## User acceptance steps

On a second Windows 10 or 11 computer:

1. Copy `AniRec-1.2.0-Windows-x64.zip` and verify its SHA-256 against the GitHub release notes.
2. Extract it, open PowerShell in the extracted root, and run `powershell -ExecutionPolicy Bypass -File .\verify_windows_acceptance.ps1 -Launch`.
3. Confirm the preflight is completely `PASS`, then use `USER_ACCEPTANCE.md` to record the interactive checks.
4. Start `AniRec.exe`; confirm no console opens and the icon, dark theme, and first-run wizard render.
5. Enter the user's MAL Client ID and public profile URL (or username), then choose **Validate and Continue**.
6. Confirm the wizard advances directly to initial analysis without opening browser OAuth.
7. Complete all remaining persistence, recommendation, offline, Unicode, and shutdown rows in `USER_ACCEPTANCE.md`.
8. On Recommendations, mark one card **Like** and another **Not for me**; confirm both leave For You, appear in the visible matching tabs, and rerank the remaining cards. Open Liked or Disliked and remove or reverse one vote; open Watch Later and remove one saved item. Then choose **Recommend 5 more** and verify five unseen cards are appended.
9. Review every visible recommendation and confirm the empty feed offers **Recommend 10 new anime**; start it and verify fresh cards appear through the normal progress flow.
10. On Home, choose **Update MAL data** and verify progress briefly displays completion, closes automatically, and leaves the header at `MAL: Connected`.
11. Record Windows version and PASS/FAIL/BLOCKED results after removing personal data.

Do not send credentials, tokens, profile data, or unredacted logs with the result.

## Known limitations and blocked acceptance

- RC1 through RC5 are superseded. RC6 keeps the streamlined public Client ID
  setup and adds the visible/editable recommendation library, responsive modern
  hierarchy, more compact cards, contextual table actions, and successful
  operation auto-close.
- Private MAL anime lists are not supported by streamlined 1.2.0 onboarding;
  the list must be public.
- The executable is unsigned and has no installer, MSIX, auto-update, or SmartScreen reputation.
- `onefile` is deliberately deferred until the user accepts the `onedir` build.
- Local Client Secrets/tokens rely on the Windows user account and filesystem permissions; Windows Credential Manager is not used.
- The recommendation model is intentionally genre-based rather than collaborative filtering.

## Source-control state

- Release branch: `main`
- Feature pull request: `#1`, merged into `main` as `6d1953f13b33e18a64d6f6708953de6326367552`.
- Release tag: `v1.2.0`.
