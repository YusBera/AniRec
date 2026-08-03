# AniRec 0.1.0 — development-machine EXE smoke

Date: 2026-08-03 (Europe/Istanbul)
Host: Windows 11 23H2 (`10.0.22631`), x64
Artifact: `dist/AniRec/AniRec.exe`

All credentials and anime/profile records used below are synthetic fixtures. No real MyAnimeList account or token was used.

| Check | Status | Evidence |
|---|---|---|
| Windows GUI executable; no console | PASS | PE subsystem is `IMAGE_SUBSYSTEM_WINDOWS_GUI` (`2`), machine `0x8664`. |
| Version and application icon | PASS | Windows file/product version is `0.1.0`; EXE has a resource table and the original multi-size ICO. |
| QSS, placeholders, asset notice, GPL license | PASS | Seven required resource files exist below `_internal/gui/resources`; `LICENSE` also exists at the distribution root. |
| Clean first-run launch and setup wizard | PASS | Real packaged EXE opened `AniRec` plus modal `Set up AniRec`; [first-run screenshot](images/anirec-first-run-wizard.png). |
| First-run controlled close | PASS | Wizard received `WM_CLOSE`, then the main window received `WM_CLOSE`; process exited with code `0` and no AniRec process remained. |
| Writable data stays outside `dist` | PASS | Real EXE created `AniRec/logs/anirec.log` below an isolated `%APPDATA%` parent containing Turkish characters. |
| Settings/profile/token/result folders | PASS | Versioned synthetic state was written through AniRec services under `config/`, `profiles/mal-4242/`, `tokens/`, and `logs/`; the packaged EXE read it successfully. |
| Theme/profile/result persistence after reopen | PASS | Packaged EXE reopened in the saved light theme with profile metrics and two recommendations, then exited through `WM_CLOSE` with code `0`; [persisted home screenshot](images/anirec-home.png). |
| Unicode anime/profile and Turkish-character path | PASS | The packaged GUI rendered `Türkçe Kullanıcı`, `葬送のフリーレン`, and `Gökyüzü Hikayesi`; its isolated `%APPDATA%` parent also contained `Türkçe`. |
| Safe recommendation flow | PASS | A mock `PipelineResult` produced by the same validated service/model boundary loaded in the packaged Home view; the full networkless pipeline and GUI path are covered by the regression suite. |
| Offline/timeout controlled error | PASS (mocked) | Fault-injection tests exercise connection loss, timeout, retry, safe dialog text, and post-error worker reuse. A machine-wide network disconnect was not performed. |
| Optional OAuth service lifecycle | PASS (mocked) | The compatibility service retains bounded callback, cancellation, state validation, and cleanup coverage. |
| Real public MyAnimeList profile flow | PASS (service integration) | The user's profile URL, ranking data, and non-empty completed list validated with Client ID authentication and no OAuth token; personal anime records were not printed. |
| Clean RC6 package launch and normal close | PASS | The final clean `dist\AniRec\AniRec.exe` exposed two visible first-run windows, both received normal `WM_CLOSE`, and the process exited with code `0` without forced termination. |
| Successful operation dialog lifecycle | PASS (GUI regression) | A completed worker result reaches 100%, displays a bounded success state, and closes automatically; error and cancellation paths remain inspectable. |

The first-run and persisted-state executions used separate clean or isolated app-data roots. The physical network adapter, firewall, registry, and user credential stores were not modified.
