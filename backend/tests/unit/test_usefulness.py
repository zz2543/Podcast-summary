from __future__ import annotations

import pytest

from podsum.domain.structured_parser import RetriableValidationError, parse_usefulness
from podsum.domain.usefulness_scorer import band_for


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0, "skippable"),
        (49, "skippable"),
        (50, "skimmable"),
        (69, "skimmable"),
        (70, "worth_listening"),
        (84, "worth_listening"),
        (85, "must_listen"),
        (100, "must_listen"),
    ],
)
def test_band_for_covers_every_boundary(score: int, expected: str) -> None:
    assert band_for(score) == expected


@pytest.mark.parametrize("score", [-1, 101, 1000])
def test_band_for_rejects_out_of_range(score: int) -> None:
    with pytest.raises(ValueError):
        band_for(score)


@pytest.mark.parametrize("score", [78.5, "78", None, True])
def test_band_for_rejects_non_integers(score: object) -> None:
    with pytest.raises(ValueError):
        band_for(score)  # type: ignore[arg-type]


def test_parse_usefulness_attaches_derived_band() -> None:
    result = parse_usefulness({"score": 78, "rationale": "Concrete data,  little filler."})

    assert result.score == 78
    assert result.band == "worth_listening"
    # Whitespace is collapsed the same way as every other parsed field.
    assert result.rationale == "Concrete data, little filler."


def test_parse_usefulness_ignores_a_model_supplied_band() -> None:
    """The band is a function of the score; a model that guesses does not get a vote."""
    result = parse_usefulness({"score": 20, "rationale": "Mostly chit-chat.", "band": "must_listen"})

    assert result.band == "skippable"


def test_parse_usefulness_accepts_a_json_string_payload() -> None:
    result = parse_usefulness('{"score": 91, "rationale": "Dense and verifiable."}')

    assert (result.score, result.band) == (91, "must_listen")


@pytest.mark.parametrize(
    "payload",
    [
        {"score": 101, "rationale": "Too high."},
        {"score": -1, "rationale": "Too low."},
        {"score": 78.5, "rationale": "Not an integer."},
        {"score": "78", "rationale": "A string, not an integer."},
        {"rationale": "Score missing."},
        {"score": 78},
        {"score": 78, "rationale": "   "},
        {"score": 78, "rationale": "Fine.", "dimensions": {"novelty": 9}},
        "not json at all",
    ],
)
def test_parse_usefulness_rejects_bad_payloads(payload: object) -> None:
    with pytest.raises(RetriableValidationError):
        parse_usefulness(payload)


def test_out_of_range_score_is_never_clamped() -> None:
    """140 must be retried, not silently rewritten as 100."""
    with pytest.raises(RetriableValidationError) as excinfo:
        parse_usefulness({"score": 140, "rationale": "Wildly out of range."})

    assert "0-100" in str(excinfo.value)
