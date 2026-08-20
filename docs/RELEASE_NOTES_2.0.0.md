# AniRec 2.0.0 release notes

AniRec 2.0.0 rebuilds how recommendations are calculated, explained, and
presented. Existing profiles keep working: stored settings and saved
collections round trip unchanged, and a taste profile written by an earlier
version still loads.

## Recommendations are now based on what you liked, not what you watched

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

## Percentages mean something now

A match percentage is calibrated against fixed constants rather than against
whatever else happened to be in the same batch. The same anime scores the same
in every run, "Recommend 5 more" no longer returns a second batch on a
different scale, and the top result is no longer always exactly 100 percent.
Negative percentages can no longer reach the interface.

## Explanations add up

Every recommendation shows the parts its score was built from, including
negative ones, the community rating, and anything summarised beyond the named
few. Those parts add up to the percentage shown beside them. Previously they
were in different units entirely, truncated to three, and silently dropped
anything negative.

## Feedback is counted once

Liked and Not for me votes were applied twice, once when recommendations were
generated and again when they were displayed, using two different aggregations
and mixing units. They are now applied in exactly one place, bounded so
repeated votes converge, and no longer depend on the order they are replayed
in.

## First run

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

## A simpler interface

Six destinations became three: Discover, My Library, and Settings. The
dashboard and genre analysis are folded into Discover. The seven individual
data steps now sit behind a developer tools switch, replaced for normal use by
a single button. The candidate pool size, randomness factor, and deterministic
seed became one Adventurousness slider.

## A new look

Warm, near neutral surfaces let cover artwork carry the visual weight, with a
single accent. Light and dark are generated from one set of design tokens, so
they style exactly the same surfaces; previously context menus and the progress
dialog were themed only in dark. Font scaling now moves the whole type
hierarchy together instead of growing body text while headings stayed fixed.

## Also fixed

- Titles you hid or rejected no longer return through "Recommend 5 more".
- The genre panel reports real counts and averages. Every row previously read
  zero because those values were never populated.
- The "Minimum MAL score" setting now filters. It had no effect at all.
- Untitled entries no longer match one another and exclude valid candidates.
- "System" theme follows the desktop without needing a restart.

## Known limitations

- The collaborative signal is optional and absent until a run has walked the
  graph.
- 2.0.0 has been exercised on the development Windows 11 machine. A second
  Windows 10 or 11 acceptance run is still required.
- The package is unsigned and ships as `onedir`.
- Local secrets are not held in an encrypted operating system vault.
