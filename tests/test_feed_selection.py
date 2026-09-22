"""Deterministic, diverse feed selection through the shipped entry points.

Every test here runs ``RecommendationService.recommend`` or the pipeline with
the real heuristic or ONNX engine and the real shared selector. Nothing in the
selection path is mocked; spies only count calls to the real function.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import date

import numpy as np
import pandas as pd
import pytest

import services.recommendation_service as service_module
from models import PipelineSettings
from services import RecommendationService
import recommendation_system
from recommendation_system import rank_candidate_pool
from scoring.engines import (
    FallbackRankingEngine,
    HeuristicRankingEngine,
    OnnxSequenceRankingEngine,
)
from scoring.selection import select_feed


AS_OF = date(2026, 9, 20)
PROFILE = pd.DataFrame(
    [
        {"Genre": "Action", "Importance_Score": 100.0},
        {"Genre": "Drama", "Importance_Score": 40.0},
    ]
)


# --- ONNX fixture ---------------------------------------------------------


class FakeSession:
    def __init__(self, logits):
        self.logits = np.asarray([logits], dtype=np.float32)

    def run(self, _outputs, _feeds):
        return [self.logits]


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _catalog_row(anime_id, **overrides):
    row = {
        "anime_id": anime_id,
        "title": f"Title {anime_id:03d}",
        "start_date": "2020-01-01",
        "airing_status": "Finished Airing",
        "content_rating": "PG-13 - Teens 13 or older",
        "genres": ["Action"],
        "studios": ["Studio A"],
        "source": "Manga",
        "media_type": "tv",
    }
    row.update(overrides)
    return row


def _bundle(tmp_path, catalog, prerequisites=()):
    bundle = tmp_path / "bundle"
    bundle.mkdir(parents=True)
    items = [row["anime_id"] for row in catalog]
    np.save(bundle / "items.npy", np.asarray(items, dtype=np.int32))
    np.save(bundle / "candidate_mask.npy", np.ones(len(items), dtype=bool))
    (bundle / "catalog.json").write_text(json.dumps(catalog), encoding="utf-8")
    np.savez(
        bundle / "prerequisites.npz",
        candidate=np.asarray([c for c, _p in prerequisites], dtype=np.int32),
        prequel=np.asarray([p for _c, p in prerequisites], dtype=np.int32),
    )
    (bundle / "model.onnx").write_bytes(b"fixture graph")
    files = {
        name: {"sha256": _sha256(bundle / name)}
        for name in (
            "items.npy",
            "candidate_mask.npy",
            "catalog.json",
            "prerequisites.npz",
            "model.onnx",
        )
    }
    (bundle / "manifest.json").write_text(
        json.dumps(
            {
                "bundle_version": 3,
                "format": "onnx",
                "checkpoint": {"sha256": "abcdef1234567890"},
                "data": {"n_items": len(items)},
                "model": {"maxlen": 4},
                "contract": {"sequence_length": 4},
                "parity": {"parity_pass": True},
                "files": files,
            }
        ),
        encoding="utf-8",
    )
    return bundle


HISTORY = pd.DataFrame(
    [
        {
            "Anime ID": 1,
            "Status": "completed",
            "User Score": 8,
            "Episodes Watched": 12,
            "Is Rewatching": False,
            "Updated At": "2026-09-01T10:00:00+00:00",
        }
    ]
)


def _onnx_feed(tmp_path, catalog, logits, *, count, adventurousness, reverse=False):
    """Serve a feed through the ONNX engine and the real service."""
    engine = OnnxSequenceRankingEngine(
        _bundle(tmp_path, catalog), session_factory=lambda _path: FakeSession(logits)
    )
    service = RecommendationService(ranker=engine)
    candidates = service.candidate_catalog(as_of=AS_OF)
    if reverse:
        candidates = candidates.iloc[::-1].reset_index(drop=True)
    return service.recommend(
        candidates,
        PROFILE,
        PipelineSettings(
            recommendation_count=count,
            candidate_pool_size=max(count, len(catalog)),
            top_anime_limit=max(count, len(catalog)),
            randomness_factor=adventurousness,
        ),
        user_history=HISTORY,
        consumed_mal_ids={1},
        as_of=AS_OF,
    )


def _ids(frame):
    return [int(value) for value in frame["Anime ID"]]


def _model_rank(row):
    match = re.search(r"candidate rank (\d+)", row["Recommendation Reason"])
    return int(match.group(1))


def _clone_catalog(size, outliers=None):
    """Watched item 1, then ``size`` near-identical titles 2..size+1."""
    catalog = [_catalog_row(1)]
    for anime_id in range(2, size + 2):
        catalog.append(_catalog_row(anime_id, **(outliers or {}).get(anime_id, {})))
    return catalog


def _descending_logits(size):
    # Item 1 is watched; items 2.. score strictly descending.
    return [0.0] + [10.0 - index * 0.1 for index in range(size)]


# --- heuristic fixture ------------------------------------------------------


def _heuristic_candidates():
    rows = []
    studios = ["Madhouse", "Bones", "MAPPA", "Sunrise"]
    sources = ["Manga", "Original", "Light novel"]
    types = ["tv", "movie"]
    for index in range(30):
        second = ["Drama", "Comedy", "Mystery", "Romance", "Sports"][index % 5]
        rows.append(
            {
                "Anime ID": 100 + index,
                "Title": f"Heuristic {index:02d}",
                "Genres": ["Action", second] if index % 3 else ["Action"],
                "Studios": [studios[index % 4]] if index % 7 else [],
                "Source": sources[index % 3],
                "Media Type": types[index % 2],
                "Mean Score": 9.0 - (index % 10) * 0.1,
                "Scoring Users": 1000 + index,
            }
        )
    return pd.DataFrame(rows)


def _heuristic_feed(candidates, *, count=10, adventurousness=5, seed=None):
    return RecommendationService().recommend(
        candidates,
        PROFILE,
        PipelineSettings(
            recommendation_count=count,
            candidate_pool_size=max(count, len(candidates)),
            top_anime_limit=max(count, len(candidates)),
            randomness_factor=adventurousness,
            seed=seed,
        ),
    )


def _heuristic_pool(candidates):
    return rank_candidate_pool(
        candidates,
        PROFILE,
        num_recommendations=10,
        top_anime_count=len(candidates),
    )


# --- determinism ------------------------------------------------------------


@pytest.mark.parametrize("adventurousness", [1, 5, 10])
def test_identical_inputs_and_any_seed_produce_the_same_ordered_feed(adventurousness):
    candidates = _heuristic_candidates()
    feeds = [
        _ids(_heuristic_feed(candidates, adventurousness=adventurousness, seed=seed))
        for seed in (None, None, 1, 42, 999_999)
    ]

    assert all(feed == feeds[0] for feed in feeds)
    assert len(feeds[0]) == 10


def test_candidate_input_order_does_not_change_the_feed(tmp_path):
    candidates = _heuristic_candidates()
    reversed_rows = candidates.iloc[::-1].reset_index(drop=True)

    assert _ids(_heuristic_feed(candidates, adventurousness=10)) == _ids(
        _heuristic_feed(reversed_rows, adventurousness=10)
    )

    catalog = _clone_catalog(12, {5: {"genres": ["Romance"], "studios": ["B"]}})
    logits = _descending_logits(12)
    forward = _onnx_feed(tmp_path / "a", catalog, logits, count=4, adventurousness=10)
    backward = _onnx_feed(
        tmp_path / "b", catalog, logits, count=4, adventurousness=10, reverse=True
    )
    assert _ids(forward) == _ids(backward)


_CROSS_PROCESS_SCRIPT = r"""
import json, sys
sys.path.insert(0, sys.argv[1])
import pandas as pd
from services import RecommendationService
from models import PipelineSettings
rows = json.loads(sys.argv[2])
feed = RecommendationService().recommend(
    pd.DataFrame(rows),
    pd.DataFrame([{"Genre": "Action", "Importance_Score": 100.0},
                  {"Genre": "Drama", "Importance_Score": 40.0}]),
    PipelineSettings(recommendation_count=10, candidate_pool_size=len(rows),
                     top_anime_limit=len(rows), randomness_factor=10),
)
print(json.dumps([int(v) for v in feed["Anime ID"]]))
"""


def test_feed_is_identical_across_python_processes_and_hash_seeds(repo_root):
    candidates = _heuristic_candidates()
    # CSV-encoded labels, as "more" and single-step read them back from disk.
    records = [
        {**row, "Genres": str(row["Genres"]), "Studios": str(row["Studios"])}
        for row in candidates.to_dict("records")
    ]
    in_process = _ids(_heuristic_feed(pd.DataFrame(records), adventurousness=10))

    outputs = []
    for hash_seed in ("0", "1", "12345"):
        environment = {**os.environ, "PYTHONHASHSEED": hash_seed}
        completed = subprocess.run(
            [
                sys.executable,
                "-c",
                _CROSS_PROCESS_SCRIPT,
                str(repo_root / "AniRec"),
                json.dumps(records),
            ],
            capture_output=True,
            text=True,
            env=environment,
            check=True,
        )
        outputs.append(json.loads(completed.stdout.strip().splitlines()[-1]))

    assert all(output == in_process for output in outputs)


# --- ranking preservation -----------------------------------------------------


@pytest.mark.parametrize("adventurousness", range(1, 11))
def test_strongest_ranked_title_is_always_served(tmp_path, adventurousness):
    candidates = _heuristic_candidates()
    top = int(_heuristic_pool(candidates).iloc[0]["Anime ID"])
    heuristic = _heuristic_feed(candidates, adventurousness=adventurousness)
    assert _ids(heuristic)[0] == top

    # The top model title is a clone of everything below it; it still leads.
    catalog = _clone_catalog(
        15, {anime_id: {"genres": ["Romance"], "studios": ["Other"],
                        "source": "Original", "media_type": "movie"}
             for anime_id in range(3, 17)}
    )
    feed = _onnx_feed(
        tmp_path, catalog, _descending_logits(15), count=5,
        adventurousness=adventurousness,
    )
    assert _ids(feed)[0] == 2


def test_lowest_adventurousness_serves_exactly_the_top_of_the_ranking(tmp_path):
    candidates = _heuristic_candidates()
    pool_ids = _ids(_heuristic_pool(candidates))

    assert _ids(_heuristic_feed(candidates, adventurousness=1)) == pool_ids[:10]

    catalog = _clone_catalog(12, {9: {"genres": ["Romance"], "studios": ["B"]}})
    feed = _onnx_feed(tmp_path, catalog, _descending_logits(12), count=4,
                      adventurousness=1)
    assert _ids(feed) == [2, 3, 4, 5]


def test_high_adventurousness_adds_verified_variety_near_the_top(tmp_path):
    distinct = {"genres": ["Romance", "Slice of Life"], "studios": ["Studio B"],
                "source": "Original", "media_type": "movie"}
    catalog = _clone_catalog(12, {8: distinct})
    logits = _descending_logits(12)

    cautious = _onnx_feed(tmp_path / "low", catalog, logits, count=4,
                          adventurousness=1)
    adventurous = _onnx_feed(tmp_path / "high", catalog, logits, count=4,
                             adventurousness=10)

    assert 8 not in _ids(cautious)
    assert _ids(adventurous) == [2, 3, 4, 8]
    assert adventurous["Studios"].map(tuple).nunique() == 2
    # Rows stay in model order, and each keeps its original model rank.
    assert [_model_rank(row) for _i, row in adventurous.iterrows()] == [1, 2, 3, 7]


def test_novelty_cannot_pull_a_title_from_beyond_the_bounded_window(tmp_path):
    distinct = {"genres": ["Romance"], "studios": ["Studio B"],
                "source": "Original", "media_type": "movie"}
    # count 3 + leap 18 = the top 21 model ranks; the outlier is rank 22.
    catalog = _clone_catalog(25, {23: distinct})
    feed = _onnx_feed(tmp_path, catalog, _descending_logits(25), count=3,
                      adventurousness=10)

    assert 23 not in _ids(feed)
    assert all(_model_rank(row) <= 21 for _i, row in feed.iterrows())


def test_every_adventurousness_level_is_deterministic_and_bounded(tmp_path):
    candidates = _heuristic_candidates()
    pool_ids = _ids(_heuristic_pool(candidates))
    for adventurousness in range(1, 11):
        first = _ids(_heuristic_feed(candidates, adventurousness=adventurousness))
        again = _ids(_heuristic_feed(candidates, adventurousness=adventurousness))
        window = 10 + 2 * (adventurousness - 1)
        assert first == again
        assert set(first) <= set(pool_ids[:window])
        assert first == sorted(first, key=pool_ids.index)


# --- diversity semantics ------------------------------------------------------


def test_sharing_one_genre_is_not_treated_as_duplication(tmp_path):
    seconds = ["Drama", "Comedy", "Mystery", "Romance", "Sports", "Horror",
               "Music", "Space", "Mecha", "School", "Psychological", "Fantasy"]
    catalog = [_catalog_row(1)] + [
        _catalog_row(anime_id, genres=["Action", seconds[anime_id - 2]],
                     studios=[f"Studio {anime_id}"])
        for anime_id in range(2, 14)
    ]
    feed = _onnx_feed(tmp_path, catalog, _descending_logits(12), count=5,
                      adventurousness=10)

    assert _ids(feed) == [2, 3, 4, 5, 6]


@pytest.mark.parametrize(
    ("column", "field", "values"),
    [
        ("Studios", "studios", (["Studio A"], ["Studio B"])),
        ("Source", "source", ("Manga", "Original")),
        ("Media Type", "media_type", ("tv", "movie")),
    ],
)
def test_one_repeated_facet_earns_a_small_bounded_lift(tmp_path, column, field, values):
    repeated, different = values

    def catalog(outlier_id):
        rows = [_catalog_row(1)]
        for anime_id in range(2, 14):
            row = _catalog_row(
                anime_id,
                genres=[f"Genre {anime_id}"],
                studios=[],
                source=None,
                media_type=None,
            )
            row[field] = different if anime_id == outlier_id else repeated
            rows.append(row)
        return rows

    near = _onnx_feed(tmp_path / "near", catalog(5), _descending_logits(12),
                      count=3, adventurousness=10)
    far = _onnx_feed(tmp_path / "far", catalog(10), _descending_logits(12),
                     count=3, adventurousness=10)

    # Rank 4 can overtake rank 2 on one differing facet; rank 9 cannot.
    assert _ids(near) == [2, 3, 5]
    assert _ids(far) == [2, 3, 4]
    assert column in near.columns


def test_missing_metadata_falls_back_to_rank_order(tmp_path):
    catalog = [_catalog_row(1)] + [
        _catalog_row(anime_id, genres=[], studios=[], source=None, media_type=None)
        for anime_id in range(2, 14)
    ]
    feed = _onnx_feed(tmp_path, catalog, _descending_logits(12), count=5,
                      adventurousness=10)
    assert _ids(feed) == [2, 3, 4, 5, 6]

    bare = pd.DataFrame(
        [
            {"Anime ID": 200 + index, "Title": f"Bare {index}", "Genres": None,
             "Mean Score": 9.0 - index * 0.1}
            for index in range(15)
        ]
    )
    pool_ids = _ids(_heuristic_pool(bare))
    assert _ids(_heuristic_feed(bare, count=5, adventurousness=10)) == pool_ids[:5]


def test_missing_metadata_never_earns_novelty_in_a_mixed_pool(tmp_path):
    bare = {"genres": [], "studios": [], "source": None, "media_type": None}
    lead = {"genres": ["Action", "Comedy"]}
    partial_overlap = {"genres": ["Action", "Drama"], "studios": ["Studio B"],
                       "source": "Original"}
    catalog = [_catalog_row(1)] + [
        _catalog_row(2, **lead),
        _catalog_row(3, **partial_overlap),
        _catalog_row(4, **lead),              # identical to rank 1
        _catalog_row(5, **bare),              # undescribed, inside the window
        *[_catalog_row(anime_id, **lead) for anime_id in range(6, 12)],
    ]
    feed = _onnx_feed(tmp_path / "bare", catalog, _descending_logits(10), count=3,
                      adventurousness=10)

    assert 5 not in _ids(feed)
    assert _ids(feed) == [2, 3, 4]

    # A row identical on every fact it carries is fully redundant, even when
    # its other facets are missing.
    genres_only = {"genres": ["Action", "Comedy"], "studios": [], "source": None,
                   "media_type": None}
    catalog = [_catalog_row(1)] + [
        _catalog_row(2, **lead),
        _catalog_row(3, **genres_only),
        *[_catalog_row(anime_id, **lead) for anime_id in range(4, 8)],
        _catalog_row(8, **partial_overlap),
        *[_catalog_row(anime_id, **lead) for anime_id in range(9, 12)],
    ]
    feed = _onnx_feed(tmp_path / "partial", catalog, _descending_logits(10),
                      count=2, adventurousness=10)
    assert _ids(feed) == [2, 8]


def test_csv_encoded_and_malformed_metadata_follow_the_production_parser():
    candidates = _heuristic_candidates()
    list_feed = _ids(_heuristic_feed(candidates, adventurousness=10))

    # The same rows after the CSV round trip "more" and single-step perform.
    import io

    buffer = io.StringIO()
    candidates.to_csv(buffer, index=False)
    buffer.seek(0)
    from_csv = pd.read_csv(buffer)
    assert isinstance(from_csv.loc[0, "Genres"], str)
    assert _ids(_heuristic_feed(from_csv, adventurousness=10)) == list_feed

    malformed = candidates.copy().astype(object)
    malformed.loc[1, "Studios"] = "['Madhouse'"          # truncated literal
    malformed.loc[2, "Studios"] = float("nan")
    malformed.loc[3, "Source"] = 5                        # unexpected scalar
    malformed.loc[4, "Media Type"] = "  TV  "
    malformed.loc[5, "Genres"] = "Action, Drama"          # plain CSV text
    malformed.loc[6, "Studios"] = pd.NA
    malformed.loc[7, "Media Type"] = "unknown"
    feed = _heuristic_feed(malformed, adventurousness=10)
    assert len(feed) == 10


def test_label_case_and_whitespace_are_one_label():
    rows = [
        {"Genres": "['Action']", "Studios": ["Madhouse"], "Source": "Manga"},
        {"Genres": ["action "], "Studios": "['  MADHOUSE']", "Source": " manga"},
        {"Genres": ["Romance"], "Studios": ["Bones"], "Source": "Original"},
    ]
    # The second row duplicates the first once labels are normalised, so a
    # leap of 18 lets the distinct third row take the second slot.
    assert select_feed(rows, 2, 10) == (0, 2)


def test_fewer_candidates_than_requested_returns_all_of_them(tmp_path):
    catalog = [_catalog_row(1), _catalog_row(2), _catalog_row(3, genres=["Drama"])]
    feed = _onnx_feed(tmp_path, catalog, [0.0, 0.5, 0.9], count=10,
                      adventurousness=10)
    assert _ids(feed) == [3, 2]

    candidates = _heuristic_candidates().head(4)
    assert len(_heuristic_feed(candidates, count=4, adventurousness=10)) == 4
    assert len(_heuristic_feed(candidates, count=10, adventurousness=10)) == 4


def test_exact_score_ties_use_the_existing_stable_tie_breakers(tmp_path):
    catalog = [_catalog_row(1)] + [_catalog_row(anime_id) for anime_id in range(2, 8)]
    logits = [0.0] + [1.0] * 6
    feed = _onnx_feed(tmp_path, catalog, logits, count=3, adventurousness=10)
    reverse = _onnx_feed(tmp_path / "r", catalog, logits, count=3,
                         adventurousness=10, reverse=True)

    # Equal logits and unavailable community scores fall back to MAL ID.
    assert _ids(feed) == [2, 3, 4]
    assert _ids(reverse) == [2, 3, 4]


# --- one shared policy, applied once ----------------------------------------


@pytest.fixture
def selector_calls(monkeypatch):
    calls = []
    real = service_module.select_feed

    def counting(rows, count, adventurousness):
        calls.append((len(rows), count, adventurousness))
        return real(rows, count, adventurousness)

    monkeypatch.setattr(service_module, "select_feed", counting)
    legacy_calls = []
    legacy_real = recommendation_system.select_feed

    def legacy_counting(*args):
        legacy_calls.append(args)
        return legacy_real(*args)

    monkeypatch.setattr(recommendation_system, "select_feed", legacy_counting)
    return calls, legacy_calls


def test_heuristic_engine_output_is_selected_once_by_the_shared_policy(selector_calls):
    calls, legacy_calls = selector_calls
    candidates = _heuristic_candidates()

    feed = _heuristic_feed(candidates, adventurousness=7)

    assert calls == [(30, 10, 7)]
    assert legacy_calls == []
    assert feed.attrs["ranking_engine"].engine_id == "heuristic"


def test_onnx_engine_output_is_selected_once_by_the_shared_policy(
    tmp_path, selector_calls
):
    calls, legacy_calls = selector_calls

    feed = _onnx_feed(tmp_path, _clone_catalog(12), _descending_logits(12),
                      count=4, adventurousness=6)

    assert calls == [(12, 4, 6)]
    assert legacy_calls == []
    assert feed.attrs["ranking_engine"].engine_id == "sasrec-onnx"


def test_fallback_result_is_selected_exactly_once(tmp_path, selector_calls):
    calls, legacy_calls = selector_calls

    def unavailable(_path):
        raise RuntimeError("runtime unavailable")

    catalog = _clone_catalog(12, {8: {"genres": ["Romance"], "studios": ["B"],
                                      "source": "Original", "media_type": "movie"}})
    engine = FallbackRankingEngine(
        OnnxSequenceRankingEngine(_bundle(tmp_path, catalog), session_factory=unavailable),
        HeuristicRankingEngine(),
    )
    service = RecommendationService(ranker=engine)
    candidates = service.candidate_catalog(as_of=AS_OF)
    settings = PipelineSettings(recommendation_count=4, candidate_pool_size=12,
                                top_anime_limit=12, randomness_factor=10)

    feed = service.recommend(
        candidates, PROFILE, settings, user_history=HISTORY,
        fallback_candidates=candidates, consumed_mal_ids={1}, as_of=AS_OF,
    )

    assert feed.attrs["ranking_engine"].fallback_used
    assert feed.attrs["ranking_engine"].engine_id == "heuristic"
    assert len(calls) == 1
    assert legacy_calls == []
    assert len(feed) == 4


# --- eligibility, scores and explanations are untouched ------------------------


def test_selection_cannot_reintroduce_ineligible_titles(tmp_path):
    novel = {"genres": ["Romance"], "studios": ["Studio Z"], "source": "Original",
             "media_type": "movie"}
    catalog = [
        _catalog_row(1),
        _catalog_row(2, **novel, start_date="2030-01-01", airing_status="Not yet aired"),
        _catalog_row(3, **novel, content_rating="Rx - Hentai"),
        _catalog_row(4, **novel),                        # blocked sequel of 5
        _catalog_row(5),
        *[_catalog_row(anime_id) for anime_id in range(6, 12)],
        _catalog_row(12, **{**novel, "media_type": "music"}),
    ]
    engine = OnnxSequenceRankingEngine(
        _bundle(tmp_path, catalog, prerequisites=[(3, 4)]),
        session_factory=lambda _path: FakeSession(
            [9.9, 9.8, 9.7, 9.6, 5.0, 4.9, 4.8, 4.7, 4.6, 4.5, 4.4, 9.5]
        ),
    )
    service = RecommendationService(ranker=engine)
    candidates = pd.DataFrame.from_records(
        engine.candidate_catalog(include_nsfw=False, as_of=AS_OF)
        + (
            {"Anime ID": 2, "Title": "Title 002", "Genres": ["Romance"],
             "Start Date": "2030-01-01", "Anime Status": "Not yet aired"},
        )
    )

    feed = service.recommend(
        candidates, PROFILE,
        PipelineSettings(recommendation_count=5, candidate_pool_size=12,
                         top_anime_limit=12, randomness_factor=10),
        user_history=HISTORY, consumed_mal_ids={1}, excluded_mal_ids={6},
        as_of=AS_OF,
    )

    assert not {1, 2, 3, 4, 6, 12} & set(_ids(feed))
    assert _ids(feed) == [5, 7, 8, 9, 10]


def test_selected_heuristic_rows_keep_their_exact_scores_and_explanations():
    candidates = _heuristic_candidates()
    pool = _heuristic_pool(candidates).set_index("Anime ID", drop=False)

    feed = _heuristic_feed(candidates, adventurousness=10)

    assert _ids(feed) != _ids(pool)[:10]  # selection actually diversified
    for _index, row in feed.iterrows():
        original = pool.loc[row["Anime ID"]]
        for column in ("Recommendation Score", "Match Score", "Genre Contributions",
                       "Contributing Genres", "Recommendation Reason"):
            assert row[column] == original[column]
        breakdown = sum(value for _label, value in row["Genre Contributions"])
        assert breakdown == pytest.approx(row["Match Score"], abs=0.01)
    assert feed.attrs["ranking_engine"].explanation_type == "exact-additive"


def test_selected_onnx_rows_keep_model_scores_and_honest_explanations(tmp_path):
    distinct = {"genres": ["Romance"], "studios": ["Studio B"],
                "source": "Original", "media_type": "movie"}
    logits = _descending_logits(12)
    feed = _onnx_feed(tmp_path, _clone_catalog(12, {8: distinct}), logits,
                      count=4, adventurousness=10)

    for _index, row in feed.iterrows():
        assert row["Recommendation Score"] == pytest.approx(logits[row["Anime ID"] - 1])
        assert not row["Match Score Available"]
        assert row["Genre Contributions"] == []
        assert row["Contributing Genres"] == []
        assert _model_rank(row) == row["Anime ID"] - 1
    assert feed.attrs["ranking_engine"].explanation_type == "sequence-score"
    assert feed.attrs["ranking_engine"].engine_id == "sasrec-onnx"
