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


def test_parse_chapter_payload_rejects_quote_without_timestamp() -> None:
    with pytest.raises(RetriableValidationError):
        parse_chapter_payload(
            {
                "chapters": [
                    {
                        "title": "Opening",
                        "key_points": ["Context"],
                        "candidate_quotes": [{"text": "A quote without time"}],
                    }
                ]
            }
        )


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
        "candidate_quotes": [{"text": "A verified candidate", "start_ms": 20_000}],
    }
