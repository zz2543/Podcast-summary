from __future__ import annotations

from podsum.domain.chapter_segmenter import segment


def test_short_audio_has_at_least_one_chapter() -> None:
    spans = segment(
        [
            {"start_ms": 0, "end_ms": 8_000, "text": "A short introduction."},
            {"start_ms": 8_200, "end_ms": 20_000, "text": "The main point follows."},
        ]
    )

    assert len(spans) == 1
    assert spans[0].start_ms == 0
    assert spans[0].end_ms == 20_000


def test_long_silence_creates_non_zero_chapters() -> None:
    spans = segment(
        [
            {"start_ms": 0, "end_ms": 120_000, "text": "Opening context."},
            {"start_ms": 122_000, "end_ms": 240_000, "text": "Now the first main idea."},
            {"start_ms": 242_000, "end_ms": 360_000, "text": "Next comes the second idea."},
        ],
        target_minutes=2,
    )

    assert len(spans) >= 2
    assert all(item.end_ms > item.start_ms for item in spans)


def test_ordering_is_preserved_in_text_windows() -> None:
    spans = segment(
        [
            {"start_ms": 0, "end_ms": 70_000, "text": "first"},
            {"start_ms": 70_000, "end_ms": 140_000, "text": "second"},
            {"start_ms": 142_000, "end_ms": 210_000, "text": "finally third"},
        ],
        target_minutes=1,
    )

    combined = " ".join(span.text_window for span in spans)
    assert combined.index("first") < combined.index("second") < combined.index("third")


def test_timestamps_are_monotonic() -> None:
    spans = segment(
        [
            {"start_ms": 0, "end_ms": 100_000, "text": "first block"},
            {"start_ms": 101_800, "end_ms": 210_000, "text": "another block"},
            {"start_ms": 211_700, "end_ms": 320_000, "text": "finally the last block"},
        ],
        target_minutes=1,
    )

    assert [span.idx for span in spans] == list(range(len(spans)))
    for previous, current in zip(spans, spans[1:], strict=False):
        assert previous.end_ms <= current.start_ms
