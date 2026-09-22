from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from models import PipelineSettings
from scoring.contracts import RankingEngineMetadata, RankingResult
from scoring.engines import FallbackRankingEngine, RankingEngineUnavailable
from scoring.eligibility import EligibilityAudit, EligibilityContext, FinalEligibilityPolicy
from services import RecommendationService


def _catalog_row(**changes):
    row = {
        "start_date": "2020-01-01",
        "airing_status": "finished_airing",
        "content_rating": "PG-13",
        "media_type": "tv",
    }
    row.update(changes)
    return row


def test_final_policy_explains_every_exclusion_and_prefers_enriched_metadata():
    context = EligibilityContext(
        catalog_version="fixture-catalog-v1",
        catalog_by_mal_id={
            1: _catalog_row(),
            2: _catalog_row(airing_status="not_yet_aired"),
            3: _catalog_row(content_rating="Rx - Hentai"),
            4: _catalog_row(media_type="Music"),
            5: _catalog_row(),
            6: _catalog_row(),
            7: _catalog_row(),
            8: _catalog_row(start_date="2020"),
            9: _catalog_row(),
        },
        covered_mal_ids=frozenset(range(1, 10)),
        prerequisites_by_mal_id={5: frozenset({99})},
        strict_release_dates=True,
    )
    candidates = tuple(
        {"Anime ID": mal_id, "Title": f"Title {mal_id}"}
        for mal_id in range(1, 11)
    )
    # Candidate and catalogue restrictions are conservative, so a title whose
    # candidate release moved into the future cannot be reintroduced by merge.
    candidates = (
        {**candidates[0], "Start Date": "2030-01-01"},
        *candidates[1:],
        {"Anime ID": 9, "Title": "Duplicate nine"},
    )

    eligible, audit = FinalEligibilityPolicy().apply(
        candidates,
        context=context,
        user_history=({"Anime ID": 6, "Status": "plan_to_watch"},),
        excluded_mal_ids={7},
        as_of=date(2026, 9, 21),
    )

    assert [row["Anime ID"] for row in eligible] == [9]
    assert audit.catalog_version == "fixture-catalog-v1"
    assert audit.input_candidates == 11
    assert audit.eligible_candidates == 1
    assert audit.excluded_by_reason == {
        "already_in_history": 1,
        "duplicate": 1,
        "excluded_media_type": 1,
        "missing_prerequisite": 1,
        "not_released": 1,
        "not_yet_aired": 1,
        "outside_scorer_coverage": 1,
        "release_date_unavailable": 1,
        "restricted_content": 1,
        "user_excluded": 1,
    }


def test_consumed_direct_prequel_makes_the_later_entry_eligible():
    context = EligibilityContext(
        catalog_version="fixture-catalog-v1",
        catalog_by_mal_id={5: _catalog_row()},
        covered_mal_ids=frozenset({5}),
        prerequisites_by_mal_id={5: frozenset({99})},
        strict_release_dates=True,
    )

    eligible, audit = FinalEligibilityPolicy().apply(
        ({"Anime ID": 5, "Title": "Season two"},),
        context=context,
        consumed_mal_ids={99},
        as_of=date(2026, 9, 21),
    )

    assert [row["Anime ID"] for row in eligible] == [5]
    assert audit.excluded_candidates == 0


@pytest.mark.parametrize(
    ("catalog_change", "reason"),
    [
        ({"start_date": "2030-01-01"}, "not_released"),
        ({"airing_status": "not_yet_aired"}, "not_yet_aired"),
        ({"content_rating": "R+ - Mild Nudity"}, "restricted_content"),
        ({"media_type": "PV"}, "excluded_media_type"),
    ],
)
def test_safe_overlay_cannot_weaken_verified_catalogue_restrictions(
    catalog_change, reason
):
    context = EligibilityContext(
        catalog_version="fixture-catalog-v1",
        catalog_by_mal_id={1: _catalog_row(**catalog_change)},
        covered_mal_ids=frozenset({1}),
        strict_release_dates=True,
    )
    safe_overlay = ({
        "Anime ID": 1,
        "Title": "Claims to be safe",
        "Start Date": "2020-01-01",
        "Anime Status": "finished_airing",
        "Content Rating": "PG-13",
        "Media Type": "TV",
    },)

    eligible, audit = FinalEligibilityPolicy().apply(
        safe_overlay,
        context=context,
        as_of=date(2026, 9, 21),
    )

    assert eligible == ()
    assert audit.excluded_by_reason == {reason: 1}


