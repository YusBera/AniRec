# Project Definition

## What AniRec Is

AniRec recommends anime and shows its reasoning. A reader connects an existing
anime list, AniRec reads taste from the scores they have already given, and it
proposes titles they have not seen with evidence attached to each one.

The differentiator is not the ranking. It is that every recommendation can be
inspected: what contributed, how much, and what the system does not know.

## Platform Priority

The platforms are built in this order. The order is a commitment, not a
preference, and it decides engineering trade-offs when they conflict.

| Priority | Platform | Status |
| --- | --- | --- |
| 1 | Web application | In development, primary target |
| 2 | Mobile application | Planned, not started |
| 3 | Recommendation API for third parties | Intended revenue, deliberately deferred |

**Web first** means the browser client is the product. A feature that exists only
in the desktop application is not shipped. A web surface that instructs the
reader to install a desktop application is a defect, not a limitation.

**Mobile second** means the web application is built responsively and the API is
a real contract from the start, so the mobile client is a client rather than a
rewrite. It does not mean building a mobile app now.

**Third-party API third** means keeping the option open at near-zero cost, not
building it. The one concession made today is the shape of the scoring input:
a generic interaction list rather than a MyAnimeList-specific payload. Partner
keys, metering, billing, and SLAs are explicitly out of scope until the public
product works.

## Who It Is For

A person who already tracks anime, has rated enough of it to describe a taste,
and wants something to watch next that is not simply the current most popular
title.

Secondary, later: a platform that hosts or streams anime and wants
recommendations for its own users, who will not have MyAnimeList accounts. This
is why identity and scoring must not assume MyAnimeList.

## What AniRec Is Not

* Not a list manager. It reads an existing list; it does not replace one.
* Not a social network. There is no feed, no following, no friend graph.
* Not a streaming service or a catalogue browser.
* Not a desktop application. `AniRec/gui/` is a development and power-user tool
  that is being retired.

## Hard External Constraints

AniRec depends on third-party anime data, and the terms attached to that data
bound what the product may become. These are recorded here because they
constrain architecture, not just legal review.

* The MyAnimeList API agreement requires express written authorisation before an
  application built on it generates revenue. The third-priority partner API is
  squarely commercial and runs directly into this.
* That agreement prohibits scraping and requires content to be obtained through
  the API.
* Redistribution of MyAnimeList content is restricted, which covers serving their
  synopses and cover images from AniRec's own surfaces.
* Importing a public list by username requires the application's MAL Client ID,
  not the reader's OAuth token. OAuth storage is therefore unnecessary for the
  normal public-list import path; it is needed for private lists and writes.
* MAL relations and recommendations are available only per title. Building the
  full relation graph through the public API would require roughly one request
  per catalogue title, reinforcing D-003's collector-snapshot source.
* MAL's published spec describes an obsolete implicit login flow. The working
  integration uses authorization code with PKCE (`plain`); do not rewrite it to
  match that stale authentication section.

These constraints are the reason accounts are AniRec's own and MyAnimeList is one
importer among several planned. See `docs/DECISIONS.md`.

## What Success Looks Like

Near term, for the web application:

* A person with no prior AniRec presence can sign up, import a list, and receive
  recommendations without leaving the browser.
* No recommendation is a continuation of a story the reader has not started.
* Every recommendation can be expanded into a reason that reconciles with its score.
* A value the system does not have is shown as unavailable rather than invented.

Not yet measurable, and deliberately not claimed: that the recommendations are
good. The project has a measured baseline table for its rankers
(`docs/design/RECOMMENDER_EVALUATION.md`) and no user-satisfaction signal at all.
