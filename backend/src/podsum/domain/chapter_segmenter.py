from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ChapterSpan:
    idx: int
    start_ms: int
    end_ms: int
    text_window: str


TOPIC_SHIFT_RE = re.compile(
    r"\b(now|next|finally|first|second|third|another|moving on|let's talk)\b|"
    r"(接下来|然后|首先|其次|最后|另一个|换个话题|回到)",
    re.IGNORECASE,
)


def segment(transcript_segments: list[Any], target_minutes: int = 10) -> list[ChapterSpan]:
    cleaned = [_segment_from_any(item) for item in transcript_segments]
    segments = [item for item in cleaned if item is not None]
    if not segments:
        return []

    target_ms = max(target_minutes, 1) * 60_000
    episode_start = segments[0].start_ms
    episode_end = max(segment.end_ms for segment in segments)
    if episode_end <= episode_start:
        return []

    boundaries = _natural_boundaries(segments, target_ms)
    if not boundaries:
        boundaries = _even_boundaries(episode_start, episode_end, target_ms)

    spans: list[ChapterSpan] = []
    chapter_start = episode_start
    for boundary in boundaries:
        if boundary <= chapter_start:
            continue
        text_window = _window_text(segments, chapter_start, boundary)
        if text_window:
            spans.append(
                ChapterSpan(
                    idx=len(spans),
                    start_ms=chapter_start,
                    end_ms=boundary,
                    text_window=text_window,
                )
            )
        chapter_start = boundary

    if chapter_start < episode_end:
        text_window = _window_text(segments, chapter_start, episode_end)
        if text_window:
            spans.append(
                ChapterSpan(
                    idx=len(spans),
                    start_ms=chapter_start,
                    end_ms=episode_end,
                    text_window=text_window,
                )
            )

    return spans or [ChapterSpan(idx=0, start_ms=episode_start, end_ms=episode_end, text_window=_join_text(segments))]


def _natural_boundaries(segments: list[ChapterSpan], target_ms: int) -> list[int]:
    boundaries: list[int] = []
    last_boundary = segments[0].start_ms
    for previous, current in zip(segments, segments[1:], strict=False):
        gap_ms = current.start_ms - previous.end_ms
        elapsed_ms = current.start_ms - last_boundary
        if elapsed_ms < target_ms * 0.55:
            continue
        if gap_ms >= 1_500 or TOPIC_SHIFT_RE.search(current.text_window):
            boundaries.append(current.start_ms)
            last_boundary = current.start_ms
            continue
        if elapsed_ms >= target_ms * 1.4:
            boundaries.append(current.start_ms)
            last_boundary = current.start_ms
    return boundaries


def _even_boundaries(start_ms: int, end_ms: int, target_ms: int) -> list[int]:
    if end_ms - start_ms <= target_ms:
        return []
    boundaries: list[int] = []
    boundary = start_ms + target_ms
    while boundary < end_ms:
        boundaries.append(boundary)
        boundary += target_ms
    return boundaries


def _window_text(segments: list[ChapterSpan], start_ms: int, end_ms: int) -> str:
    return " ".join(
        segment.text_window
        for segment in segments
        if segment.end_ms > start_ms and segment.start_ms < end_ms and segment.text_window
    ).strip()


def _join_text(segments: list[ChapterSpan]) -> str:
    return " ".join(segment.text_window for segment in segments if segment.text_window).strip()


def _segment_from_any(value: Any) -> ChapterSpan | None:
    start_ms = _int_field(value, "start_ms")
    end_ms = _int_field(value, "end_ms")
    text = _text_field(value, "text")
    if start_ms is None or end_ms is None or end_ms <= start_ms or not text:
        return None
    return ChapterSpan(idx=0, start_ms=start_ms, end_ms=end_ms, text_window=text)


def _int_field(value: Any, field: str) -> int | None:
    raw_value = value.get(field) if isinstance(value, dict) else getattr(value, field, None)
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _text_field(value: Any, field: str) -> str:
    raw_value = value.get(field) if isinstance(value, dict) else getattr(value, field, None)
    if not isinstance(raw_value, str):
        return ""
    return re.sub(r"\s+", " ", raw_value).strip()
