from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from podsum.domain.entity_extractor import extract


class FakeLLM:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.prompt = ""

    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        self.prompt = prompt
        return schema.model_validate(self.payload).model_dump()


def test_entity_extractor_corrects_llm_count() -> None:
    llm = FakeLLM({"entities": [{"name": "Apple", "kind": "product", "count": 5}]})
    entities = extract(
        [
            {"start_ms": 0, "text": "Apple released a product."},
            {"start_ms": 10_000, "text": "Apple discussed Apple Intelligence."},
        ],
        llm,
    )

    assert entities[0].count == 3
    assert entities[0].sample_timestamps_ms == [0, 10_000]


def test_entity_extractor_preserves_classification() -> None:
    llm = FakeLLM(
        {
            "entities": [
                {"name": "Steve Jobs", "kind": "person", "count": 1},
                {"name": "The Innovators", "kind": "book", "count": 1},
            ]
        }
    )
    entities = extract(
        [{"start_ms": 0, "text": "Steve Jobs appears in The Innovators."}],
        llm,
    )

    assert {(entity.name, entity.kind) for entity in entities} == {
        ("Steve Jobs", "person"),
        ("The Innovators", "book"),
    }


def test_entity_extractor_dedupes_by_name_and_kind() -> None:
    llm = FakeLLM(
        {
            "entities": [
                {"name": "Notion", "kind": "product", "count": 99},
                {"name": "Notion", "kind": "product", "count": 1},
            ]
        }
    )
    entities = extract(
        [{"start_ms": 0, "text": "Notion connects to Notion databases."}],
        llm,
    )

    assert len(entities) == 1
    assert entities[0].count == 2


def test_entity_extractor_limits_sample_timestamps() -> None:
    llm = FakeLLM({"entities": [{"name": "DeepSeek", "kind": "product", "count": 7}]})
    segments = [
        {"start_ms": index * 1_000, "text": "DeepSeek appears here."}
        for index in range(7)
    ]

    entities = extract(segments, llm)

    assert entities[0].count == 7
    assert entities[0].sample_timestamps_ms == [0, 1_000, 2_000, 3_000, 4_000]
