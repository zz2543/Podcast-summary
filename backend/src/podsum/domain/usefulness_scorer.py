"""Usefulness score helpers (FR-027).

The model returns a 0-100 ``score`` and a one-sentence ``rationale``; the band is
derived here so that the same score always maps to the same band regardless of
what the model felt like calling it.
"""

from __future__ import annotations

from typing import Literal

Band = Literal["must_listen", "worth_listening", "skimmable", "skippable"]

MIN_SCORE = 0
MAX_SCORE = 100

#: (inclusive lower bound, band), highest first.
_BAND_THRESHOLDS: tuple[tuple[int, Band], ...] = (
    (85, "must_listen"),
    (70, "worth_listening"),
    (50, "skimmable"),
    (0, "skippable"),
)


def band_for(score: int) -> Band:
    """Map a 0-100 score onto its band.

    Raises ``ValueError`` for anything outside 0-100 or not an integer: an
    out-of-range score is a model failure to retry, never something to clamp.
    """
    if isinstance(score, bool) or not isinstance(score, int):
        raise ValueError("usefulness score must be an integer")
    if not MIN_SCORE <= score <= MAX_SCORE:
        raise ValueError(f"usefulness score must be within {MIN_SCORE}-{MAX_SCORE}")
    for lower_bound, band in _BAND_THRESHOLDS:
        if score >= lower_bound:
            return band
    raise AssertionError("unreachable: bands cover 0-100")
