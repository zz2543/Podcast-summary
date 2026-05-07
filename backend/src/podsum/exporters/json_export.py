from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

SCHEMA_PATH = (
    Path(__file__).resolve().parents[4]
    / "specs"
    / "001-podcast-summary"
    / "contracts"
    / "episode-output.schema.json"
)
EPISODE_OUTPUT_SCHEMA: dict[str, Any] = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def render(episode_detail: Any) -> dict[str, Any]:
    episode = _value(episode_detail, "episode")
    artifact = _value(episode_detail, "artifact")
    stage_status = _stage_status(_value(artifact, "stage_status") or {})
    prompt_versions = _prompt_versions(_value(artifact, "prompt_versions") or {})

    return {
        "id": _value(episode, "id"),
        "title": _value(episode, "title"),
        "podcast_name": _value(episode, "podcast_name"),
        "guests": _value(episode, "guests"),
        "source_type": _value(episode, "source_type"),
        "source_ref": _value(episode, "source_ref"),
        "duration_seconds": _value(episode, "duration_seconds"),
        "language": _value(episode, "language"),
        "status": _value(episode, "status"),
        "stage_status": stage_status,
        "prompt_versions": prompt_versions,
        "hook": _value(artifact, "hook") if stage_status["hook"] == "present" else None,
        "three_act": (
            _value(artifact, "three_act") if stage_status["three_act"] == "present" else None
        ),
        "chapters": _plain_list(_value(episode_detail, "chapters")),
        "entities": _plain_list(_value(episode_detail, "entities")),
        "artifact_paths": {
            "markdown": _value(artifact, "markdown_path"),
            "json": _value(artifact, "json_path"),
            "tts": _value(artifact, "tts_path"),
        },
        "created_at": _isoformat(_value(episode, "created_at")),
        "updated_at": _isoformat(_value(episode, "updated_at")),
    }


def _value(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


def _plain_list(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _stage_status(values: dict[str, str]) -> dict[str, str]:
    return {
        "hook": values.get("hook", "missing"),
        "three_act": values.get("three_act", "missing"),
        "chapters": values.get("chapters", "missing"),
        "entities": values.get("entities", "missing"),
        "tts": values.get("tts", "missing"),
    }


def _prompt_versions(values: dict[str, str]) -> dict[str, str]:
    return {
        "one_liner": values.get("one_liner", "v1"),
        "three_act": values.get("three_act", "v1"),
        "chapter_outline": values.get("chapter_outline", "v1"),
        "entity_extraction": values.get("entity_extraction", "v1"),
    }


def _isoformat(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return None
