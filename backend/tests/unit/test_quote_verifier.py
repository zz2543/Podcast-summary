from __future__ import annotations

from podsum.domain.quote_verifier import verify, verify_against_segments


def test_verbatim_quote_passes() -> None:
    assert verify("keep learning", "The lesson is to keep learning every week.")


def test_paraphrase_fails() -> None:
    assert not verify("continue studying", "The lesson is to keep learning every week.")


def test_case_mismatch_fails() -> None:
    assert not verify("Keep Learning", "The lesson is to keep learning every week.")


def test_nfkc_equivalent_passes() -> None:
    assert verify("AI tools", "ＡＩ tools change workflows.")


def test_double_space_is_tolerated() -> None:
    assert verify("keep learning", "The lesson is to keep   learning every week.")


def test_leading_newline_is_tolerated() -> None:
    assert verify("\nkeep learning", "The lesson is to keep learning every week.")


def test_missing_punctuation_fails() -> None:
    assert not verify("keep learning", "The lesson is to keep, learning every week.")


def test_partial_substring_at_segment_boundary_passes() -> None:
    ok, start_ms = verify_against_segments(
        "learning every",
        [
            {"start_ms": 1_000, "end_ms": 4_000, "text": "keep learning"},
            {"start_ms": 4_200, "end_ms": 8_000, "text": "every week"},
        ],
    )

    assert ok
    assert start_ms == 1_000


def test_verify_against_segments_returns_false_for_missing_quote() -> None:
    ok, start_ms = verify_against_segments(
        "not in transcript",
        [{"start_ms": 0, "end_ms": 1_000, "text": "actual words"}],
    )

    assert not ok
    assert start_ms is None
