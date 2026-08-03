"""MyAnimeList data service with an injectable HTTP boundary."""

from __future__ import annotations

from collections.abc import Callable

import pandas as pd

try:
    from ..anime_data import get_top_anime
    from ..infrastructure.mal_client import MALClient
    from ..user_data import get_user_completed_animes
except ImportError:  # Compatibility with the S01 top-level test import path.
    from anime_data import get_top_anime
    from infrastructure.mal_client import MALClient
    from user_data import get_user_completed_animes


class AnimeDataService:
    def __init__(
        self,
        *,
        http_get: Callable | None = None,
        top_fetcher: Callable = get_top_anime,
        completed_fetcher: Callable = get_user_completed_animes,
        client: MALClient | None = None,
    ) -> None:
        self._client = client or MALClient(http_get=http_get)
        self._top_fetcher = top_fetcher
        self._completed_fetcher = completed_fetcher

    def fetch_top_anime(
        self,
        *,
        limit: int,
        access_token: str | None = None,
        client_id: str | None = None,
        cancellation_token=None,
    ) -> pd.DataFrame:
        return self._top_fetcher(
            limit=limit,
            access_token=access_token,
            client_id=client_id,
            client=self._client,
            cancellation=cancellation_token,
        )

    def fetch_completed_anime(
        self,
        username: str,
        access_token: str | None = None,
        *,
        client_id: str | None = None,
        cancellation_token=None,
    ) -> pd.DataFrame:
        return self._completed_fetcher(
            username,
            access_token,
            client_id=client_id,
            client=self._client,
            cancellation=cancellation_token,
        )
