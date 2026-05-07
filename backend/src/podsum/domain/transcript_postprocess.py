from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

Language = Literal["zh", "en"]


@dataclass(frozen=True)
class NormalizedSegment:
    idx: int
    start_ms: int
    end_ms: int
    text: str
    language: Language


def normalize(raw_segments: list[Any], language_hint: str | None) -> list[NormalizedSegment]:
    normalized: list[NormalizedSegment] = []
    for raw_segment in raw_segments:
        start_ms = _int_field(raw_segment, "start_ms")
        end_ms = _int_field(raw_segment, "end_ms")
        text = _clean_text(_field(raw_segment, "text"))
        if start_ms is None or end_ms is None or end_ms <= start_ms or not text:
            continue

        language = _segment_language(_field(raw_segment, "language"), language_hint, text)
        if normalized and normalized[-1].language == language:
            previous = normalized[-1]
            normalized[-1] = NormalizedSegment(
                idx=previous.idx,
                start_ms=previous.start_ms,
                end_ms=max(previous.end_ms, end_ms),
                text=_join_text(previous.text, text, language),
                language=language,
            )
        else:
            normalized.append(
                NormalizedSegment(
                    idx=len(normalized),
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=text,
                    language=language,
                )
            )
    return normalized


def _field(raw_segment: Any, name: str) -> Any:
    if isinstance(raw_segment, dict):
        return raw_segment.get(name)
    return getattr(raw_segment, name, None)


def _int_field(raw_segment: Any, name: str) -> int | None:
    value = _field(raw_segment, name)
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()


def _segment_language(value: Any, language_hint: str | None, text: str) -> Language:
    explicit = _normalize_language(value)
    if explicit is not None:
        return explicit
    hinted = _normalize_language(language_hint)
    if hinted is not None:
        return hinted
    return _infer_language(text)


def _normalize_language(value: Any) -> Language | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("_", "-")
    if normalized.startswith("zh") or normalized.startswith("yue") or "mand" in normalized:
        return "zh"
    if normalized.startswith("en") or normalized.endswith("-en"):
        return "en"
    return None


def _infer_language(text: str) -> Language:
    cjk_count = sum("\u4e00" <= char <= "\u9fff" for char in text)
    latin_count = sum(char.isascii() and char.isalpha() for char in text)
    return "zh" if cjk_count and cjk_count >= latin_count else "en"


def _join_text(left: str, right: str, language: Language) -> str:
    separator = "" if language == "zh" else " "
    return _clean_text(f"{left}{separator}{right}")
