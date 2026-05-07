from __future__ import annotations

import json
from typing import Any, Protocol

import httpx
from pydantic import BaseModel
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt

from podsum.config import LLMProvider, Settings


class LLMResponseError(RuntimeError):
    """Raised when a provider response is missing a usable JSON payload."""


class LLMClient(Protocol):
    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        raise NotImplementedError


class UnimplementedLLMClient:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        raise NotImplementedError(f"LLM provider is not implemented yet: {self.provider}")


class DeepSeekLLM:
    def __init__(
        self,
        settings: Settings,
        *,
        client: Any | None = None,
        retry_attempts: int = 3,
    ) -> None:
        from openai import (
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            OpenAI,
            RateLimitError,
        )

        self.settings = settings
        self.retry_attempts = retry_attempts
        self.retryable_errors = (
            APIConnectionError,
            APITimeoutError,
            InternalServerError,
            RateLimitError,
        )
        self.client = client or OpenAI(
            api_key=_secret_value(settings.DEEPSEEK_API_KEY),
            base_url=settings.DEEPSEEK_BASE_URL,
        )

    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        for attempt in Retrying(
            retry=retry_if_exception_type(self.retryable_errors),
            stop=stop_after_attempt(self.retry_attempts),
            reraise=True,
        ):
            with attempt:
                response = self.client.chat.completions.create(
                    model=self.settings.DEEPSEEK_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                )
                content = _openai_message_content(response)
        return _validate_json_payload(content, schema)


class QwenLLM:
    def __init__(
        self,
        settings: Settings,
        *,
        generation_api: Any | None = None,
        retry_attempts: int = 3,
    ) -> None:
        from dashscope import Generation

        self.settings = settings
        self.retry_attempts = retry_attempts
        self.generation_api = generation_api or Generation

    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        for attempt in Retrying(
            retry=retry_if_exception_type((httpx.HTTPError, TimeoutError)),
            stop=stop_after_attempt(self.retry_attempts),
            reraise=True,
        ):
            with attempt:
                response = self.generation_api.call(
                    model=self.settings.QWEN_LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    api_key=_secret_value(self.settings.DASHSCOPE_API_KEY),
                    result_format="message",
                    response_format={"type": "json_object"},
                )
                content = _qwen_message_content(response)
        return _validate_json_payload(content, schema)


class AnthropicLLM:
    endpoint = "https://api.anthropic.com/v1/messages"

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        retry_attempts: int = 3,
    ) -> None:
        self.settings = settings
        self.retry_attempts = retry_attempts
        self.client = client or httpx.Client(timeout=60.0)

    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        for attempt in Retrying(
            retry=retry_if_exception_type(httpx.HTTPError),
            stop=stop_after_attempt(self.retry_attempts),
            reraise=True,
        ):
            with attempt:
                response = self.client.post(
                    self.endpoint,
                    headers={
                        "x-api-key": _secret_value(self.settings.ANTHROPIC_API_KEY),
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": self.settings.ANTHROPIC_MODEL,
                        "max_tokens": 4000,
                        "messages": [{"role": "user", "content": prompt}],
                    },
                )
                response.raise_for_status()
                content = _anthropic_message_content(response.json())
        return _validate_json_payload(content, schema)


def create_llm_client(settings: Settings) -> LLMClient:
    provider: LLMProvider = settings.LLM_PROVIDER
    if provider == "deepseek":
        return DeepSeekLLM(settings)
    if provider == "qwen":
        return QwenLLM(settings)
    if provider == "anthropic":
        return AnthropicLLM(settings)
    return UnimplementedLLMClient(provider)


def _validate_json_payload(content: Any, schema: type[BaseModel]) -> dict[str, Any]:
    if isinstance(content, str):
        try:
            payload = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LLMResponseError("LLM response content was not valid JSON") from exc
    elif isinstance(content, dict):
        payload = content
    else:
        raise LLMResponseError("LLM response content was missing")
    return schema.model_validate(payload).model_dump()


def _openai_message_content(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError) as exc:
        raise LLMResponseError("OpenAI-compatible response had no message content") from exc
    if isinstance(content, list):
        content = "".join(str(item) for item in content)
    if not isinstance(content, str) or not content.strip():
        raise LLMResponseError("OpenAI-compatible response content was empty")
    return content


def _qwen_message_content(response: Any) -> str:
    payload = _to_plain_data(response)
    output = payload.get("output", {}) if isinstance(payload, dict) else {}
    if isinstance(output.get("text"), str):
        return output["text"]
    choices = output.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    raise LLMResponseError("Qwen response had no message content")


def _anthropic_message_content(payload: dict[str, Any]) -> str:
    content_items = payload.get("content")
    if not isinstance(content_items, list):
        raise LLMResponseError("Anthropic response had no content blocks")
    for item in content_items:
        if isinstance(item, dict) and isinstance(item.get("text"), str) and item["text"].strip():
            return item["text"]
    raise LLMResponseError("Anthropic response had no text content")


def _to_plain_data(value: Any) -> Any:
    if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if hasattr(value, "__dict__"):
        return {key: _to_plain_data(item) for key, item in value.__dict__.items() if not key.startswith("_")}
    return value


def _secret_value(value: Any) -> str:
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    if value is None:
        return ""
    return str(value)
