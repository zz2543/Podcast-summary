from __future__ import annotations

import pytest

from podsum.domain.structured_parser import (
    RetriableValidationError,
    parse_one_liner,
    parse_three_act,
)


def test_parse_one_liner_accepts_valid_hook() -> None:
    assert (
        parse_one_liner(
            {"hook": "How pricing changes shape AI coding"},
            episode_title="Weekly developer news",
            lang="en",
        )
        == "How pricing changes shape AI coding"
    )


def test_parse_one_liner_rejects_over_50_code_points() -> None:
    with pytest.raises(RetriableValidationError, match="50"):
        parse_one_liner({"hook": "中" * 51}, episode_title="标题", lang="zh")


def test_parse_one_liner_rejects_over_50_english_code_points() -> None:
    with pytest.raises(RetriableValidationError, match="50"):
        parse_one_liner({"hook": "a" * 51}, episode_title="title", lang="en")


def test_parse_one_liner_rejects_title_repeat() -> None:
    with pytest.raises(RetriableValidationError, match="similar"):
        parse_one_liner(
            '{"hook": "AI Coding Interview Prep"}',
            episode_title="AI coding interview prep",
            lang="en",
        )


def test_parse_one_liner_rejects_near_title_paraphrase() -> None:
    with pytest.raises(RetriableValidationError, match="similar"):
        parse_one_liner(
            {"hook": "AI coding interview guide"},
            episode_title="AI coding interview prep",
            lang="en",
        )


def test_parse_three_act_accepts_valid_payload() -> None:
    three_act = parse_three_act(
        {
            "background": " The market changed. ",
            "core_argument": "Teams need tighter feedback loops.",
            "conclusion": "Adopt smaller releases.",
        }
    )

    assert three_act.model_dump() == {
        "background": "The market changed.",
        "core_argument": "Teams need tighter feedback loops.",
        "conclusion": "Adopt smaller releases.",
    }


def test_parse_three_act_rejects_extra_keys() -> None:
    with pytest.raises(RetriableValidationError):
        parse_three_act(
            {
                "background": "A",
                "core_argument": "B",
                "conclusion": "C",
                "extra": "D",
            }
        )


def test_parse_three_act_rejects_missing_key() -> None:
    with pytest.raises(RetriableValidationError):
        parse_three_act(
            {
                "background": "A",
                "core_argument": "B",
            }
        )


def test_parse_three_act_rejects_whitespace_only_fields() -> None:
    with pytest.raises(RetriableValidationError):
        parse_three_act(
            {
                "background": "A",
                "core_argument": " ",
                "conclusion": "C",
            }
        )
