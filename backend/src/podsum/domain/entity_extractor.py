from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

from podsum.domain.prompt_assembler import PromptAssembler

EntityKind = Literal["person", "book", "product"]


class JsonLLM(Protocol):
    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        raise NotImplementedError


@dataclass(frozen=True)
class Entity:
    name: str
    kind: EntityKind
    count: int
    sample_timestamps_ms: list[int]


class _LLMEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    kind: EntityKind
    count: int = Field(default=1, ge=0)

    @field_validator("name")
    @classmethod
    def name_non_empty(cls, value: str) -> str:
        cleaned = _normalize(value)
        if not cleaned:
            raise ValueError("entity name must not be empty")
        return cleaned


class _EntityPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entities: list[_LLMEntity]


def extract(transcript_segments: list[Any], llm: JsonLLM) -> list[Entity]:
    transcript = _transcript_text(transcript_segments)
    prompt = PromptAssembler().render(
        "entity_extraction",
        "v1",
        lang=_language_hint(transcript),
        transcript=transcript,
    )
    payload = llm.complete_json(prompt, _EntityPayload)
    parsed = _EntityPayload.model_validate(payload)

    entities: dict[tuple[str, EntityKind], Entity] = {}
    for item in parsed.entities:
        key = (item.name, item.kind)
        if key in entities:
            continue
        count, samples = _count_mentions(item.name, transcript_segments)
        if count <= 0:
            continue
        entities[key] = Entity(
            name=item.name,
            kind=item.kind,
            count=count,
            sample_timestamps_ms=samples[:5],
        )
    return sorted(entities.values(), key=lambda entity: (entity.kind, entity.name))


def _count_mentions(name: str, segments: list[Any]) -> tuple[int, list[int]]:
    pattern = re.compile(re.escape(_normalize(name)))
    count = 0
    samples: list[int] = []
    for segment in segments:
        text = _normalize(_field(segment, "text"))
        start_ms = _int_field(segment, "start_ms")
        matches = list(pattern.finditer(text))
        if not matches:
            continue
        count += len(matches)
        if start_ms is not None and len(samples) < 5:
            samples.append(start_ms)
    return count, samples


def _transcript_text(segments: list[Any]) -> str:
    return " ".join(
        text for text in (_normalize(_field(segment, "text")) for segment in segments) if text
    )


def _language_hint(transcript: str) -> str:
    cjk_count = sum("\u4e00" <= char <= "\u9fff" for char in transcript)
    latin_count = sum(char.isascii() and char.isalpha() for char in transcript)
    if cjk_count and latin_count:
        return "mixed"
    if cjk_count:
        return "zh"
    return "en"


def _normalize(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", value)).strip()


def _field(segment: Any, name: str) -> str:
    value = segment.get(name) if isinstance(segment, dict) else getattr(segment, name, "")
    return value if isinstance(value, str) else ""


def _int_field(segment: Any, name: str) -> int | None:
    value = segment.get(name) if isinstance(segment, dict) else getattr(segment, name, None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
