from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from podsum.config import Settings
from podsum.services.llm_client import (
    AnthropicLLM,
    DeepSeekLLM,
    QwenLLM,
    create_llm_client,
)


class Payload(BaseModel):
    value: str


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.kwargs: dict[str, Any] = {}

    def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def settings_for(*, llm_provider: str = "deepseek") -> Settings:
    return Settings(
        _env_file=None,
        LLM_PROVIDER=llm_provider,
        VOLC_ACCESS_KEY_ID="ak",
        VOLC_SECRET_ACCESS_KEY="sk",
        DOUBAO_ASR_APP_ID="asr-app",
        DOUBAO_ASR_ACCESS_TOKEN="asr-token",
        DEEPSEEK_API_KEY="deepseek",
        DOUBAO_TTS_APP_ID="tts-app",
        DOUBAO_TTS_ACCESS_TOKEN="tts-token",
        DASHSCOPE_API_KEY="dashscope",
        ANTHROPIC_API_KEY="anthropic",
        ANTHROPIC_MODEL="claude-test",
    )


def test_deepseek_complete_json_uses_json_mode_and_validates_schema() -> None:
    completions = FakeCompletions('{"value": "ok"}')
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    result = DeepSeekLLM(settings_for(), client=fake_client).complete_json("prompt", Payload)

    assert result == {"value": "ok"}
    assert completions.kwargs["model"] == "deepseek-chat"
    assert completions.kwargs["response_format"] == {"type": "json_object"}
    assert completions.kwargs["messages"] == [{"role": "user", "content": "prompt"}]


def test_deepseek_complete_json_rejects_schema_mismatch() -> None:
    completions = FakeCompletions('{"other": "bad"}')
    fake_client = SimpleNamespace(chat=SimpleNamespace(completions=completions))

    with pytest.raises(ValidationError):
        DeepSeekLLM(settings_for(), client=fake_client).complete_json("prompt", Payload)


def test_create_llm_client_selects_registered_providers() -> None:
    assert isinstance(create_llm_client(settings_for(llm_provider="deepseek")), DeepSeekLLM)
    assert isinstance(create_llm_client(settings_for(llm_provider="qwen")), QwenLLM)
    assert isinstance(create_llm_client(settings_for(llm_provider="anthropic")), AnthropicLLM)
