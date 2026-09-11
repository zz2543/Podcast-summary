"""Which language the summary should be written in.

ASR providers label each utterance on its own, so a Chinese episode that drops
in English product names ("Codex", "Electron") comes back with a handful of
segments tagged `en`. Deciding the episode language by set union then yields
`mixed`, which used to be interpolated straight into the prompts as
"Summarize this podcast in mixed." — and the model answered in English. Both
helpers here weigh actual characters instead of labels.
"""

from __future__ import annotations

from typing import Any

Language = str

# A minority language has to carry at least this share of the content before the
# episode counts as genuinely bilingual rather than as one language with
# borrowed terms.
MIXED_THRESHOLD = 0.2

# One CJK character carries roughly a whole word; a Latin letter does not.
# Comparing raw character counts would call a Chinese sentence with three
# English product names in it an English sentence.
LATIN_LETTERS_PER_WORD = 4.7

LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "zh": "Simplified Chinese (the language spoken in this episode; do not translate it)",
    "en": "English (the language spoken in this episode; do not translate it)",
}


def character_counts(segments: list[Any]) -> tuple[int, int]:
    """(CJK characters, Latin letters) across every segment's text."""
    cjk = latin = 0
    for segment in segments:
        for char in _text(segment):
            if "\u4e00" <= char <= "\u9fff":
                cjk += 1
            elif char.isascii() and char.isalpha():
                latin += 1
    return cjk, latin


def weighted_counts(segments: list[Any]) -> tuple[float, float]:
    """Character counts converted to comparable word-sized units."""
    cjk, latin = character_counts(segments)
    return float(cjk), latin / LATIN_LETTERS_PER_WORD


def dominant(segments: list[Any], fallback: str = "en") -> Language:
    """The single language to write in. Never returns `mixed`."""
    zh_units, en_units = weighted_counts(segments)
    if zh_units == 0 and en_units == 0:
        return fallback if fallback in LANGUAGE_INSTRUCTIONS else "en"
    return "zh" if zh_units >= en_units else "en"


def classify(segments: list[Any]) -> Language | None:
    """Episode-level language stored on the row: `zh`, `en`, `mixed`, or None."""
    zh_units, en_units = weighted_counts(segments)
    total = zh_units + en_units
    if total == 0:
        return None
    if min(zh_units, en_units) / total >= MIXED_THRESHOLD:
        return "mixed"
    return "zh" if zh_units >= en_units else "en"


def instruction(code: str | None, segments: list[Any] | None = None) -> str:
    """Prompt-ready phrase for the `{lang}` slot.

    `mixed` and unknown codes resolve through the character counts, so a prompt
    never receives a language name the model cannot write in.
    """
    if code in LANGUAGE_INSTRUCTIONS:
        return LANGUAGE_INSTRUCTIONS[code]
    resolved = dominant(segments or [], fallback="en")
    return LANGUAGE_INSTRUCTIONS[resolved]


def _text(segment: Any) -> str:
    value = segment.get("text") if isinstance(segment, dict) else getattr(segment, "text", "")
    return value if isinstance(value, str) else ""
