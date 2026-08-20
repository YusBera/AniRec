"""Shared title normalization for exclusion and de-duplication comparisons."""

from __future__ import annotations

import math


_MISSING_TITLE_KEYS = {"", "nan", "none", "<na>"}


def normalize_title_key(value: object) -> str:
    """Return a comparable key for a title, or an empty string when absent.

    Every exclusion and de-duplication path must agree on this, otherwise a
    trailing space or a missing value silently changes whether a title is
    filtered. Missing values collapse to an empty key rather than to the string
    ``"nan"``, which would otherwise make untitled rows match one another.
    """
    if value is None:
        return ""
    if isinstance(value, float) and math.isnan(value):
        return ""
    key = str(value).strip().casefold()
    return "" if key in _MISSING_TITLE_KEYS else key
