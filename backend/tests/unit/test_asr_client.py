from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

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
    def _request_file_submit(
        self,
        audio_path: Path,
        language_hint: str | None,
        *,
        audio_url: str | None = None,
    ) -> dict[str, Any]:
        _ = audio_path, language_hint, audio_url
        return {
            "provider": "doubao",
            "mode": "file_data",
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


class FakeDoubaoHTTPClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> httpx.Response:
        self.calls.append({"url": url, "headers": headers, "json": json})
        request = httpx.Request("POST", url)
        if url.endswith("/submit"):
            return httpx.Response(
                200,
                headers={"X-Api-Status-Code": "20000000", "X-Tt-Logid": "log-1"},
                json={},
                request=request,
            )
        return httpx.Response(
            200,
            headers={"X-Api-Status-Code": "20000000"},
            json={
                "result": {
                    "utterances": [
                        {
                            "start_time": 1000,
                            "end_time": 2500,
                            "text": "完整长音频识别",
                            "additions": {"lid_lang": "speech_mand"},
                        }
                    ]
                }
            },
            request=request,
        )


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


def test_doubao_file_asr_uses_submit_query_for_public_audio_url(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.normalized.mp3"
    audio_path.write_bytes(b"fake")
    client = FakeDoubaoHTTPClient()

    segments = DoubaoASR(settings_for(), retry_attempts=1, client=client).transcribe(
        audio_path,
        "zh",
        "https://example.test/audio.mp3",
    )

    assert segments[0].text == "完整长音频识别"
    submit = client.calls[0]
    assert submit["headers"]["X-Api-Resource-Id"] == "volc.seedasr.auc"
    assert submit["json"]["audio"]["url"] == "https://example.test/audio.mp3"
    assert "data" not in submit["json"]["audio"]
    assert "codec" not in submit["json"]["audio"]


def test_doubao_file_asr_uses_base64_submit_for_local_audio(tmp_path: Path) -> None:
    audio_path = tmp_path / "audio.normalized.mp3"
    audio_path.write_bytes(b"fake")
    client = FakeDoubaoHTTPClient()

    segments = DoubaoASR(settings_for(), retry_attempts=1, client=client).transcribe(audio_path, "zh")

    assert segments[0].text == "完整长音频识别"
    call = client.calls[0]
    assert call["url"].endswith("/submit")
    assert call["headers"]["X-Api-Resource-Id"] == "volc.seedasr.auc"
    assert call["json"]["audio"]["data"] == "ZmFrZQ=="
    assert "url" not in call["json"]["audio"]
    assert "codec" not in call["json"]["audio"]


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
