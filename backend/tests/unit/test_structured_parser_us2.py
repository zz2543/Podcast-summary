from __future__ import annotations

import pytest

from podsum.domain.structured_parser import RetriableValidationError, parse_chapter_payload


def test_parse_chapter_payload_rejects_empty_key_points() -> None:
    with pytest.raises(RetriableValidationError):
        parse_chapter_payload(
            {
                "chapters": [
                    {
                        "title": "Opening",
                        "key_points": [],
                        "candidate_quotes": [],
                    }
                ]
            }
        )


def test_parse_chapter_payload_defaults_missing_quote_timestamp() -> None:
    # A key moment gets its real timestamp from verifying the anchor against the
    # transcript, so the model no longer has to supply one.
    chapters = parse_chapter_payload(
        {
            "chapters": [
                {
                    "title": "Opening",
                    "key_points": ["Context"],
                    "key_moments": [{"quote": "A quote without time", "takeaway": "Why it matters"}],
                }
            ]
        }
    )

    assert chapters[0].moments[0].start_ms == 0
    assert chapters[0].moments[0].text == "A quote without time"
    assert chapters[0].moments[0].takeaway == "Why it matters"


def test_parse_chapter_payload_rejects_moment_without_text() -> None:
    with pytest.raises(RetriableValidationError):
        parse_chapter_payload(
            {
                "chapters": [
                    {
                        "title": "Opening",
                        "key_points": ["Context"],
                        "key_moments": [{"takeaway": "No anchor to locate"}],
                    }
                ]
            }
        )


def test_parse_chapter_payload_keeps_optional_summary() -> None:
    chapters = parse_chapter_payload(
        {
            "chapters": [
                {"title": "Opening", "key_points": ["Context"], "summary": "  Why it went this way.  "},
                {"title": "Next", "key_points": ["Context"]},
            ]
        }
    )

    assert chapters[0].summary == "Why it went this way."
    assert chapters[1].summary is None


def test_parse_chapter_payload_accepts_valid_case() -> None:
    chapters = parse_chapter_payload(
        {
            "chapters": [
                {
                    "title": "Opening",
                    "key_points": [" Context ", "Argument"],
                    "candidate_quotes": [{"text": " Verbatim quote ", "start_ms": 12_000}],
                }
            ]
        }
    )

    assert len(chapters) == 1
    assert chapters[0].title == "Opening"
    assert chapters[0].key_points == ["Context", "Argument"]
    assert chapters[0].candidate_quotes[0].text == "Verbatim quote"
    assert chapters[0].candidate_quotes[0].start_ms == 12_000


def test_parse_chapter_payload_ignores_extra_fields() -> None:
    chapters = parse_chapter_payload(
        [
            {
                "title": "Opening",
                "key_points": ["Context"],
                "candidate_quotes": [
                    {
                        "text": "A verified candidate",
                        "start_ms": 20_000,
                        "confidence": 0.12,
                    }
                ],
                "unused": "ignored",
            }
        ]
    )

    assert chapters[0].model_dump() == {
        "title": "Opening",
        "key_points": ["Context"],
        "candidate_quotes": [
            {"text": "A verified candidate", "start_ms": 20_000, "takeaway": None}
        ],
        "key_moments": [],
        "summary": None,
    }
