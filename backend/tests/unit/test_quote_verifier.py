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

    # Quote "learning every" begins inside the first segment ("keep learning")
    # at character offset 5 of its 13-char text spanning 1000..4000 ms, so the
    # interpolated start is 1000 + (5/13)*3000 ≈ 2153 ms.
    assert ok
    assert start_ms is not None
    assert 1_000 < start_ms < 4_000
    assert abs(start_ms - 2_153) <= 1


def test_quote_inside_long_merged_segment_is_interpolated() -> None:
    """Reflects production bug: when ASR/postprocess yields one giant segment,
    every quote used to collapse to the same start_ms. With interpolation,
    quotes near the end of a long segment get a timestamp near its end."""
    long_text = (
        "alpha bravo charlie delta echo foxtrot golf hotel india juliet "
        "kilo lima mike november oscar papa quebec romeo sierra tango "
        "uniform victor whiskey xray yankee zulu "
        "one two three four five six seven eight nine ten "
        "eleven twelve thirteen fourteen fifteen sixteen seventeen "
        "eighteen nineteen twenty"
    )
    segments = [{"start_ms": 0, "end_ms": 600_000, "text": long_text}]

    _, ms_start = verify_against_segments("alpha bravo", segments)
    _, ms_mid = verify_against_segments("oscar papa", segments)
    _, ms_end = verify_against_segments("nineteen twenty", segments)

    assert ms_start is not None and ms_mid is not None and ms_end is not None
    assert ms_start < ms_mid < ms_end
    assert ms_end > 500_000


def test_verify_against_segments_returns_false_for_missing_quote() -> None:
    ok, start_ms = verify_against_segments(
        "not in transcript",
        [{"start_ms": 0, "end_ms": 1_000, "text": "actual words"}],
    )

    assert not ok
    assert start_ms is None
