# AniRec v1.2.2

AniRec v1.2.2 is a maintenance release focused on reliable setup, MAL data completeness,
and local-data controls.

## Changes

- First-run setup validates the Client ID and public profile, then requests profile-scoped
  MyAnimeList OAuth approval before the initial analysis.
- Advanced Operations now uses the OAuth button for both actions:
  - reuse or refresh an existing profile token;
  - open the MyAnimeList authorization page when no token exists.
- OAuth progress states are shown in the Advanced Operations card.
- OAuth authorization status forwarding is covered by regression tests.
- Settings includes an **Include NSFW anime** checkbox. When enabled, both Top Anime and
  user-list requests include MAL's NSFW-labelled titles; completed rewatches are retained.
- **Delete local profile** and **Delete all local data** now correctly accept the Qt
  confirmation result and execute the selected deletion.
- Existing CLI, public-list pipeline, token storage, and cancellation behavior remain compatible.

## Verification

- Full networkless test suite: `364 passed`.
- Package type: Windows x64 PyInstaller `onedir`.
- Real OAuth and second-computer acceptance require manual verification with the user's own MyAnimeList application.

AniRec is unofficial and is not affiliated with or endorsed by MyAnimeList.
