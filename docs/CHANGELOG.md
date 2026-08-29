# AniRec changelog

Release notes for every shipped version, newest first.
Packaging and acceptance evidence for superseded versions is in [release/HISTORY.md](release/HISTORY.md).

---

## 1.3.0

AniRec 1.3.0 rebuilds how recommendations are calculated, explained, and
presented. It is the last release before the learned model: 2.0 is reserved
for the neural recommender, which needs a corpus that is still being
collected. Existing profiles keep working: stored settings and saved
collections round trip unchanged, and a taste profile written by an earlier
version still loads.

### Recommendations are now based on what you liked, not what you watched

The previous model multiplied a genre's share of your history by its mean
rating divided by its own median. Both came from the same sample, so that ratio
equalled one for any consistently rated genre and the result reduced to a
frequency count. It could not represent dislike at all, and a genre watched
twenty times and rated poorly outranked one watched twice and loved.

Recommendations now come from a taste profile that:

- centres your ratings on your own average, so being a generous or a harsh
  rater no longer skews the result;
- weighs each genre by how much evidence stands behind it, so one enthusiastic
  rating does not outrank a long consistent record;
- can represent dislike, and uses it;
- looks beyond genre to studio, source material, media type, and era;
- scores by similarity rather than by adding weights up, so a title carrying
  many tags no longer beats a precise match on volume alone;
- accounts for how many people rated a title, so an obscure entry with a
  handful of perfect scores does not displace a widely loved one;
- optionally consults MyAnimeList's own recommendation graph, walked outward
  from your highest rated titles.

### Percentages mean something now

A match percentage is calibrated against fixed constants rather than against
whatever else happened to be in the same batch. The same anime scores the same
in every run, "Recommend 5 more" no longer returns a second batch on a
different scale, and the top result is no longer always exactly 100 percent.
Negative percentages can no longer reach the interface.

### Explanations add up

Every recommendation shows the parts its score was built from, including
negative ones, the community rating, and anything summarised beyond the named
few. Those parts add up to the percentage shown beside them. Previously they
were in different units entirely, truncated to three, and silently dropped
anything negative.

### Feedback is counted once

Liked and Not for me votes were applied twice, once when recommendations were
generated and again when they were displayed, using two different aggregations
and mixing units. They are now applied in exactly one place, bounded so
repeated votes converge, and no longer depend on the order they are replayed
in.

### First run

- The setup step links to the MyAnimeList API page and explains what a Client
  ID is, in plain language.
- The redirect URI MyAnimeList requires is shown with a copy button.
- The Client Secret field is now actually reachable. It was previously built
  but never placed on screen, so the connection step could be refused with no
  way to correct it.
- Approving access in the browser no longer appears to leave the window
  frozen. A second, non dismissable error dialog was being raised behind the
  modal setup window.
- The local callback can no longer hang indefinitely on a browser's
  speculative connection, so the timeout and the cancel button work.
- **Look around with sample data** explores the whole application without an
  account.

### A simpler interface

Six utility-heavy destinations became five focused product surfaces: Discover,
My Library, My Profile, Compare, and Settings. The dashboard and genre analysis
are folded into Discover. My Profile calculates rating distribution, community
alignment, genre, studio, era, and seasonal statistics from the active synced
profile. It does not call or modify the recommendation engine. Compare adds a
truthful sample-backed taste comparison surface without inventing live
compatibility data. Discover can combine genre, studio, year, score, status,
episode, and up to five profile filters; active filters remain visible as
keyboard-accessible technical tags that wrap instead of scrolling out of
sight. The seven individual data steps now sit behind a developer tools switch,
replaced for normal use by a single button. The candidate pool size, randomness
factor, and deterministic seed became one Adventurousness slider.

### A new look

Warm, near neutral surfaces let cover artwork carry the visual weight, with a
single accent. Light and dark are generated from one set of design tokens, so
they style exactly the same surfaces; previously context menus and the progress
dialog were themed only in dark. Font scaling now moves the whole type
hierarchy together instead of growing body text while headings stayed fixed.

