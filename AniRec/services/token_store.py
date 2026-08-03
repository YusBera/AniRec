"""Profile-isolated OAuth token persistence."""

from __future__ import annotations

from pathlib import Path

try:
    from ..errors import AuthError
    from ..infrastructure.json_storage import JsonStore
    from ..infrastructure.paths import token_file
    from ..models import TokenRecord
except ImportError:  # Compatibility with the S01 top-level import path.
    from errors import AuthError
    from infrastructure.json_storage import JsonStore
    from infrastructure.paths import token_file
    from models import TokenRecord


class TokenStore:
    def __init__(
        self,
        *,
        root_override: str | Path | None = None,
        store: JsonStore | None = None,
    ) -> None:
        self._root_override = root_override
        self._store = store or JsonStore()

    def path_for(self, profile_id: str) -> Path:
        return token_file(profile_id, self._root_override)

    def load(self, profile_id: str) -> TokenRecord | None:
        path = self.path_for(profile_id)
        if not path.exists():
            return None
        try:
            return TokenRecord.from_storage_dict(self._store.read(path))
        except (OSError, TypeError, ValueError) as error:
            raise AuthError("Stored OAuth token is invalid.") from error

    def save(self, profile_id: str, token: TokenRecord) -> Path:
        return self._store.write(token.to_storage_dict(), self.path_for(profile_id))

    def delete(self, profile_id: str) -> Path:
        path = self.path_for(profile_id)
        path.unlink(missing_ok=True)
        return path
