# Backend handoff — open items from the 1.3.0 frontend work

Written 2026-08-26 during the frontend score-inspector redesign. No backend,
service, scoring, API, persistence, or release code was changed as part of this
work.

## P0 — the percentage is not behaving like a percentage

In the live connected product, the first visible recommendations scored about
27%, 25%, and 24%. The UI receives these values as `match_score` and labels them
"Personal match" with a percent sign.

For a user, 27% means "poor fit." If 27 is a strong result on the model's actual
scale, the output must be calibrated before it is exposed as a percentage. If
27 really means a weak result, the ranking/pool should not present it as the
first recommendation without an explicit low-confidence state.

Questions for the scoring owner:

- What is the theoretical and observed distribution of `match_score`?
- Is 100 reachable, or merely a cosmetic ceiling?
- Should scores be percentile-normalized within the candidate pool?
- What minimum score should trigger "we need more taste data" instead of a
  recommendation?
- Can the API return a confidence/coverage value separately from affinity?

The landing demonstration currently uses scores around 90%. Do not change the
frontend to fabricate those values for real data.

## P0 — contribution taxonomy is mixed

The field is named `genre_contributions`, but live values included:

- a genre/tag (`Samurai`);
- a studio (`Studio Deen`);
- `Other tags`;
- `Community rating`;
- `Similar viewers`.

The frontend now calls these **score contributors**, but retains the existing
field and values for compatibility. The backend contract should eventually use
a typed structure such as:

```text
ScoreContribution(label, value, kind)
kind = genre | theme | studio | source | community | collaborative | other
```

This would let the UI colour and explain signals without inferring their type
from display text.

## P1 — enforce the sum invariant at the service boundary

The product promise is that contributors add up to the displayed score. The
live example did add up within rounding tolerance, which is good, but this
should be a backend invariant rather than a frontend assumption.

Recommended contract:

```text
abs(sum(contribution.value) - match_score) <= 0.01
```

If normalization or display rounding makes that impossible, return both the
raw total and the calibrated display score, plus a documented relationship
between them. Never silently send a breakdown that does not reconcile.

## P1 — weak-result and low-data states

The UI needs an explicit state when the model lacks enough evidence. A low score
is not the same thing as a confident negative recommendation. Suggested output
fields:

- `confidence` or `evidence_coverage`;
- number of useful rated/completed titles;
- whether the score is below the recommended display threshold;
- a short machine-readable reason such as `sparse_history`, `narrow_pool`, or
  `cold_start`.

This lets the frontend say "AniRec needs more history" instead of confidently
presenting a 22% match.

## P1 — normalize signal labels

Live explanations mixed genres, studios, themes, and source media in one
sentence. That is acceptable as a scoring model, but the labels need stable
human-readable casing and categories. In particular, raw values such as
`novel` should not appear beside named studios as if they were the same type.

Please normalize labels before persistence/output and keep the raw source value
separately if it is needed for debugging.

## P2 — cover delivery and placeholder flash

The detail view briefly displayed the full-size placeholder before the cached
cover arrived. The frontend can crossfade the result, but the cover service
should confirm:

- memory/disk cache hits are returned synchronously where possible;
- the detail request reuses card-sized cache data until the large image lands;
- failed requests have a retry/backoff state distinct from "no cover exists";
- cached files are decoded off the UI thread.

## Release/operations blocker

The landing page identifies itself as `MODEL 1.3.0`, while the public GitHub
"Latest" release is v1.2.2. The landing CTA points to the generic releases
index, so a visitor cannot download the experience being advertised.

Before publishing the landing page:

1. Tag and package the exact reviewed 1.3.0 frontend.
2. Attach a stable Windows x64 asset with a predictable filename.
3. Point the CTA to that asset or to `/releases/latest`, not the release index.
4. Publish the SHA-256 beside the CTA.
5. Keep the unsigned-build/SmartScreen warning visible before download.
6. Verify the sample-library path in the packaged build on a clean Windows
   account.

This is a release-truth issue, not a cosmetic frontend issue.
