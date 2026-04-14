"""Helpers for working with genre values stored in CSV files."""

from __future__ import annotations

import ast
import math
from typing import Iterable


def parse_genres(value: object) -> list[str]:
    """Return a clean genre list from an API value or a CSV string value."""
    if value is None:
        return []

    if isinstance(value, float) and math.isnan(value):
        return []

    if isinstance(value, (list, tuple, set)):
        return _clean_genres(value)

    if isinstance(value, str):
        stripped_value = value.strip()
        if not stripped_value:
            return []

        try:
            parsed_value = ast.literal_eval(stripped_value)
        except (SyntaxError, ValueError):
            return _clean_genres(stripped_value.split(","))

        if isinstance(parsed_value, (list, tuple, set)):
            return _clean_genres(parsed_value)

        return _clean_genres([parsed_value])

    return _clean_genres([value])


def _clean_genres(values: Iterable[object]) -> list[str]:
    return [str(value).strip() for value in values if str(value).strip()]
