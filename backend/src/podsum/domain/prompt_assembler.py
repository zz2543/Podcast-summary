from __future__ import annotations

import ast
import re
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Any

VERSION_RE = re.compile(r"^v[0-9]+$")
PROMPT_HINTS = {
    "assistant",
    "episode",
    "json",
    "podcast",
    "prompt",
    "summarize",
    "transcript",
}


class PromptError(ValueError):
    pass


class PromptNotFoundError(PromptError):
    pass


class PromptValidationError(PromptError):
    pass


@dataclass(frozen=True)
class PromptTemplate:
    role: str
    version: str
    metadata: dict[str, Any]
    body: str

    def render(self, **slots: str) -> str:
        expected = {
            field_name
            for _, field_name, _, _ in string.Formatter().parse(self.body)
            if field_name
        }
        missing = sorted(expected - set(slots))
        if missing:
            raise PromptValidationError(f"missing prompt slots: {', '.join(missing)}")
        return self.body.format(**slots)


def parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        raise PromptValidationError("prompt frontmatter is required")

    end = raw.find("\n---", 4)
    if end == -1:
        raise PromptValidationError("prompt frontmatter is not closed")

    metadata: dict[str, Any] = {}
    for line in raw[4:end].splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if ":" not in stripped:
            raise PromptValidationError("invalid frontmatter line")
        key, value = stripped.split(":", 1)
        parsed: Any = value.strip()
        if parsed.lower() == "true":
            parsed = True
        elif parsed.lower() == "false":
            parsed = False
        metadata[key.strip()] = parsed

    body = raw[end + 4 :].lstrip("\n")
    return metadata, body


class PromptAssembler:
    def __init__(self, prompts_dir: Path | str = "prompts") -> None:
        self.prompts_dir = Path(prompts_dir)

    def load(self, role: str, version: str) -> PromptTemplate:
        if not VERSION_RE.fullmatch(version):
            raise PromptValidationError("prompt version must match vN")

        path = self.prompts_dir / f"{role}.{version}.md"
        if not path.exists():
            raise PromptNotFoundError(f"prompt not found: {path}")

        metadata, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if metadata.get("role") != role:
            raise PromptValidationError("prompt role does not match file name")
        if metadata.get("version") != version:
            raise PromptValidationError("prompt version does not match file name")
        if not body.strip():
            raise PromptValidationError("prompt body is empty")
        return PromptTemplate(role=role, version=version, metadata=metadata, body=body)

    def render(self, role: str, version: str, **slots: str) -> str:
        return self.load(role, version).render(**slots)


def find_inline_prompt_violations(source_root: Path | str = "backend/src") -> list[str]:
    violations: list[str] = []
    root = Path(source_root)
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            value = node.value.strip().lower()
            if len(node.value) <= 80:
                continue
            if any(hint in value for hint in PROMPT_HINTS):
                violations.append(f"{path}:{node.lineno}")
    return violations
