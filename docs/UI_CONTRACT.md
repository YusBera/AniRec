# UI contract

What the web client may show from the recommendation API, and what it must
never show. The backend implements every field named here, and the
generated types in `frontend/src/api/generated/schema.d.ts` match them.
Domain rules in `DOMAIN_RULES.md` take precedence over any wording here.

## Personal fit and "why" (Goal 2)

The backend side is implemented. This is the exact contract for the UI session. The
fields are in `RecommendationViewModelResponse`, and the generated types in
`frontend/src/api/generated/schema.d.ts` are already regenerated and verified.

### Stop showing the percentage

The API now sends `personal_match: 0.0`, `personal_match_available: false` and
an empty `genre_contributions`, so today's UI already shows "unavailable". Do
not render, sort by, or compute anything from these three fields; they remain
only so older clients still parse. `personal_match_text` and
`contributing_genres` are legacy too.

### The indicator: `fit_rank`, `fit_pool_size`, `fit_top_percent`

- Show the rank, e.g. "#4 of 13,458 for you". `fit_top_percent` is
  `100 * fit_rank / fit_pool_size`. A percentile of the ranked candidates is
  fine to show; a "match %" is not.
- `fit_rank` is the engine's rank **before** diversity selection, so it can
  differ from feed position. Do not label it as feed position.
- The complete saved feed shares one `ranking_id`. `fit_rank` describes the
  model order; `rank` describes its saved browsing position after selection.
  Both remain fixed when filters or pages change. A new analysis starts a new
  ranking.

### Refresh and pages (D-018)

- **Refresh:** `POST /api/operations/refresh` with no count.
  - It syncs the list and regenerates only when needed. The result's
    `user_stats.feed_refresh` is `"missing"`, `"inputs-changed"`,
    `"engine-changed"`, `"legacy-capped-ranking"` or `"current"`;
    `"current"` keeps the saved model order.
  - Start it once per session for each profile the service reports active,
    and from the small Refresh button. That includes a profile with no feed
    yet, which is served the sample library until its first refresh. Never
    start it when there is no profile.
  - An `auth_error` is shown by its title and description only. Its
    suggested fix is to reconnect an account, which the web client cannot do
    (D-017).
- **Pages:** `GET /api/discover/feed?query=<URL-encoded JSON>` accepts page,
  genre, studio, year, MAL score, status, episode and sort selections. The API
  filters the entire saved ranking first and returns `total`, zero-based
  `page`, `page_size: 50` and only that page's recommendations. Genre choices
  intersect. Page changes make one read request and no ranking operation.
  Missing community scores do not satisfy a positive score floor. The
  unfiltered complete feed is also bounded to its first 50 picks.
- `refresh` is a feed-writing operation: it never overlaps `sync`,
  `recommendation` or `more-recommendations` for the same profile.
- Every row carries `ranking_id`, the ranking its `fit_rank` comes from.
  Compare or sort `fit_rank` only between rows that share it.
- `fit_pool_size` differs by engine. The sequence model ranks thousands of
  titles and the heuristic a few hundred, and a fallback switches engines, so
  never compare `fit_top_percent` across engines. Show which engine ranked
  the pick next to the number.
- All three are `null` for sample or legacy results. Then show
  "Personal fit unavailable" and no number.
- MAL score stays a separate, clearly labelled figure. Never blend the two.
- Sort "Personal fit" by `fit_rank` ascending, with nulls last. Rename the
  "Match" sort label.

### Inspector: personal rank, without explanations (D-023)

PERSONAL FIT shows the API's personal rank, eligible population and answering
engine. Do not render "Why this pick", legacy `reason` strings, supporting
history titles, additive score parts or removal diagnostics.

New recommendations have `why: null` for both engines, including heuristic
fallback. The nullable field and legacy evidence-artwork endpoint remain for
saved-feed compatibility; the web client does not request evidence artwork.
Old saved explanations still deserialize but are not displayed.

### Likes and dislikes (D-013, revised by D-015)

**No vote controls on Discover cards or in the inspector.** D-015 moves
feedback to the Library, after watching. The Library-side reporting and the
observed-on-return path are later work. The endpoint below stays, and so do
the votes already collected under D-013.

The backend collects votes. They do not change recommendations yet, so the UI
must not say or imply that they do: no "we'll show you more like this".

- Send `POST /api/discover/feedback` with `{profile_id, mal_id, action:
  "sentiment", sentiment: "liked" | "disliked" | null, feed_id}`, where
  `feed_id` is the feed's `activity_feed_id`. `null` clears the vote. Without
  a matching `feed_id` the vote is still kept, but unattributed.
- Liking clears a dislike and the reverse. The response `state` carries
  `liked_mal_ids` and `disliked_mal_ids`.
- The server records the time. It records what was shown, and ignores the
  client's `genres` and `title`, only when the vote is attributed: the title is
  in the served feed and `feed_id` matches it. Otherwise the vote is stored as
  sent, unattributed. A later vote on the same title replaces the earlier
  record, including its attribution.
- A dislike is not "Not interested". To remove the title from the feed, also
  send the existing `action: "hidden"`. They are separate decisions.

### Cost and states

Discover rebuilds do not generate explanations. A successful sequence rebuild
performs its ranking inference without counterfactual/removal calls. Opening
the Inspector does not generate explanations or fetch explanation artwork.
