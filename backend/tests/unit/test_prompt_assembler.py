from __future__ import annotations

from pathlib import Path

import pytest

from podsum.domain.prompt_assembler import (
    PromptAssembler,
    PromptNotFoundError,
    PromptValidationError,
    find_inline_prompt_violations,
)


def write_prompt(root: Path, name: str, body: str, frontmatter: str | None = None) -> Path:
    frontmatter = frontmatter or "role: one_liner\nversion: v1\nlang_aware: true"
    path = root / name
    path.write_text(f"---\n{frontmatter}\n---\n{body}", encoding="utf-8")
    return path


def test_load_by_role_and_version(tmp_path: Path) -> None:
    write_prompt(tmp_path, "one_liner.v1.md", "Summarize {transcript} in {lang}.")

    template = PromptAssembler(tmp_path).load("one_liner", "v1")

    assert template.role == "one_liner"
    assert template.version == "v1"
    assert template.metadata["lang_aware"] is True


def test_missing_version_raises(tmp_path: Path) -> None:
    write_prompt(tmp_path, "one_liner.v1.md", "Body", "role: one_liner")

    with pytest.raises(PromptValidationError, match="version"):
        PromptAssembler(tmp_path).load("one_liner", "v1")


def test_slot_substitution(tmp_path: Path) -> None:
    write_prompt(tmp_path, "one_liner.v1.md", "{episode_title}: {transcript} [{lang}]")

    rendered = PromptAssembler(tmp_path).render(
        "one_liner",
        "v1",
        episode_title="Episode 1",
        transcript="hello",
        lang="en",
    )

    assert rendered == "Episode 1: hello [en]"


def test_missing_slot_raises(tmp_path: Path) -> None:
    write_prompt(tmp_path, "one_liner.v1.md", "{episode_title}: {transcript}")

    with pytest.raises(PromptValidationError, match="transcript"):
        PromptAssembler(tmp_path).render("one_liner", "v1", episode_title="Episode 1")


def test_frontmatter_validation(tmp_path: Path) -> None:
    (tmp_path / "one_liner.v1.md").write_text("No frontmatter", encoding="utf-8")

    with pytest.raises(PromptValidationError, match="frontmatter"):
        PromptAssembler(tmp_path).load("one_liner", "v1")


def test_missing_prompt_raises(tmp_path: Path) -> None:
    with pytest.raises(PromptNotFoundError):
        PromptAssembler(tmp_path).load("one_liner", "v1")


def test_inline_prompt_scan_flags_prompt_like_strings(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text(
        "PROMPT = 'Summarize this podcast transcript as JSON for the assistant "
        "with enough detail to exceed the inline limit.'\n",
        encoding="utf-8",
    )

    assert find_inline_prompt_violations(tmp_path) == [f"{source}:1"]
