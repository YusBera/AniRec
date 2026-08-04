"""CSV persistence adapter; calculation services only receive DataFrames."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from collections.abc import Callable, Iterable
from dataclasses import dataclass

import pandas as pd


@dataclass
class _StagedCsv:
    destination: Path
    temporary: Path
    backup: Path | None = None
    committed: bool = False


class CsvStorage:
    def __init__(self, *, replace_func=os.replace) -> None:
        self._replace = replace_func

    def read(
        self,
        path: str | Path,
        *,
        required_columns: Iterable[str] = (),
    ) -> pd.DataFrame:
        source = Path(path)
        if not source.exists():
            raise FileNotFoundError(f"File not found: {source}")
        frame = pd.read_csv(source)
        missing = set(required_columns) - set(frame.columns)
        if missing:
            columns = ", ".join(sorted(missing))
            raise ValueError(f"{source} is missing required columns: {columns}")
        return frame

    def write(self, frame: pd.DataFrame, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            frame.to_csv(temporary, index=False)
            self._replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return destination

    def write_batch(
        self,
        entries: Iterable[tuple[pd.DataFrame, str | Path]],
        *,
        cancellation_check: Callable[[], None] | None = None,
    ) -> tuple[Path, ...]:
        """Replace several CSVs as one rollback-capable local transaction."""
        staged: list[_StagedCsv] = []
        destinations: set[Path] = set()
        try:
            for frame, path in entries:
                if cancellation_check:
                    cancellation_check()
                destination = Path(path)
                if destination in destinations:
                    raise ValueError(f"Duplicate CSV batch destination: {destination}")
                destinations.add(destination)
                destination.parent.mkdir(parents=True, exist_ok=True)
                descriptor, temporary_name = tempfile.mkstemp(
                    prefix=f".{destination.name}.",
                    suffix=".tmp",
                    dir=destination.parent,
                )
                os.close(descriptor)
                temporary = Path(temporary_name)
                staged.append(_StagedCsv(destination, temporary))
                frame.to_csv(temporary, index=False)

            if cancellation_check:
                cancellation_check()
            for item in staged:
                if cancellation_check:
                    cancellation_check()
                if item.destination.exists():
                    descriptor, backup_name = tempfile.mkstemp(
                        prefix=f".{item.destination.name}.",
                        suffix=".bak",
                        dir=item.destination.parent,
                    )
                    os.close(descriptor)
                    item.backup = Path(backup_name)
                    item.backup.unlink()
                    self._replace(item.destination, item.backup)
                self._replace(item.temporary, item.destination)
                item.committed = True
        except Exception:
            self._rollback(staged)
            raise
        finally:
            for item in staged:
                item.temporary.unlink(missing_ok=True)

        for item in staged:
            if item.backup is not None:
                item.backup.unlink(missing_ok=True)
        return tuple(item.destination for item in staged)

    def _rollback(self, staged: Iterable[_StagedCsv]) -> None:
        for item in reversed(tuple(staged)):
            if item.committed:
                item.destination.unlink(missing_ok=True)
            if item.backup is not None and item.backup.exists():
                self._replace(item.backup, item.destination)
        for item in staged:
            if item.backup is not None:
                item.backup.unlink(missing_ok=True)
