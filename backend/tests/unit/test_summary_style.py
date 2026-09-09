from __future__ import annotations

from pathlib import Path

import pytest

from podsum.domain.prompt_assembler import PromptAssembler
from podsum.domain.summary_style import (
    DEFAULT_PRESET,
    MAX_NOTE_CHARS,
    PRESETS,
    STYLE_PROMPT_ROLE,
    STYLE_PROMPT_VERSION,
    StyleError,
    SummaryStyle,
    build_directive,
    parse,
    sanitize_note,
    split_sections,
)

PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


@pytest.fixture(scope="module")
def style_body() -> str:
    return PromptAssembler(PROMPTS_DIR).load(STYLE_PROMPT_ROLE, STYLE_PROMPT_VERSION).body


def test_parse_defaults_to_default_preset() -> None:
    style = parse(None, None)
    assert style == SummaryStyle(preset=DEFAULT_PRESET, note=None)
    assert style.is_default


def test_parse_accepts_every_shipped_preset() -> None:
    for preset in PRESETS:
        assert parse(preset, None).preset == preset


def test_parse_rejects_unknown_preset() -> None:
    with pytest.raises(StyleError):
        parse("hacker_mode", None)


def test_parse_rejects_non_string_preset() -> None:
    with pytest.raises(StyleError):
        parse(7, None)


def test_note_collapses_newlines_and_control_characters() -> None:
    assert sanitize_note("focus on\n\nmethodology\tplease") == "focus on methodology please"


def test_blank_note_becomes_none() -> None:
    assert sanitize_note("   \n  ") is None
    assert parse("debate", "  ").is_default is False


def test_note_over_limit_is_rejected() -> None:
    with pytest.raises(StyleError):
        sanitize_note("x" * (MAX_NOTE_CHARS + 1))


def test_note_at_limit_is_accepted() -> None:
    assert sanitize_note("x" * MAX_NOTE_CHARS) == "x" * MAX_NOTE_CHARS


def test_default_style_yields_no_directive(style_body: str) -> None:
    assert build_directive(style_body, parse(None, None)) == ""


def test_preset_directive_includes_header_and_preset_text(style_body: str) -> None:
    sections = split_sections(style_body)
    directive = build_directive(style_body, parse("study_notes", None))
    assert sections["_header"] in directive
    assert sections["study_notes"] in directive
    assert sections["business_insight"] not in directive


def test_note_is_quoted_inside_the_directive(style_body: str) -> None:
    directive = build_directive(style_body, parse("quick_skim", "skip the ads"))
    assert '"skip the ads"' in directive


def test_default_preset_with_note_still_produces_a_directive(style_body: str) -> None:
    directive = build_directive(style_body, parse("default", "keep it dry"))
    assert directive
    assert '"keep it dry"' in directive


def test_missing_section_is_reported(style_body: str) -> None:
    del style_body  # this case needs a deliberately broken body
    with pytest.raises(StyleError, match="missing sections"):
        build_directive("## default\n", SummaryStyle(preset="study_notes"))


def test_every_preset_has_a_section_in_the_prompt_file(style_body: str) -> None:
    sections = split_sections(style_body)
    assert set(PRESETS) <= set(sections)
    assert {"_header", "_reader_note"} <= set(sections)


def test_v2_prompts_render_with_a_directive_slot() -> None:
    assembler = PromptAssembler(PROMPTS_DIR)
    directive = build_directive(
        assembler.load(STYLE_PROMPT_ROLE, STYLE_PROMPT_VERSION).body,
        parse("debate", "name the two camps"),
    )
    rendered = assembler.render(
        "three_act_summary",
        "v2",
        lang="en",
        style_directive=directive,
        transcript="hello",
    )
    assert "name the two camps" in rendered
    assert "hello" in rendered
