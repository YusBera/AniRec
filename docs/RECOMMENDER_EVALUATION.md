# Recommender Evaluation

Originally measured 2026-09-20 and corrected with the durable AniRecTrainer
evidence gate on 2026-09-21. Read this before changing ranking, candidate
generation, or the selection policy.

All figures are on split `56534d1a96`, test, n=31,902, through the `AniRecTrainer`
evaluation harness: exact full-catalogue ranking over 30,540 items, pessimistic
tie-breaking. "Served" is what a reader actually receives, because both engines
select 10 uniformly from the top 75, so served = R@75 x 10/75.

| Model | R@10 | +/-SE | novel | R@75 | served | cov@10 |
| --- | --- | --- | --- | --- | --- | --- |
| Popularity | 0.0304 | 0.0010 | 0.0334 | | | 437 |
| Heuristic, full catalogue (historical, not reproducible) | 0.0248 | 0.0009 | 0.0078 | 0.0735 | 0.0098 | 9,145 |
| Heuristic, shipped top-list pool (historical, not reproducible) | 0.0359 | 0.0010 | 0.0121 | 0.1150 | 0.0153 | 501 |
| EASE | 0.1055 | 0.0017 | 0.0458 | | | 5,634 |
| Recent transitions | 0.1385 | 0.0019 | 0.0756 | 0.3439 | 0.0459 | 7,952 |
| Sequence model (SASRec) | 0.2448 | 0.0024 | 0.1778 | 0.5338 | 0.0712 | 6,265 |
| Sequence model + franchise exclusion | 0.2226 | 0.0023 | 0.1808 | 0.4957 | 0.0661 | 6,243 |

The heuristic rows were produced by a session-temporary vectorised evaluator.
That evaluator, the exact candidate IDs and the public score/rank inputs were not
retained. The current evidence gate cannot regenerate the rows or the stated
22,142 missing targets, so both remain historical claims and are not used to
select an architecture. MAL popularity is not a substitute for score rank.

## Goal 4: chronological model decision (2026-09-24)

The newer, larger evidence, from the 22 September snapshot. The rules were
fixed before any SASRec result existed. The records are in `AniRecTrainer`:
- the rules: `reports/GOAL4_DECISION_PROTOCOL_23SEP.md`;
- the verdict and diagnostics: `reports/GOAL4_DECISION_RECORD_24SEP.md`;
- the analysis that applied them: `scripts/goal4_analysis.py`.

Split `9c8f337435`: train before 1 August, validation August, test 1-16
September, 48,668 test users, 30,282 candidate items, pessimistic ties.

| Model | Test R@10 (3 seeds) |
| --- | ---: |
| SASRec d256 reference (patience 3) | 0.2685 +/- 0.0029 |
| SASRec d256 patience 6 | 0.2679 +/- 0.0016 |
| recent transitions | 0.1358 |
| EASE (lambda at the edge of its search range) | 0.1111 |
| popularity | 0.0406 |

- **Decision: the reference config stays.** Patience 6 is statistically
  indistinguishable. McNemar on paired per-user hits gives p > 0.2 for every
  matched seed, the seeds disagree on direction, and the mean delta is -0.0007.
  No cohort, including history length, moves more than 1.4%.
- The baseline rows were not measured blind; the protocol discloses why. The
  sequence model's roughly twofold margin over them is not in doubt.
- About 1 test target in 10 is outside what AniRec's serving rules would show,
  so offline Recall@10 overstates what a served feed can reach.
- The model serving AniRec today was trained on the older snapshot, so it was
  not measured here. Replacing it is separate work: retrain, export, check
  PyTorch/ONNX agreement, and inspect real recommendations.

The 20 September measurements below remain valid for their own split.

## What this establishes

**Candidate generation was reported as a binding constraint.** The historical
top-list artifact needed to reproduce the 22,142 count was not saved. The current
reproducible serving-policy audit instead shows 1,727 of 31,902 targets
unreachable under the 22,210-item ONNX-safe catalogue, rising to 3,270 after the
verified direct-prerequisite rule.

**The historical heuristic run reported a pool-width drop, not its cause.** Its
reported Recall@10 fell from 0.0359 on the top-list pool to 0.0248 on 30,540
scorable items, but the evaluator, exact candidates and inputs were not retained.
A separate code audit found that the old content cosine applied IDF on both the
user and candidate sides; that defect was corrected on 2026-09-22. The missing
artifact means the rarity defect cannot be claimed as the cause of the historical
drop, and the correction cannot be claimed as a quality lift until a retained
rerun measures both candidate populations.

**The historical ablation questioned heuristic personalisation but is not
reproducible evidence.** It reported content-only 0.0296, community-only 0.0344
and the shipped blend 0.0359 on the same split. These values may motivate a new
retained ablation, but they do not establish the current heuristic's quality and
must not select the next architecture.

**The selection policy costs more than the engine gap.** Served over
deterministic is 0.43 for the heuristic, 0.33 for recent transitions, 0.30 for the
sequence model. It costs the better ranker more, because discarding rank order
only hurts when rank order carries information.

**The franchise exclusion is cheaper than previously estimated.** An earlier
analysis put it near 50%; measured, it is -9.1%, and it makes 6.2% of targets
unreachable. The production rule only withholds sequels of the reader's top 40
positively rated titles, not all continuations.

## What this does not establish

The harness measures whether the next item a reader logged appears in the
returned set. It is the right proxy and it is what every model here was judged
on, but it does not measure satisfaction, and it does not penalise a feed of ten
near-identical titles.

The exact-timestamp diagnostic has now run on all three recorded SASRec seeds.
Only 1,080 of 31,902 final model inputs contain an exact tie; mean Recall@10 moved
from 0.244123 to 0.244185 (+0.000063), with zero rank changes in the no-tie
cohort. Exact ties therefore do not explain the model's overall margin. This does
not establish viewing chronology and does not test same-day bulk edits with
different exact timestamps.

The reproducible corrected-split table is: popularity 0.0304, recent transitions
0.1385, EASE 0.1055 and SASRec d256 patience-6 three-seed mean 0.2441 ± 0.0015
Recall@10. Still outstanding: a reproducible heuristic evaluator, a stronger
classical sequential/collaborative baseline, production-policy replay, and a
later untouched confirmation window.

## Related

`docs/DECISIONS.md` D-006, D-007, D-008. `docs/ONNX_MODEL_SERVING.md` for the
bundle contract. `docs/archive/BACKEND_HANDOFF.md` for the open contract items,
some of which this evaluation has now answered.
