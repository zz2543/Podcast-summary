from __future__ import annotations

from pathlib import Path
from typing import Protocol

from podsum.config import Settings
from podsum.persistence.models import TranscriptSegment


class ASRClient(Protocol):
    def transcribe(self, audio_path: Path, language_hint: str | None) -> list[TranscriptSegment]:
        raise NotImplementedError


class UnimplementedASRClient:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def transcribe(self, audio_path: Path, language_hint: str | None) -> list[TranscriptSegment]:
        raise NotImplementedError(f"ASR provider is not implemented yet: {self.provider}")


def create_asr_client(settings: Settings) -> ASRClient:
    return UnimplementedASRClient(settings.ASR_PROVIDER)