def test_fallback_receives_the_same_filtered_candidates_and_audit():
    captured = []
    context = EligibilityContext(
        catalog_version="fixture-catalog-v1",
        catalog_by_mal_id={
            1: _catalog_row(),
            2: _catalog_row(start_date="2030-01-01"),
        },
        covered_mal_ids=frozenset({1, 2}),
        strict_release_dates=True,
    )

    class Preferred:
        engine_id = "preferred"

        def eligibility_context(self):
            return context

        def rank(self, _request):
            raise RankingEngineUnavailable("fixture unavailable")

    class Fallback:
        engine_id = "fallback"

        def rank(self, request):
            captured.append(request)
            row = {
                **request.candidates[0],
                "Recommendation Score": 1.0,
                "Match Score": 0.0,
                "Match Score Available": False,
            }
            return RankingResult(
                ranked_candidates=(row,),
                columns=tuple(row),
                metadata=RankingEngineMetadata(
                    engine_id=self.engine_id,
                    engine_version="1",
                    feature_schema_version="fixture-v1",
                    explanation_type="none",
                ),
            )

    service = RecommendationService(
        ranker=FallbackRankingEngine(Preferred(), Fallback())
    )
    candidates = pd.DataFrame(
        [
            {"Anime ID": 1, "Title": "Safe", "Genres": ["Action"]},
            {"Anime ID": 2, "Title": "Future", "Genres": ["Action"]},
        ]
    )
    fallback_candidates = candidates.iloc[[0]].copy()
    result = service.recommend(
        candidates,
        pd.DataFrame([{"Genre": "Action", "Importance_Score": 1.0}]),
        PipelineSettings(recommendation_count=1, candidate_pool_size=2, seed=7),
        fallback_candidates=fallback_candidates,
        as_of=date(2026, 9, 21),
    )

    assert result["Anime ID"].tolist() == [1]
    assert [row["Anime ID"] for row in captured[0].candidates] == [1]
    assert captured[0].context["eligibility"] == {
        "policy_version": "anirec-final-eligibility-v1",
        "catalog_version": "fixture-catalog-v1",
        "input_candidates": 1,
        "eligible_candidates": 1,
        "excluded_candidates": 0,
        "excluded_by_reason": {},
    }
    assert service.last_eligibility_audit.excluded_by_reason == {}
    assert result.attrs["eligibility_audit"].catalog_version == "fixture-catalog-v1"


def test_result_audit_is_request_owned_during_shared_state_interleaving(monkeypatch):
    service = RecommendationService(random_int=lambda _start, _end: 7)
    wrong_audit = EligibilityAudit(
        policy_version="raced-policy",
        catalog_version="wrong",
        input_candidates=999,
        eligible_candidates=0,
        excluded_by_reason={"wrong": 999},
    )
    original_from_records = pd.DataFrame.from_records

    def racing_from_records(*args, **kwargs):
        service._last_eligibility_audit = wrong_audit
        return original_from_records(*args, **kwargs)

    monkeypatch.setattr(pd.DataFrame, "from_records", racing_from_records)
    result = service.recommend(
        pd.DataFrame(
            [{"Anime ID": 1, "Title": "Safe", "Genres": ["Action"]}]
        ),
        pd.DataFrame([{"Genre": "Action", "Importance_Score": 1.0}]),
        PipelineSettings(recommendation_count=1, candidate_pool_size=1, seed=7),
        as_of=date(2026, 9, 21),
    )

    assert service.last_eligibility_audit is wrong_audit
    assert result.attrs["eligibility_audit"].policy_version == (
        "anirec-final-eligibility-v1"
    )
    assert result.attrs["eligibility_audit"].catalog_version == "live-unversioned"
    assert result.attrs["eligibility_audit"].eligible_candidates == 1
