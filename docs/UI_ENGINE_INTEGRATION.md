# Latest UI and v3 engine integration

Verified on 20 September 2026. This clone combines GitHub UI branch
`codex/library-led-workspace-handoff` at `82f7cbd` with the local v3 ONNX
serving and recommendation activity changes. Integration branch:
`codex/ui-v3-engine`. Changes are local and uncommitted.

The original sibling AniRec checkout and its uncommitted work were preserved.
This clone is under `AniRecTrainer/work/anirec-ui`; `work` is ignored by the
parent Trainer repository, so integration changes belong to this clone's Git
repository.

## Launch locally

From this clone's root, in a PowerShell terminal:

```powershell
$env:ANIREC_MODEL_BUNDLE = 'C:\Users\yusuf\AniRecTrainerWork\exports\sasrec-typed-d256-p6-seed2-split56534d1a96-v3'
& 'C:\Users\yusuf\OneDrive\Desktop\projects\AniRec\.venv\Scripts\python.exe' -B -m AniRec.api --port 8770
```

In another terminal, from this clone's `frontend` directory:

```powershell
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

Open <http://127.0.0.1:5173/>. The API uses AniRec's existing local profile and
data directory. The interpreter currently comes from the original checkout's
virtual environment. Both servers bind to loopback. Stop an existing preview
before starting another instance.

## Verified behavior

- Generated API schema verification, TypeScript checks, 61 frontend tests and
  production build passed.
- 66 targeted Python tests passed across workspace API, ONNX engine, pipeline,
  API boundary, activity events and user data.
- Real ONNX inspection in this clone ranked 22,210 eligible candidates with no
  fallback (about 20 ms inference for the inspected history).
- Discover, My Library and Settings load with the existing local profile.
- Discover activity does not record hidden Discover cards while another
  workspace page is active. Library interactions are not attributed to
  Discover impressions.

The initial Discover feed is saved output from the previous heuristic engine.
Launching with a model bundle does not regenerate or relabel saved results.
The ONNX inspection used an anonymous evaluation history; fresh generation
with the active personal profile still needs to be checked separately.
Recommendation activity remains opt-in and local-only.

See `ONNX_MODEL_SERVING.md` for model selection and fallback semantics and
`RECOMMENDATION_ACTIVITY.md` for logging behavior. UI refinement remains
deferred.

---

## UI contract: personal fit and "why" (Goal 2)

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
- A feed and its "more" batches share one ranking, so their `fit_rank` values
  are unique and comparable. "More" continues exactly the ranking the feed was
  generated from. Hiding or restoring titles in between changes only what can
  be selected: a restored title returns at the next full generation. If the
  ranking inputs changed since (a MAL sync, different feedback, a changed
  "Include NSFW anime" or minimum MAL score setting, rebuilt candidates or
  taste profile, or a different engine or catalogue), the "more" operation
  fails with a message containing "Generate a new feed". Offer that action;
  never mix two rankings in one feed. A new full generation starts a new
  ranking.
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

### Clicking it: `why` (an `Explanation`)

Branch on `why.method`. If `why` is `null`, render it the same as `unavailable`.

**`exact-additive` (heuristic): an additive bar.**
- `segments[].value` sums to `total`, the ranking score, to within one float
  rounding step. Negative parts offset positive ones, so a positive part can
  exceed `total`. Draw bar lengths proportional to `|value|`, with positive
  parts ("raised it") and negative parts ("held it back") on separate sides.
  Never present a part as a percentage of `total`, and never drop negatives.
- `kind: "taste"` parts come from the reader's own ratings. `facet` is one of
  genre, studio, source, media-type or era; label the segment with its facet.
  On click, show:
  - `taste.rated_count` rated titles with this facet, averaging
    `taste.mean_user_score` against the reader's overall
    `taste.overall_mean_user_score`;
  - the `evidence` titles with their `user_score`, the reader's real ratings;
  - `feedback_adjustment`, if non-null, as "adjusted by your likes/dislikes".
- `taste.affinity` is the value the ranking used, after any feedback. When
  `feedback_adjustment` is set, do not describe it as coming from ratings
  alone. `rated_count` and `mean_user_score` are null when the reader's rated
  list was unavailable: say "unknown", not zero.
- `kind: "community"` is the MAL community rating and `kind: "similar-viewers"`
  is the recommendation graph. Label both as not about the reader's taste.
  - If `signal_available` is `false`, there was no data and a neutral stand-in
    was used. Say so.
  - `community.mean_score` and `community.scoring_users` are the MAL figures.

**`counterfactual-removal` (sequence model): a relative-impact bar, not shares.**
- The model was rerun without parts of the reader's history. `total` and
  `baseline` are `null` because the effects overlap and do not add up. Never
  render these segments as slices of a whole or as percentages of the score.
- Each segment is the reader's history titles in one genre. `member_count`
  gives how many; `kind: "history-other"` covers titles without genres.
  - Wording must be "your *Psychological* titles", never "because it is
    Psychological". The model never sees genres.
  - `value` is the model-score drop without those titles; bar length can be
    proportional to `|value|`.
  - `rank_without` is the pick's rank without them. Show it as
    "#`full_rank` → #`rank_without`".
  - Negative `value` means those titles held the pick back.
- On click, list the segment's `evidence` titles. Each has its own
  single-title `value` and `rank_without`, plus `list_status` and `user_score`.
- `influences` are the strongest single titles overall: "Because you watched
  *X*: without it, #4 → #337". Use `list_status` for the verb: watched,
  dropped, plan to watch, and so on.
- `history_window` is how many recent list entries the model reads, up to 200.
  Say "from your N most recent titles". Never say the whole list. A removal
  takes titles out of that window; it does not pull older titles in.
- If a segment's `member_count` equals `history_window`, removing it leaves no
  history, and `rank_without` is the rank for a brand-new reader. Say so.
- Group and single-title effects interact. A genre segment can be negative
  while each of its titles, removed alone, is positive. Show the numbers as
  they are, and never infer one from the other.
- `full_rank` and `ranked_candidate_count` are the same rank as `fit_rank` and
  `fit_pool_size`.

**`unavailable`:** show "This pick can't be explained" plus `unavailable_reason`,
mapped to plain text:
- `engine-cannot-explain` → "this engine can't explain its picks";
- `explanation-failed` and `explanation-unavailable` → "couldn't compute an
  explanation this time";
- `outside-ranked-candidates` → "not in the ranked set";
- `score-parts-missing` → "no score breakdown was recorded".

Never substitute another engine's explanation.

### Cost and states

Sequence-model explanations are computed at generation, adding about 4 s for a
200-title history, so opening one needs no request. A failed explanation never
removes the recommendation; it arrives as `unavailable`.
