"""Preset-plus-note summary styling.

The submit modal lets the reader pick one preset, a detail level, and add a
short free-text note. All three are stored on the episode and assembled here
into the `style_directive` block that the summary prompts interpolate. Style
says *how* to write, detail says *how much*; they are independent axes. All
prompt text lives in `prompts/summary_style.v2.md` (Constitution V); this module
only selects and frames it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

STYLE_PROMPT_ROLE = "summary_style"
STYLE_PROMPT_VERSION = "v2"
DEFAULT_PRESET = "default"
MAX_NOTE_CHARS = 200
PRESETS: tuple[str, ...] = (
    "default",
    "study_notes",
    "business_insight",
    "debate",
    "quick_skim",
)

DEFAULT_DETAIL = "standard"
DETAIL_LEVELS: tuple[str, ...] = ("concise", "standard", "detailed")

HEADER_SECTION = "_header"
NOTE_SECTION = "_reader_note"

_SECTION_RE = re.compile(r"^## (\S+)[ \t]*$", re.MULTILINE)
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class StyleError(ValueError):
    """Rejected preset id, note, or malformed style prompt file."""


@dataclass(frozen=True)
class SummaryStyle:
    preset: str = DEFAULT_PRESET
    note: str | None = None
    detail: str = DEFAULT_DETAIL

    @property
    def is_default(self) -> bool:
        # "standard" detail is what the summary prompts already describe, so it
        # needs no directive of its own.
        return self.preset == DEFAULT_PRESET and not self.note and self.detail == DEFAULT_DETAIL


def sanitize_note(raw: object) -> str | None:
    """Normalize a reader note, or raise `StyleError` if it cannot be used."""
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise StyleError("style_note must be a string")
    # Newlines and control characters collapse to spaces so a note cannot forge
    # its own section or instruction block inside the assembled prompt.
    note = " ".join(_CONTROL_RE.sub(" ", raw).split())
    if not note:
        return None
    if len(note) > MAX_NOTE_CHARS:
        raise StyleError(f"style_note must be at most {MAX_NOTE_CHARS} characters")
    return note


def parse(preset: object = None, note: object = None, detail: object = None) -> SummaryStyle:
    """Validate untrusted request fields into a `SummaryStyle`."""
    if preset is None or preset == "":
        resolved = DEFAULT_PRESET
    elif isinstance(preset, str) and preset in PRESETS:
        resolved = preset
    else:
        raise StyleError(f"summary_style must be one of: {', '.join(PRESETS)}")
    if detail is None or detail == "":
        resolved_detail = DEFAULT_DETAIL
    elif isinstance(detail, str) and detail in DETAIL_LEVELS:
        resolved_detail = detail
    else:
        raise StyleError(f"detail_level must be one of: {', '.join(DETAIL_LEVELS)}")
    return SummaryStyle(preset=resolved, note=sanitize_note(note), detail=resolved_detail)


def split_sections(prompt_body: str) -> dict[str, str]:
    """Split the style prompt body into `## <id>` sections; text before the
    first heading is documentation and is dropped."""
    sections: dict[str, str] = {}
    matches = list(_SECTION_RE.finditer(prompt_body))
    for idx, match in enumerate(matches):
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(prompt_body)
        sections[match.group(1)] = prompt_body[match.end() : end].strip()
    return sections


def build_directive(prompt_body: str, style: SummaryStyle) -> str:
    """Render the directive block injected into the v2 summary prompts.

    Returns an empty string for the default style with no note, which keeps the
    v2 prompts equivalent to their v1 predecessors.
    """
    if style.is_default:
        return ""
    sections = split_sections(prompt_body)
    detail_section = detail_section_name(style.detail)
    required = [HEADER_SECTION, style.preset]
    if detail_section is not None:
        required.append(detail_section)
    if style.note:
        required.append(NOTE_SECTION)
    missing = [name for name in required if name not in sections]
    if missing:
        raise StyleError(f"summary_style prompt is missing sections: {', '.join(missing)}")

    parts = [sections[HEADER_SECTION]]
    if sections[style.preset]:
        parts.append(sections[style.preset])
    if detail_section is not None and sections[detail_section]:
        parts.append(sections[detail_section])
    if style.note:
        parts.append(sections[NOTE_SECTION].format(note=style.note))
    return "\n\n".join(parts) + "\n"


def detail_section_name(detail: str) -> str | None:
    """Section id for a detail level, or None for the level the prompts already
    describe."""
    return None if detail == DEFAULT_DETAIL else f"detail_{detail}"
