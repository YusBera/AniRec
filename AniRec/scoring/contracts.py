"""Technology-neutral contracts for recommendation ranking engines.

The application speaks these plain Python structures at the ranking boundary.
An engine may use pandas, NumPy, ONNX, a subprocess, or another implementation
internally without exposing that choice to the pipeline or interface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Protocol, runtime_checkable


RANKING_CONTRACT_VERSION = 1
RANKING_INPUT_SCHEMA_VERSION = "anirec-ranking-input-v1"


@dataclass(frozen=True)
class RankingParameters:
    """Engine-independent controls for one ranking operation."""

    recommendation_count: int
    candidate_pool_size: int
    randomness_factor: int
    random_seed: int
    minimum_mean_score: float | None = None

    def __post_init__(self) -> None:
        if int(self.recommendation_count) <= 0:
            raise ValueError("recommendation_count must be positive.")
        if int(self.candidate_pool_size) <= 0:
            raise ValueError("candidate_pool_size must be positive.")
        if int(self.randomness_factor) <= 0:
            raise ValueError("randomness_factor must be positive.")


@dataclass(frozen=True)
class RankingRequest:
    """Portable input for any current or future ranking implementation.

    Rows are deliberately mappings rather than dataframes or tensors. Each
    engine owns the conversion into its preferred runtime representation.
    Column order is retained separately so tabular adapters can round-trip an
    empty input without losing its schema.
    """

    candidates: tuple[Mapping[str, object], ...]
    taste_profile: tuple[Mapping[str, object], ...]
    parameters: RankingParameters
    user_history: tuple[Mapping[str, object], ...] = ()
    candidate_columns: tuple[str, ...] = ()
    profile_columns: tuple[str, ...] = ()
    history_columns: tuple[str, ...] = ()
    context: Mapping[str, object] = field(default_factory=dict)
    taste_adjustments: Mapping[str, float] = field(default_factory=dict)
    excluded_mal_ids: frozenset[int] = frozenset()
    excluded_titles: frozenset[str] = frozenset()
    collaborative_scores: Mapping[int, float] = field(default_factory=dict)
    input_schema_version: str = RANKING_INPUT_SCHEMA_VERSION
    contract_version: int = RANKING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != RANKING_CONTRACT_VERSION:
            raise ValueError(
                f"Unsupported ranking contract version: {self.contract_version!r}."
            )
        object.__setattr__(self, "candidates", tuple(dict(row) for row in self.candidates))
        object.__setattr__(
            self,
            "taste_profile",
            tuple(dict(row) for row in self.taste_profile),
        )
        object.__setattr__(
            self,
            "user_history",
            tuple(dict(row) for row in self.user_history),
        )
        object.__setattr__(
            self,
            "candidate_columns",
            tuple(str(value) for value in self.candidate_columns),
        )
        object.__setattr__(
            self,
            "profile_columns",
            tuple(str(value) for value in self.profile_columns),
        )
        object.__setattr__(
            self,
            "history_columns",
            tuple(str(value) for value in self.history_columns),
        )
        object.__setattr__(self, "context", dict(self.context))
        object.__setattr__(
            self,
            "taste_adjustments",
            {str(key): float(value) for key, value in self.taste_adjustments.items()},
        )
        object.__setattr__(
            self,
            "excluded_mal_ids",
            frozenset(int(value) for value in self.excluded_mal_ids),
        )
        object.__setattr__(
            self,
            "excluded_titles",
            frozenset(str(value) for value in self.excluded_titles),
        )
        object.__setattr__(
            self,
            "collaborative_scores",
            {int(key): float(value) for key, value in self.collaborative_scores.items()},
        )


@dataclass(frozen=True)
class RankingEngineMetadata:
    """Provenance needed to reproduce and diagnose a ranking result."""

    engine_id: str
    engine_version: str
    feature_schema_version: str
    explanation_type: str
    inference_ms: float | None = None
    fallback_used: bool = False
    requested_engine_id: str | None = None
    contract_version: int = RANKING_CONTRACT_VERSION


@dataclass(frozen=True)
class RankingResult:
    """Portable ranked rows plus engine provenance and non-fatal warnings."""

    ranked_candidates: tuple[Mapping[str, object], ...]
    columns: tuple[str, ...]
    metadata: RankingEngineMetadata
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "ranked_candidates",
            tuple(dict(row) for row in self.ranked_candidates),
        )
        object.__setattr__(self, "columns", tuple(str(value) for value in self.columns))
        object.__setattr__(self, "warnings", tuple(str(value) for value in self.warnings))


@runtime_checkable
class RankingEngine(Protocol):
    """The only interface the application requires from a ranking engine."""

    engine_id: str

    def rank(self, request: RankingRequest) -> RankingResult:
        """Rank candidates or raise a typed availability error."""
