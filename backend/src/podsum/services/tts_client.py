from __future__ import annotations

import base64
import uuid
from pathlib import Path
from typing import Any, Protocol

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt

from podsum.config import Settings, TTSProvider
from podsum.services.asr_client import _build_volcengine_speech_api


class TTSClient(Protocol):
    def synthesize(self, text: str, lang: str, out_path: Path) -> None:
        raise NotImplementedError


class UnimplementedTTSClient:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def synthesize(self, text: str, lang: str, out_path: Path) -> None:
        raise NotImplementedError(f"TTS provider is not implemented yet: {self.provider}")


class TTSResponseError(RuntimeError):
    """Raised when a TTS provider response cannot be converted to MP3 bytes."""


class DoubaoTTS:
    endpoint = "https://openspeech.bytedance.com/api/v1/tts"

    def __init__(
        self,
        settings: Settings,
        *,
        client: httpx.Client | None = None,
        retry_attempts: int = 3,
    ) -> None:
        self.settings = settings
        self.retry_attempts = retry_attempts
        self.client = client or httpx.Client(timeout=120.0)
        self.sdk_api = _build_volcengine_speech_api(settings)

    def synthesize(self, text: str, lang: str, out_path: Path) -> None:
        request = self._request_payload(text, lang)
        token = _required_secret(self.settings.DOUBAO_TTS_ACCESS_TOKEN, "DOUBAO_TTS_ACCESS_TOKEN")
        for attempt in Retrying(
            retry=retry_if_exception_type((httpx.HTTPError, TTSResponseError)),
            stop=stop_after_attempt(self.retry_attempts),
            reraise=True,
        ):
            with attempt:
                response = self.client.post(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {token}"},
                    json=request,
                )
                response.raise_for_status()
                audio = _doubao_audio_bytes(response)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(audio)

    def _request_payload(self, text: str, lang: str) -> dict[str, Any]:
        return {
            "app": {
                "appid": _required_value(self.settings.DOUBAO_TTS_APP_ID, "DOUBAO_TTS_APP_ID"),
                "token": _required_secret(
                    self.settings.DOUBAO_TTS_ACCESS_TOKEN,
                    "DOUBAO_TTS_ACCESS_TOKEN",
                ),
                "cluster": self.settings.DOUBAO_TTS_CLUSTER,
            },
            "user": {"uid": "podsum"},
            "audio": {
                "voice_type": _voice_type(self.settings, lang),
                "encoding": "mp3",
                "speed_ratio": 1.0,
                "volume_ratio": 1.0,
                "pitch_ratio": 1.0,
            },
            "request": {
                "reqid": str(uuid.uuid4()),
                "text": text,
                "text_type": "plain",
                "operation": "query",
            },
        }


class QwenTTS:
    def __init__(
        self,
        settings: Settings,
        *,
        synthesizer_cls: Any | None = None,
        retry_attempts: int = 3,
    ) -> None:
        self.settings = settings
        self.retry_attempts = retry_attempts
        if synthesizer_cls is None:
            from dashscope.audio.tts_v2 import SpeechSynthesizer

            synthesizer_cls = SpeechSynthesizer
        self.synthesizer_cls = synthesizer_cls

    def synthesize(self, text: str, lang: str, out_path: Path) -> None:
        _ = lang
        for attempt in Retrying(stop=stop_after_attempt(self.retry_attempts), reraise=True):
            with attempt:
                synthesizer = self.synthesizer_cls(
                    model=self.settings.QWEN_TTS_MODEL,
                    voice=self.settings.QWEN_TTS_VOICE,
                    api_key=_required_secret(self.settings.DASHSCOPE_API_KEY, "DASHSCOPE_API_KEY"),
                )
                audio = synthesizer.call(text)
                if not isinstance(audio, bytes) or not audio:
                    raise TTSResponseError("Qwen TTS response did not contain audio bytes")
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(audio)


def create_tts_client(settings: Settings) -> TTSClient:
    provider: TTSProvider = settings.TTS_PROVIDER
    if provider == "doubao":
        return DoubaoTTS(settings)
    if provider == "qwen":
        return QwenTTS(settings)
    return UnimplementedTTSClient(provider)


def _doubao_audio_bytes(response: httpx.Response) -> bytes:
    content_type = response.headers.get("content-type", "")
    if content_type.startswith("audio/"):
        return response.content
    payload = response.json()
    if payload.get("code") not in (None, 0, 3000):
        raise TTSResponseError(f"Doubao TTS failed: {payload}")
    data = payload.get("data")
    if not isinstance(data, str) or not data:
        raise TTSResponseError("Doubao TTS response did not contain base64 audio data")
    try:
        return base64.b64decode(data)
    except ValueError as exc:
        raise TTSResponseError("Doubao TTS returned invalid base64 audio data") from exc


def _voice_type(settings: Settings, lang: str) -> str:
    return settings.DOUBAO_TTS_VOICE_TYPE_ZH if lang == "zh" else settings.DOUBAO_TTS_VOICE_TYPE_EN


def _required_value(value: Any, name: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"{name} is required for TTS")
    return str(value)


def _required_secret(value: Any, name: str) -> str:
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return _required_value(value, name)
