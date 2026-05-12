from __future__ import annotations

import re
import unicodedata
from typing import Any


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip()
    return re.sub(r"\s+", " ", normalized)


def verify(candidate_text: str, transcript_text: str) -> bool:
    candidate = _normalize(candidate_text)
    transcript = _normalize(transcript_text)
    return bool(candidate) and candidate in transcript


def verify_against_segments(candidate: str, segments: list[Any]) -> tuple[bool, int | None]:
    candidate_text = _normalize(candidate)
    if not candidate_text:
        return False, None

    transcript, spans = _normalized_transcript_with_spans(segments)
    match_index = transcript.find(candidate_text)
    if match_index < 0:
        return False, None

    for seg_start, seg_end, start_ms, end_ms in spans:
        if seg_start <= match_index < seg_end:
            seg_text_len = max(seg_end - seg_start, 1)
            seg_duration = max(end_ms - start_ms, 0)
            offset_in_seg = match_index - seg_start
            interpolated = start_ms + int(offset_in_seg / seg_text_len * seg_duration)
            return True, interpolated
    return True, spans[0][2] if spans else None


def _normalized_transcript_with_spans(
    segments: list[Any],
) -> tuple[str, list[tuple[int, int, int, int]]]:
    """Return (joined_transcript, spans) where each span is
    (char_offset_start, char_offset_end, start_ms, end_ms)."""
    pieces: list[str] = []
    spans: list[tuple[int, int, int, int]] = []
    cursor = 0
    for segment in segments:
        text = _normalize(_field(segment, "text"))
        start_ms = _int_field(segment, "start_ms")
        end_ms = _int_field(segment, "end_ms")
        if not text or start_ms is None or end_ms is None:
            continue
        if pieces:
            pieces.append(" ")
            cursor += 1
        seg_start_offset = cursor
        pieces.append(text)
        cursor += len(text)
        spans.append((seg_start_offset, cursor, start_ms, end_ms))
    return "".join(pieces), spans


def _field(segment: Any, name: str) -> str:
    value = segment.get(name) if isinstance(segment, dict) else getattr(segment, name, "")
    return value if isinstance(value, str) else ""


def _int_field(segment: Any, name: str) -> int | None:
    value = segment.get(name) if isinstance(segment, dict) else getattr(segment, name, None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
