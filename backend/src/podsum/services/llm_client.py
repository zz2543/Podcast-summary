from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel

from podsum.config import Settings


class LLMClient(Protocol):
    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        raise NotImplementedError


class UnimplementedLLMClient:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def complete_json(self, prompt: str, schema: type[BaseModel]) -> dict[str, Any]:
        raise NotImplementedError(f"LLM provider is not implemented yet: {self.provider}")


def create_llm_client(settings: Settings) -> LLMClient:
    return UnimplementedLLMClient(settings.LLM_PROVIDER)
