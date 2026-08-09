# AniRec v1.2.0

AniRec v1.2.0 turns the original recommendation workflow into a modern Windows desktop application while preserving the command-line interface.

## Highlights

- Modern English PySide6 desktop interface with an OLED-black theme, compact recommendation cards, table view, responsive navigation, and polished progress/error states.
- Streamlined MyAnimeList setup using a user-provided Client ID and a public profile URL or username; normal onboarding does not require OAuth.
- Explainable recommendations based on MAL anime IDs, scores, genres, and profile history.
- Adaptive taste learning: every Like or Not for me vote immediately updates genre affinities and reranks future recommendations.
- Editable For You, Liked, Disliked, and Watch Later libraries, plus Recommend 5 more and the 10-anime empty-feed refill.
- Working MAL synchronization, genre analysis, local profiles, safe data management, cover caching, light/dark themes, and the original CLI workflow.
- Background operations with cancellation, guarded retry, redacted errors, and automatic close after successful completion.

## Windows download

Download `AniRec-1.2.0-Windows-x64.zip`, extract the entire archive, and run `AniRec\AniRec.exe`. Keep the `_internal` directory beside the executable.

SHA-256: `ECA1B1A895E120090DBAE98545A8A2CA2BB3233AEA2109D4F55F5609BF8DC65C`

The build is a Windows x64 PyInstaller `onedir` package. It is unsigned, so Windows SmartScreen may show a warning. No installer or automatic updater is included.

## Verification

- 358 automated tests passed.
- Clean PyInstaller 6.21 Windows x64 build passed.
- Packaged application visible-window launch and normal-close smoke passed with exit code 0.
- File/product version is 1.2.0 and the executable uses the Windows GUI subsystem.
- Source and distribution privacy/security audits found no personal MAL profile, Client ID, token, private-key block, or developer path.
- The download includes a per-file SHA-256 manifest and a non-destructive Windows acceptance preflight.

AniRec is unofficial and is not affiliated with or endorsed by MyAnimeList.
