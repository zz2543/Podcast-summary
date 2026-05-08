from __future__ import annotations

import json
import re
import unicodedata
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator


class RetriableValidationError(ValueError):
    """Raised when the LLM output is structurally valid enough to retry with a hint."""


class ThreeAct(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background: str
    core_argument: str
    conclusion: str

    @field_validator("background", "core_argument", "conclusion")
    @classmethod
    def non_empty(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("field must not be empty")
        return cleaned


class CandidateQuote(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    start_ms: int

    @field_validator("text")
    @classmethod
    def quote_text_non_empty(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("quote text must not be empty")
        return cleaned


class ChapterDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    key_points: list[str]
    candidate_quotes: list[CandidateQuote] = []

    @field_validator("title")
    @classmethod
    def title_non_empty(cls, value: str) -> str:
        cleaned = _clean_text(value)
        if not cleaned:
            raise ValueError("chapter title must not be empty")
        return cleaned

    @field_validator("key_points")
    @classmethod
    def key_points_non_empty(cls, value: list[str]) -> list[str]:
        cleaned = [_clean_text(item) for item in value if _clean_text(item)]
        if not cleaned:
            raise ValueError("chapter key_points must not be empty")
        return cleaned


def parse_one_liner(raw_json: Any, episode_title: str, lang: str) -> str:
    payload = _payload_dict(raw_json)
    value = payload.get("hook")
    if not isinstance(value, str):
        raise RetriableValidationError("one-liner payload must contain string key 'hook'")

    hook = _clean_text(value)
    if not hook:
        raise RetriableValidationError("one-liner hook must not be empty")
    if _similarity_ratio(hook, episode_title) > 0.6:
        raise RetriableValidationError("one-liner hook is too similar to episode title")
    _ = lang
    return hook


def parse_three_act(raw_json: Any) -> ThreeAct:
    try:
        return ThreeAct.model_validate(_payload_dict(raw_json))
    except (ValidationError, RetriableValidationError) as exc:
        raise RetriableValidationError("three-act payload failed validation") from exc


def parse_chapter_payload(raw_json: Any) -> list[ChapterDraft]:
    payload = _payload(raw_json)
    raw_chapters = payload.get("chapters") if isinstance(payload, dict) else payload
    if not isinstance(raw_chapters, list):
        raise RetriableValidationError("chapter payload must contain a chapters list")
    try:
        chapters = [ChapterDraft.model_validate(item) for item in raw_chapters]
    except ValidationError as exc:
        raise RetriableValidationError("chapter payload failed validation") from exc
    if not chapters:
        raise RetriableValidationError("chapter payload must contain at least one chapter")
    return chapters


def _payload_dict(raw_json: Any) -> dict[str, Any]:
    if isinstance(raw_json, dict):
        return raw_json
    if isinstance(raw_json, str):
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RetriableValidationError("LLM output must be valid JSON") from exc
        if isinstance(payload, dict):
            return payload
    raise RetriableValidationError("LLM output must be a JSON object")


def _payload(raw_json: Any) -> Any:
    if isinstance(raw_json, (dict, list)):
        return raw_json
    if isinstance(raw_json, str):
        try:
            return json.loads(raw_json)
        except json.JSONDecodeError as exc:
            raise RetriableValidationError("LLM output must be valid JSON") from exc
    raise RetriableValidationError("LLM output must be valid JSON")


def _clean_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return re.sub(r"\s+", " ", normalized).strip()


def _similarity_ratio(left: str, right: str) -> float:
    normalized_left = _normalize_for_similarity(left)
    normalized_right = _normalize_for_similarity(right)
    if not normalized_left or not normalized_right:
        return 0.0
    distance = _levenshtein_distance(normalized_left, normalized_right)
    return 1 - distance / max(len(normalized_left), len(normalized_right))


def _normalize_for_similarity(value: str) -> str:
    cleaned = _clean_text(value).casefold()
    return re.sub(r"\W+", "", cleaned)


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]
