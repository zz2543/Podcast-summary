from __future__ import annotations

import pytest

from podsum.domain.structured_parser import RetriableValidationError, parse_one_liner


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


def test_parse_one_liner_rejects_title_repeat() -> None:
    with pytest.raises(RetriableValidationError, match="similar"):
        parse_one_liner(
            '{"hook": "AI Coding Interview Prep"}',
            episode_title="AI coding interview prep",
            lang="en",
        )
