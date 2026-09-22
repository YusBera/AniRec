"""Engine-independent final recommendation eligibility policy.

This module is deliberately free of pandas and model runtimes so the serving
path and offline evaluators can apply exactly the same rules.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
import math

try:
    from ..title_utils import normalize_title_key
except ImportError:  # Compatibility with the top-level import path used by tests.
    from title_utils import normalize_title_key


ELIGIBILITY_POLICY_VERSION = "anirec-final-eligibility-v1"
EXCLUDED_MEDIA_TYPES = frozenset({"music", "cm", "pv"})


@dataclass(frozen=True)
class EligibilityContext:
    """Versioned catalogue facts used by the final policy.

    ``covered_mal_ids`` is ``None`` when the active scorer has no fixed item
    vocabulary. An empty set means that the versioned catalogue covers nothing.
    """

    catalog_version: str = "live-unversioned"
    catalog_by_mal_id: Mapping[int, Mapping[str, object]] = field(default_factory=dict)
    covered_mal_ids: frozenset[int] | None = None
    prerequisites_by_mal_id: Mapping[int, frozenset[int]] = field(default_factory=dict)
    strict_release_dates: bool = False


@dataclass(frozen=True)
class EligibilityAudit:
    policy_version: str
    catalog_version: str
    input_candidates: int
    eligible_candidates: int
    excluded_by_reason: Mapping[str, int]

    @property
    def excluded_candidates(self) -> int:
        return self.input_candidates - self.eligible_candidates

    def as_dict(self) -> dict[str, object]:
        return {
            "policy_version": self.policy_version,
            "catalog_version": self.catalog_version,
            "input_candidates": self.input_candidates,
            "eligible_candidates": self.eligible_candidates,
            "excluded_candidates": self.excluded_candidates,
            "excluded_by_reason": dict(self.excluded_by_reason),
        }


class FinalEligibilityPolicy:
    """Apply one deterministic, auditable eligibility boundary before scoring."""

    version = ELIGIBILITY_POLICY_VERSION

    def apply(
        self,
        candidates: Sequence[Mapping[str, object]],
        *,
        context: EligibilityContext | None = None,
        user_history: Iterable[Mapping[str, object]] = (),
        consumed_mal_ids: Iterable[int] = (),
        excluded_mal_ids: Iterable[int] = (),
        excluded_titles: Iterable[str] = (),
        include_nsfw: bool = False,
        as_of: date | None = None,
    ) -> tuple[tuple[dict[str, object], ...], EligibilityAudit]:
        context = context or EligibilityContext()
        cutoff = as_of or date.today()
        history = tuple(user_history)
        known_ids = self._history_ids(history)
        consumed_ids = {
            *self._positive_ids(consumed_mal_ids),
            *self._consumed_history_ids(history),
        }
        explicit_ids = self._positive_ids(excluded_mal_ids)
        explicit_titles = {
            key for value in excluded_titles if (key := normalize_title_key(value))
        }
        reasons: Counter[str] = Counter()
        eligible: list[dict[str, object]] = []
        seen_ids: set[int] = set()
        seen_titles: set[str] = set()

        for source in candidates:
            row = dict(source)
            mal_id = self._positive_int(row.get("Anime ID"))
            title_key = normalize_title_key(row.get("Title"))
            metadata = context.catalog_by_mal_id.get(mal_id, {}) if mal_id else {}

            if mal_id is not None:
                if mal_id in seen_ids:
                    reasons["duplicate"] += 1
                    continue
                seen_ids.add(mal_id)
            elif title_key:
                if title_key in seen_titles:
                    reasons["duplicate"] += 1
                    continue
                seen_titles.add(title_key)

            if context.covered_mal_ids is not None and (
                mal_id is None or mal_id not in context.covered_mal_ids
            ):
                reasons["outside_scorer_coverage"] += 1
                continue
            if mal_id is not None and mal_id in known_ids:
                reasons["already_in_history"] += 1
                continue
            if (mal_id is not None and mal_id in explicit_ids) or (
                title_key and title_key in explicit_titles
            ):
                reasons["user_excluded"] += 1
                continue

            row_release_value = row.get("Start Date")
            row_release = (
                self._exact_date(row_release_value)
                if self._present(row_release_value)
                else None
            )
            catalog_release_value = metadata.get("start_date")
            catalog_release = (
                self._exact_date(catalog_release_value)
                if self._present(catalog_release_value)
                else None
            )
            if context.strict_release_dates and catalog_release is None:
                reasons["release_date_unavailable"] += 1
                continue
            if (
                not context.strict_release_dates
                and self._present(row_release_value)
                and row_release is None
                and catalog_release is None
            ):
                reasons["release_date_unavailable"] += 1
                continue
            if any(
                released is not None and released > cutoff
                for released in (row_release, catalog_release)
            ):
                reasons["not_released"] += 1
                continue

            statuses = self._field_keys(
                row, metadata, "Anime Status", "airing_status"
            )
            if "not_yet_aired" in statuses:
                reasons["not_yet_aired"] += 1
                continue

            ratings = self._field_texts(
                row, metadata, "Content Rating", "content_rating"
            )
            if not include_nsfw and any(
                rating.casefold().startswith(("r+", "rx")) for rating in ratings
            ):
                reasons["restricted_content"] += 1
                continue

            media_types = self._field_keys(
                row, metadata, "Media Type", "media_type"
            )
            if media_types & EXCLUDED_MEDIA_TYPES:
                reasons["excluded_media_type"] += 1
                continue

            prerequisites = context.prerequisites_by_mal_id.get(mal_id, frozenset())
            if prerequisites and prerequisites.isdisjoint(consumed_ids):
                reasons["missing_prerequisite"] += 1
                continue
            eligible.append(row)

        audit = EligibilityAudit(
            policy_version=self.version,
            catalog_version=context.catalog_version,
            input_candidates=len(candidates),
            eligible_candidates=len(eligible),
            excluded_by_reason=dict(sorted(reasons.items())),
        )
        return tuple(eligible), audit

    @classmethod
    def _history_ids(cls, history: Iterable[Mapping[str, object]]) -> set[int]:
        return {
            mal_id
            for row in history
            if (mal_id := cls._positive_int(row.get("Anime ID"))) is not None
        }

    @classmethod
    def _consumed_history_ids(
        cls, history: Iterable[Mapping[str, object]]
    ) -> set[int]:
        consumed = set()
        for row in history:
            mal_id = cls._positive_int(row.get("Anime ID"))
            if mal_id is None:
                continue
            status = cls._key(row.get("Status"))
            episodes = cls._nonnegative_int(row.get("Episodes Watched"))
            if status == "completed" or (
                status == "watching" and episodes > 0
            ) or cls._truthy(row.get("Is Rewatching")):
                consumed.add(mal_id)
        return consumed

    @classmethod
    def _positive_ids(cls, values: Iterable[int]) -> set[int]:
        return {
            number
            for value in values
            if (number := cls._positive_int(value)) is not None
        }

    @classmethod
    def _field_texts(
        cls,
        row: Mapping[str, object],
        metadata: Mapping[str, object],
        row_name: str,
        metadata_name: str,
    ) -> tuple[str, ...]:
        values = []
        for value in (row.get(row_name), metadata.get(metadata_name)):
            if (text := cls._text(value)) is not None and text not in values:
                values.append(text)
        return tuple(values)

    @classmethod
    def _field_keys(
        cls,
        row: Mapping[str, object],
        metadata: Mapping[str, object],
        row_name: str,
        metadata_name: str,
    ) -> set[str]:
        return {
            key
            for value in cls._field_texts(row, metadata, row_name, metadata_name)
            if (key := cls._key(value))
        }

    @staticmethod
    def _present(value: object) -> bool:
        if value is None:
            return False
        if isinstance(value, float) and math.isnan(value):
            return False
        return not isinstance(value, str) or bool(value.strip())

    @staticmethod
    def _exact_date(value: object) -> date | None:
        if isinstance(value, datetime):
            return value.date()
        if isinstance(value, date):
            return value
        text = FinalEligibilityPolicy._text(value)
        if text is None:
            return None
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None

    @staticmethod
    def _positive_int(value: object) -> int | None:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    @staticmethod
    def _nonnegative_int(value: object) -> int:
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _truthy(value: object) -> bool:
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes"}
        return bool(value)

    @staticmethod
    def _text(value: object) -> str | None:
        if not FinalEligibilityPolicy._present(value):
            return None
        return str(value).strip() or None

    @staticmethod
    def _key(value: object) -> str:
        text = FinalEligibilityPolicy._text(value)
        return "" if text is None else text.casefold().replace("-", "_").replace(" ", "_")