### Appearance and layout

Four themes rather than two. OLED black uses true black, which switches pixels
off entirely on an OLED panel. Gradient blends between two colours you choose,
with a live preview; only the background is really yours, because the surfaces
and text are derived from your colours so the result stays readable whatever
you pick.

The feed can be shown as a grid of cards, as a compact list, or as a table. The
list trades the poster for density: a small thumbnail, the title, a truncated
reason, and a tag, so several times as many titles fit the same space. The grid
adds columns as the window widens. Whichever you choose is remembered.

Appearance and layout choices no longer require an account. Saving any setting
previously demanded a Client ID, which meant nothing chosen while looking
around could be kept.

### Also fixed

- Titles you hid or rejected no longer return through "Recommend 5 more".
- The genre panel reports real counts and averages. Every row previously read
  zero because those values were never populated.
- The "Minimum MAL score" setting now filters. It had no effect at all.
- Untitled entries no longer match one another and exclude valid candidates.
- "System" theme follows the desktop without needing a restart.

### Known limitations

- The collaborative signal is optional and absent until a run has walked the
  graph.
- The learned model is not in this release. The scoring blend already carries
  its term at weight zero and renormalises without it, so it can be added
  without disturbing anything here.
- 1.3.0 has been exercised on the development Windows 11 machine. A second
  Windows 10 or 11 acceptance run is still required.
- The package is unsigned and ships as `onedir`.
- Local secrets are not held in an encrypted operating system vault.

---

## 1.2.2

AniRec v1.2.2 is a maintenance release focused on reliable setup, MAL data completeness,
and local-data controls.

### Changes

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

### Verification

- Full networkless test suite: `364 passed`.
- Package type: Windows x64 PyInstaller `onedir`.
- Real OAuth and second-computer acceptance require manual verification with the user's own MyAnimeList application.

AniRec is unofficial and is not affiliated with or endorsed by MyAnimeList.

---

## 1.2.0

AniRec v1.2.0 turns the original recommendation workflow into a modern Windows desktop application while preserving the command-line interface.

### Highlights

- Modern English PySide6 desktop interface with an OLED-black theme, compact recommendation cards, table view, responsive navigation, and polished progress/error states.
- Streamlined MyAnimeList setup using a user-provided Client ID and a public profile URL or username; normal onboarding does not require OAuth.
- Explainable recommendations based on MAL anime IDs, scores, genres, and profile history.
- Adaptive taste learning: every Like or Not for me vote immediately updates genre affinities and reranks future recommendations.
- Editable For You, Liked, Disliked, and Watch Later libraries, plus Recommend 5 more and the 10-anime empty-feed refill.
- Working MAL synchronization, genre analysis, local profiles, safe data management, cover caching, light/dark themes, and the original CLI workflow.
- Background operations with cancellation, guarded retry, redacted errors, and automatic close after successful completion.

### Windows download

Download `AniRec-1.2.0-Windows-x64.zip`, extract the entire archive, and run `AniRec\AniRec.exe`. Keep the `_internal` directory beside the executable.

SHA-256: `ECA1B1A895E120090DBAE98545A8A2CA2BB3233AEA2109D4F55F5609BF8DC65C`

The build is a Windows x64 PyInstaller `onedir` package. It is unsigned, so Windows SmartScreen may show a warning. No installer or automatic updater is included.

### Verification

- 358 automated tests passed.
- Clean PyInstaller 6.21 Windows x64 build passed.
- Packaged application visible-window launch and normal-close smoke passed with exit code 0.
- File/product version is 1.2.0 and the executable uses the Windows GUI subsystem.
- Source and distribution privacy/security audits found no personal MAL profile, Client ID, token, private-key block, or developer path.
- The download includes a per-file SHA-256 manifest and a non-destructive Windows acceptance preflight.

AniRec is unofficial and is not affiliated with or endorsed by MyAnimeList.
