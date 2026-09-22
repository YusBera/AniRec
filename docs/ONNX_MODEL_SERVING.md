# ONNX sequence-model serving

AniRec uses the heuristic ranker unless `ANIREC_MODEL_BUNDLE` points to a
verified bundle. The current serving contract is bundle version 3.

```powershell
$env:ANIREC_MODEL_BUNDLE = 'C:\path\to\sasrec-bundle-v3'
python -m AniRec.main
```

The bundle must contain `model.onnx`, `items.npy`, `candidate_mask.npy`,
`catalog.json`, `prerequisites.npz`, and `manifest.json`. AniRec verifies every
file hash, catalogue alignment, and the recorded PyTorch/ONNX parity result
before creating an ONNX Runtime CPU session. Any missing dependency, invalid
history, incompatible bundle, or runtime failure routes the request through
the existing heuristic engine and records that fallback in the ranking
metadata. The fallback receives the same frozen candidate population.

The sequence input is the user's full current MAL list ordered by MAL update
time, with equal timestamps ordered by MAL anime ID to match training. The
model excludes every title already on the list and every title outside the
frozen candidate mask. The version 3 serving catalogue excludes entries with
no exact release date, entries whose release is later than the pipeline run,
and titles marked not yet aired. R+ and Rx entries are excluded unless the
user enables NSFW results. Candidate metadata stays aligned to the verified
bundle rather than being replaced by a per-run ranking-list overlay.

A later-released title with a reciprocal MAL prequel/sequel relation is
eligible only when at least one direct prequel is a completed title or an
in-progress title with watched episodes. The release-order check avoids
treating later-produced story prequels as required viewing.

The bundle exposes its catalogue mask, public metadata and prerequisite mapping
to `FinalEligibilityPolicy`. That policy filters both the sequence-model pool
and the heuristic fallback pool before either scorer runs. Catalogue policy
loading is independent of ONNX Runtime startup, so an inference failure cannot
silently remove these protections from fallback output.

The pipeline persists the exact population to `candidate_catalogue.csv` with
source `installed-model-catalogue` and does not call the MyAnimeList ranking
endpoint. When no usable bundle catalogue is installed, the compatibility source
is explicitly recorded as `mal-ranking-legacy`; it is not presented as owned
data. An installed catalogue that is valid but contains zero eligible rows fails
closed and never switches sources silently.

Raw model logits are retained for diagnostics and are never displayed as match
percentages. Personal fit is the pick's rank among the eligible candidates.
Each served row is explained by counterfactual removal: the model is rerun,
batch size one, without each genre group of the reader's input history and
without each single input title, and the pick's score drop and rank are
measured among the same candidates. This covers only the most recent titles
the model reads (`history_window`). A failure yields an "unavailable"
explanation, never a lost feed. Recommendation activity remains opt-in and local-only; new results
store the actual ranking engine ID and version with each event.

The verified 20 September 2026 bundle contains 30,540 model items. Its normal
safe serving view contains 22,210 released, dated, candidate-mask-eligible
titles as of that date; enabling NSFW results raises that view to 24,955. The
configured `top_anime_limit` controls only the legacy no-bundle compatibility
source. It does not limit a configured bundle's candidate population.
