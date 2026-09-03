# Features for after the neural recommender ships

Written 2026-09-02, while the training corpus was still being collected. This
file exists so that work which only becomes possible once the model is live is
not lost between now and then, and so that the pieces which must be built
*before* launch are recognised as such.

The ordering matters: the first item cannot be added retroactively.

---

## P0 — Impression logging

### What already exists

`RecommendationFeedback` in `services/recommendation_state_service.py` records
explicit per-title sentiment (liked / disliked, being renamed to
not-interested), plus `hidden_mal_ids`. It is keyed one record per MAL id, and
persisted **profile-locally** through `JsonStore` under `profile_dir`.

That is a real signal and it already feeds the heuristic engine. It is not
sufficient for training a model, for three reasons.

### What is missing

**Implicit negatives.** Explicit feedback only exists where a user bothered to
click. The overwhelming majority of recommendations are shown, ignored, and
leave no trace. That silence is the most abundant signal there is, and the
training corpus has no equivalent: `plan_to_watch` is not a negative, and an
item absent from a list may be unwatched or merely unknown. An impression that
was displayed and not acted on is the first genuine "offered and refused."

**Attribution.** Sentiment is stored per title, not per recommendation event.
There is no record of which model version produced the suggestion, what rank it
appeared at, or what score it carried. Without rank, click data cannot be
debiased for position — items at the top get chosen because they are at the top.
Without model version, two releases cannot be compared at all.

**A path off the machine.** Profile-local storage means the signal never reaches
training. That is the correct default for privacy, but it does mean an upload
path has to be designed rather than assumed.

### What to record

One row per recommendation *impression*, not per session, because the useful
comparison is between the item shown and the items shown beside it.

| Field | Why |
|---|---|
| `impression_id` | Groups the items shown together in one batch |
| `shown_at` | Ordering, and lets stale impressions be discarded |
| `anime_id` | The item |
| `rank` | Position in the list. Position bias is strong; without rank, click data cannot be debiased |
| `model_version` | Which release produced it. Without this, feedback cannot be attributed and A/B comparison is impossible |
| `score` | The model's own score, so calibration can be checked against outcomes |
| `outcome` | See below |
| `outcome_at` | Time to act, which separates "obvious yes" from "thought about it" |

### Outcomes worth distinguishing

- `shown` — displayed and neither acted on nor dismissed. **The default, and the
  most numerous.** This is the implicit negative the corpus completely lacks
  today, and the reason to log impressions rather than only clicks.
- `opened` — the user opened the detail view. Interest without commitment.
- `added` — added to their list. The strong positive.
- `dismissed` — explicitly rejected. A much stronger negative than `shown`. This
  is where the existing not-interested control already fits; it needs the
  impression context attached rather than replacing.
- `already_seen` — the user has watched it but it was not in the list AniRec
  read. Tells you the exclusion filter failed, which is a bug signal, not taste.

Existing sentiment records should be kept as they are and joined to impressions
by `anime_id`, not folded into them. They answer different questions: sentiment
is a durable statement about a title, an impression is one event.

### Why this changes the model, not just the metrics

The corpus models *MAL's population*. Feedback models *your users*, who are a
different and self-selected group. The two will disagree, and where they
disagree the feedback is right about the product.

### Constraints

- The desktop app is the only place this can be observed, so it has to be
  logged locally and uploaded, or it does not exist.
- Uploading requires consent, and the pipeline is pseudonymous by design.
  Feedback should carry the same keyed-HMAC pseudonym as the training corpus, or
  a separate per-install identifier — never a MAL username.
- A user who declines telemetry must still get recommendations. This is an
  improvement loop, not a licence check.
- Log locally first, upload in batches. A user offline for a week should lose
  nothing.

---

## P1 — Recommendation staleness and rotation

The user tower recomputes a vector from current history, so recommendations move
when the user's list moves. A user who watches nothing for a month gets the same
list every time they open the app.

Options: rotate within a candidate band rather than always showing the global
top-N, decay items already shown several times without action (the `shown` count
above gives this for free), or surface newly aired titles preferentially, which
is the one case where the catalogue changed even though the user did not.

Depends on impression logging existing.

---

## P1 — New-release handling in the UI

Product rule already decided: never recommend an unaired title. A currently
airing one may be recommended, shown with episodes released so far and expected
end date, and a user setting restricts recommendations to finished shows only.

Needs `airing_status`, `episodes` and `end_date` from the model bundle's index.
`airing_status` was wrong on 30,428 of 30,429 rows until 2026-09-02 and
`end_date` is 38.8% populated, so verify both before building UI on them.

---

## P2 — Explaining a learned recommendation

The heuristic engine could say "you like action and this is action." A two-tower
model cannot: the score is a dot product in a learned space. Users trust what
they understand, and 1.3.0 already invested in explanation.

Approximations available without extra data: nearest neighbours among titles the
user rated highly ("because you liked X"), franchise relations once sequel edges
are populated, and shared studio or staff. None is the real reason, and the copy
should not claim otherwise.

---

## P2 — Continuous catalogue refresh

Roughly 1,200 new anime a year, about 100 a month. The model does not need
retraining to recommend them — `item_encoder.onnx` embeds a new title from its
metadata alone — but the metadata has to arrive from somewhere.

This is the only thing that must run continuously for the product to keep
working. User-list scraping, by contrast, is training input and only needs to
run when a retrain is planned.

---

## P3 — Retraining cadence

Not urgent and not automatic. What ages is the learned mapping, on a scale of
years. What forces a retrain sooner is feature vocabulary drift: 2,074 distinct
studio combinations today, and a studio the model never saw is out of
vocabulary.

Expect every 6–12 months, triggered by measured degradation rather than a
calendar. Once feedback logging exists, degradation is observable directly —
falling add rate at fixed rank is the signal to watch.
