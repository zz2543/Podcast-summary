from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from podsum.config import Settings
from podsum.services.asr_client import (
    DoubaoASR,
    QwenASR,
    UnimplementedASRClient,
    WhisperASR,
    create_asr_client,
    parse_segments,
)


def settings_for(*, asr_provider: str = "doubao") -> Settings:
    return Settings(
        _env_file=None,
        ASR_PROVIDER=asr_provider,
        VOLC_ACCESS_KEY_ID="ak",
        VOLC_SECRET_ACCESS_KEY="sk",
        DOUBAO_ASR_APP_ID="asr-app",
        DOUBAO_ASR_ACCESS_TOKEN="asr-token",
        DEEPSEEK_API_KEY="deepseek",
        DOUBAO_TTS_APP_ID="tts-app",
        DOUBAO_TTS_ACCESS_TOKEN="tts-token",
        OPENAI_API_KEY="openai",
        DEEPGRAM_API_KEY="deepgram",
        DASHSCOPE_API_KEY="dashscope",
    )


class FakeDoubaoASR(DoubaoASR):
    async def _request_raw(self, audio_path: Path, language_hint: str | None) -> dict[str, Any]:
        return {
            "provider": "doubao",
            "result": {
                "utterances": [
                    {
                        "start_time": 0,
                        "end_time": 1705,
                        "text": "这是字节跳动，",
                        "additions": {"lid_lang": "speech_mand"},
                    },
                    {
                        "start_time": 2110,
                        "end_time": 3696,
                        "text": "Today is the headline.",
                        "additions": {"lid_lang": "speech_en"},
                    },
                ]
            },
        }


def test_doubao_transcribe_persists_raw_response(tmp_path: Path) -> None:
    audio_path = tmp_path / "01ARZ3NDEKTSV4RRFFQ69G5FAV" / "audio.normalized.mp3"
    audio_path.parent.mkdir()
    audio_path.write_bytes(b"fake")

    segments = FakeDoubaoASR(settings_for()).transcribe(audio_path, "zh")

    assert [(item.start_ms, item.end_ms, item.text, item.language) for item in segments] == [
        (0, 1705, "这是字节跳动，", "zh"),
        (2110, 3696, "Today is the headline.", "en"),
    ]
    raw = json.loads((audio_path.parent / "transcript.raw.json").read_text(encoding="utf-8"))
    assert raw["provider"] == "doubao"


def test_parse_segments_accepts_openai_second_offsets() -> None:
    segments = parse_segments(
        {
            "segments": [
                {
                    "start": 1.25,
                    "end": 2.75,
                    "text": " hello world ",
                    "language": "en",
                }
            ]
        }
    )

    assert segments[0].start_ms == 1250
    assert segments[0].end_ms == 2750
    assert segments[0].text == "hello world"


def test_create_asr_client_selects_registered_providers() -> None:
    assert isinstance(create_asr_client(settings_for(asr_provider="doubao")), DoubaoASR)
    assert isinstance(create_asr_client(settings_for(asr_provider="openai_whisper")), WhisperASR)
    assert isinstance(create_asr_client(settings_for(asr_provider="qwen")), QwenASR)
    assert isinstance(create_asr_client(settings_for(asr_provider="deepgram")), UnimplementedASRClient)
