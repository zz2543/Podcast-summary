from __future__ import annotations

from podsum.domain.transcript_postprocess import normalize


def test_pure_chinese_segments_merge_and_nfkc_normalize() -> None:
    segments = normalize(
        [
            {"start_ms": 0, "end_ms": 500, "text": "  这是ＡＩ  ", "language": "zh"},
            {"start_ms": 500, "end_ms": 900, "text": "播客", "language": "zh"},
        ],
        language_hint=None,
    )

    assert len(segments) == 1
    assert segments[0].text == "这是AI播客"
    assert segments[0].language == "zh"
    assert segments[0].start_ms == 0
    assert segments[0].end_ms == 900


def test_pure_english_segments_merge_with_single_space() -> None:
    segments = normalize(
        [
            {"start_ms": 0, "end_ms": 400, "text": " hello   world ", "language": "en"},
            {"start_ms": 400, "end_ms": 800, "text": " from podcast ", "language": "en"},
        ],
        language_hint=None,
    )

    assert len(segments) == 1
    assert segments[0].text == "hello world from podcast"
    assert segments[0].language == "en"


def test_mixed_code_switched_segments_keep_language_boundaries() -> None:
    segments = normalize(
        [
            {"start_ms": 0, "end_ms": 500, "text": "欢迎回来", "language": None},
            {"start_ms": 500, "end_ms": 900, "text": "open source", "language": None},
            {"start_ms": 900, "end_ms": 1300, "text": "继续聊", "language": None},
        ],
        language_hint=None,
    )

    assert [(item.text, item.language) for item in segments] == [
        ("欢迎回来", "zh"),
        ("open source", "en"),
        ("继续聊", "zh"),
    ]


def test_leading_trailing_and_repeated_space_collapsed() -> None:
    segments = normalize(
        [{"start_ms": 0, "end_ms": 500, "text": "\n  hello\t\tworld  \n", "language": None}],
        language_hint="en",
    )

    assert segments[0].text == "hello world"


def test_zero_length_segments_are_dropped() -> None:
    segments = normalize(
        [
            {"start_ms": 0, "end_ms": 0, "text": "bad", "language": "en"},
            {"start_ms": 0, "end_ms": 100, "text": "   ", "language": "en"},
            {"start_ms": 100, "end_ms": 200, "text": "good", "language": "en"},
        ],
        language_hint=None,
    )

    assert len(segments) == 1
    assert segments[0].text == "good"
    assert segments[0].idx == 0


def test_ordering_is_preserved_after_drops_and_merges() -> None:
    segments = normalize(
        [
            {"start_ms": 1000, "end_ms": 1200, "text": "second", "language": "en"},
            {"start_ms": 1200, "end_ms": 1300, "text": "", "language": "en"},
            {"start_ms": 500, "end_ms": 900, "text": "第一句", "language": "zh"},
        ],
        language_hint=None,
    )

    assert [(item.idx, item.start_ms, item.text, item.language) for item in segments] == [
        (0, 1000, "second", "en"),
        (1, 500, "第一句", "zh"),
    ]
