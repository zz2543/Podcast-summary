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

    transcript, start_offsets = _normalized_transcript_with_offsets(segments)
    match_index = transcript.find(candidate_text)
    if match_index < 0:
        return False, None

    for offset, start_ms in reversed(start_offsets):
        if match_index >= offset:
            return True, start_ms
    return True, start_offsets[0][1] if start_offsets else None


def _normalized_transcript_with_offsets(segments: list[Any]) -> tuple[str, list[tuple[int, int]]]:
    pieces: list[str] = []
    start_offsets: list[tuple[int, int]] = []
    cursor = 0
    for segment in segments:
        text = _normalize(_field(segment, "text"))
        start_ms = _int_field(segment, "start_ms")
        if not text or start_ms is None:
            continue
        if pieces:
            pieces.append(" ")
            cursor += 1
        start_offsets.append((cursor, start_ms))
        pieces.append(text)
        cursor += len(text)
    return "".join(pieces), start_offsets


def _field(segment: Any, name: str) -> str:
    value = segment.get(name) if isinstance(segment, dict) else getattr(segment, name, "")
    return value if isinstance(value, str) else ""


def _int_field(segment: Any, name: str) -> int | None:
    value = segment.get(name) if isinstance(segment, dict) else getattr(segment, name, None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
