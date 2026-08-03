"""UTF-8 JSON storage using temporary files and atomic replacement."""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class JsonStore:
    def __init__(self, *, replace_func=os.replace) -> None:
        self._replace = replace_func

    def read(self, path: str | Path) -> Mapping[str, Any]:
        source = Path(path)
        with source.open("r", encoding="utf-8") as stream:
            payload = json.load(stream)
        if not isinstance(payload, dict):
            raise ValueError("JSON root must be an object.")
        return payload

    def write(self, payload: Mapping[str, Any], path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.name}.",
            suffix=".tmp",
            dir=destination.parent,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            self._replace(temporary, destination)
            try:
                os.chmod(destination, 0o600)
            except OSError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
        return destination
