from __future__ import annotations

import re
import unicodedata


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).strip()
    return re.sub(r"\s+", " ", normalized)


def verify(candidate_text: str, transcript_text: str) -> bool:
    candidate = _normalize(candidate_text)
    transcript = _normalize(transcript_text)
    return bool(candidate) and candidate in transcript
