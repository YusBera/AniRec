"""Presentation models onto the wire, and nothing more.

There is deliberately almost no code here. ``RecommendationViewModel`` and the
rest of ``AniRec.presentation`` are frozen dataclasses of primitives and
tuples, so ``dataclasses.asdict`` already produces valid JSON. That is the
whole finding of the boundary work: the projection the Qt cards were reading
is the projection an HTTP client reads, unchanged.

One honest caveat, recorded here because it will matter later. The view model
carries pre-formatted display strings beside its numbers - ``mal_score`` and
``mal_score_text``, ``year`` and ``year_text``. Those were written for Qt,
where a label takes a string. A browser client wants the number and its own
formatting, and a second locale would need the text fields rebuilt server-side
for no reason. They are serialized as they stand so this stage changes no
behaviour, but the eventual contract should send numbers plus the few strings
that encode a real product decision - ``reason``, which has fallback logic
worth keeping in one place - and let the client format the rest.
"""

from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from ..models import PipelineResult
from ..presentation import (
    MetadataCatalog,
    RecommendationViewModel,
    recommendation_view_models,
)
from ..services import RecommendationLocalState


def view_model_to_dict(model: RecommendationViewModel) -> dict[str, Any]:
    """One recommendation, exactly as the presentation layer computed it."""
    payload = asdict(model)
    payload["genre_contributions"] = [
        {"label": str(name), "value": float(value)}
        for name, value in model.genre_contributions
    ]
    # A property rather than a field, so asdict does not see it. The card
    # needs it and the rule for composing it belongs beside the two dates.
    payload["aired_text"] = model.aired_text
    return payload


def local_state_to_dict(state: RecommendationLocalState) -> dict[str, Any]:
    """The profile-local votes, keyed by MAL id the way the client indexes."""
    return {
        "hidden_mal_ids": sorted(state.hidden_mal_ids),
        "watch_later_mal_ids": sorted(state.watch_later_mal_ids),
        "liked_mal_ids": sorted(state.liked_mal_ids),
        "disliked_mal_ids": sorted(state.disliked_mal_ids),
        "show_hidden": state.show_hidden,
    }


def catalogue_to_dict(models: tuple[RecommendationViewModel, ...]) -> dict[str, Any]:
    """Genres, studios and years present in what was actually loaded.

    Built from the same ``MetadataCatalog`` the desktop typeahead uses, so the
    filter controls on both clients offer the same terms from the same counts
    rather than two independently derived lists.
    """
    catalogue = MetadataCatalog()
    catalogue.ingest(models)
    years = sorted({model.year for model in models if model.year is not None}, reverse=True)
    statuses = sorted({model.status for model in models if model.status})
    return {
        "genres": list(catalogue.genres),
        "studios": list(catalogue.studios),
        "years": years,
        "statuses": statuses,
    }


def pipeline_result_to_dict(result: PipelineResult | None) -> dict[str, Any]:
    """A result as the feed reads it: view models plus the run's own stats."""
    if result is None:
        return {"recommendations": [], "user_stats": {}, "generated_files": []}
    models = recommendation_view_models(result.recommendations)
    return {
        "recommendations": [view_model_to_dict(model) for model in models],
        "user_stats": dict(result.user_stats),
        "generated_files": list(result.generated_files),
        "started_at": result.started_at,
        "completed_at": result.completed_at,
    }


def any_to_dict(value: Any) -> dict[str, Any]:
    """Best-effort JSON for an operation result of unknown concrete type."""
    if value is None:
        return {}
    if isinstance(value, PipelineResult):
        return pipeline_result_to_dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return dict(to_dict())
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return {"value": str(value)}
