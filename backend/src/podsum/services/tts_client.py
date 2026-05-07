from __future__ import annotations

from pathlib import Path
from typing import Protocol

from podsum.config import Settings


class TTSClient(Protocol):
    def synthesize(self, text: str, lang: str, out_path: Path) -> None:
        raise NotImplementedError


class UnimplementedTTSClient:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def synthesize(self, text: str, lang: str, out_path: Path) -> None:
        raise NotImplementedError(f"TTS provider is not implemented yet: {self.provider}")


def create_tts_client(settings: Settings) -> TTSClient:
    return UnimplementedTTSClient(settings.TTS_PROVIDER)
