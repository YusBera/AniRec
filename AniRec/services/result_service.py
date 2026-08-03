"""Profile-scoped persistence for the latest successful pipeline result."""

from __future__ import annotations

from pathlib import Path

try:
    from ..errors import DataError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.paths import profile_dir
    from ..models import PipelineResult
except ImportError:  # Compatibility with the legacy top-level import path.
    from errors import DataError
    from infrastructure.json_storage import JsonStore
    from infrastructure.paths import profile_dir
    from models import PipelineResult


LATEST_RESULT_FILENAME = "latest_result.json"


class ResultService:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        store: JsonStore | None = None,
    ) -> None:
        self._root_override = root_override
        self._store = store or JsonStore()

    def path(self, profile_id: str) -> Path:
        return profile_dir(profile_id, self._root_override) / LATEST_RESULT_FILENAME

    def load(self, profile_id: str) -> PipelineResult | None:
        path = self.path(profile_id)
        if not path.exists():
            return None
        try:
            return PipelineResult.from_dict(self._store.read(path))
        except (OSError, TypeError, ValueError, KeyError) as error:
            raise DataError("The saved pipeline result is invalid.") from error

    def save(self, profile_id: str, result: PipelineResult) -> Path:
        return self._store.write(result.to_dict(), self.path(profile_id))

    def save_merged(self, profile_id: str, result: PipelineResult) -> PipelineResult:
        previous = self.load(profile_id)
        if previous is None:
            self.save(profile_id, result)
            return result

        user_stats = dict(previous.user_stats)
        user_stats.update(result.user_stats)
        generated_files = tuple(
            dict.fromkeys((*previous.generated_files, *result.generated_files))
        )
        merged = PipelineResult(
            recommendations=result.recommendations or previous.recommendations,
            genre_stats=result.genre_stats or previous.genre_stats,
            user_stats=user_stats,
            generated_files=generated_files,
            started_at=result.started_at or previous.started_at,
            completed_at=result.completed_at or previous.completed_at,
        )
        self.save(profile_id, merged)
        return merged
