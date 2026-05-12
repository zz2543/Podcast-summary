from __future__ import annotations

import base64
import json
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
        token = _required_secret(self.settings.DOUBAO_TTS_ACCESS_TOKEN, "DOUBAO_TTS_ACCESS_TOKEN")
        chunks = _split_text_for_tts(text, max_bytes=900)
        audio_parts: list[bytes] = []
        for chunk in chunks:
            request = self._request_payload(chunk, lang)
            for attempt in Retrying(
                retry=retry_if_exception_type((httpx.HTTPError, TTSResponseError)),
                stop=stop_after_attempt(self.retry_attempts),
                reraise=True,
            ):
                with attempt:
                    response = self.client.post(
                        self.endpoint,
                        headers={"Authorization": f"Bearer;{token}"},
                        json=request,
                    )
                    if response.status_code >= 400:
                        raise TTSResponseError(
                            f"Doubao TTS HTTP {response.status_code}: {response.text[:500]}"
                        )
                    audio_parts.append(_doubao_audio_bytes(response))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"".join(audio_parts))

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


class DoubaoBigTTS:
    """豆包语音合成大模型2.0 (BigTTS / SeedTTS 2.0) via WebSocket bidirection.

    Uses ``wss://openspeech.bytedance.com/api/v3/tts/bidirection`` with the
    three ``X-Api-*`` auth headers. Speakers are the ``*_uranus_bigtts``
    voices visible under "音色详情" in the BigTTS console listing.

    Protocol is a binary framed message format (see
    :mod:`podsum.services._doubao_bigtts_protocol`). The high-level flow is:

        StartConnection  → ConnectionStarted
        StartSession     → SessionStarted
        TaskRequest      → (server streams AudioOnlyServer chunks)
        FinishSession    → ... SessionFinished
        FinishConnection → ConnectionFinished

    The whole synthesized MP3 is built by concatenating ``AudioOnlyServer``
    payloads. Synthesize is exposed as a sync method (the pipeline stage is
    sync) but the WebSocket work happens in a fresh background event loop on
    a daemon thread to avoid interfering with the FastAPI loop.
    """

    def __init__(
        self,
        settings: Settings,
        *,
        retry_attempts: int = 3,
    ) -> None:
        self.settings = settings
        self.retry_attempts = retry_attempts

    def synthesize(self, text: str, lang: str, out_path: Path) -> None:
        import threading

        result: dict[str, Any] = {}

        def runner() -> None:
            import asyncio

            try:
                result["audio"] = asyncio.run(self._synthesize_async(text, lang))
            except BaseException as exc:  # noqa: BLE001 — propagate cross-thread
                result["error"] = exc

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        thread.join()
        if "error" in result:
            raise result["error"]
        audio = result["audio"]
        if not isinstance(audio, bytes) or not audio:
            raise TTSResponseError("Doubao BigTTS returned no audio bytes")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio)

    async def _synthesize_async(self, text: str, lang: str) -> bytes:
        import websockets

        from podsum.services._doubao_bigtts_protocol import (
            EventType,
            MsgType,
            finish_connection,
            finish_session,
            receive_message,
            start_connection,
            start_session,
            task_request,
            wait_for_event,
        )

        app_id = _required_value(self.settings.DOUBAO_TTS_APP_ID, "DOUBAO_TTS_APP_ID")
        token = _required_secret(self.settings.DOUBAO_TTS_ACCESS_TOKEN, "DOUBAO_TTS_ACCESS_TOKEN")
        # Old console auth: App-Id + Access-Key + Resource-Id. The previously
        # circulated demo used "X-Api-App-Key" but the official docs name it
        # "X-Api-App-Id"; the gateway accepts both, we use the doc name to be safe.
        headers = {
            "X-Api-App-Id": app_id,
            "X-Api-Access-Key": token,
            "X-Api-Resource-Id": self.settings.DOUBAO_TTS_BIGMODEL_RESOURCE_ID,
            "X-Api-Connect-Id": str(uuid.uuid4()),
        }

        last_error: BaseException | None = None
        for _ in range(self.retry_attempts):
            try:
                async with websockets.connect(
                    self.settings.DOUBAO_TTS_BIGMODEL_URL,
                    additional_headers=headers,
                    max_size=64 * 1024 * 1024,
                    open_timeout=30,
                    close_timeout=10,
                ) as websocket:
                    await start_connection(websocket)
                    await wait_for_event(
                        websocket, MsgType.FullServerResponse, EventType.ConnectionStarted
                    )

                    session_id = str(uuid.uuid4())
                    base_request = {
                        "user": {"uid": "podsum"},
                        "namespace": "BidirectionalTTS",
                        "req_params": {
                            "speaker": _voice_type(self.settings, lang),
                            "audio_params": {
                                "format": self.settings.DOUBAO_TTS_BIGMODEL_FORMAT,
                                "sample_rate": self.settings.DOUBAO_TTS_BIGMODEL_SAMPLE_RATE,
                            },
                        },
                    }
                    start_payload = {
                        **base_request,
                        "event": int(EventType.StartSession),
                    }
                    await start_session(
                        websocket,
                        json.dumps(start_payload).encode("utf-8"),
                        session_id,
                    )
                    await wait_for_event(
                        websocket, MsgType.FullServerResponse, EventType.SessionStarted
                    )

                    task_payload = {
                        **base_request,
                        "event": int(EventType.TaskRequest),
                        "req_params": {**base_request["req_params"], "text": text},
                    }
                    await task_request(
                        websocket,
                        json.dumps(task_payload).encode("utf-8"),
                        session_id,
                    )
                    await finish_session(websocket, session_id)

                    audio = bytearray()
                    while True:
                        msg = await receive_message(websocket)
                        if msg.type == MsgType.AudioOnlyServer:
                            audio.extend(msg.payload)
                        elif msg.type == MsgType.FullServerResponse:
                            if msg.event == EventType.SessionFinished:
                                break
                            if msg.event in (
                                EventType.SessionFailed,
                                EventType.ConnectionFailed,
                            ):
                                raise TTSResponseError(
                                    f"Doubao BigTTS session failed: {msg.payload!r}"
                                )
                        elif msg.type == MsgType.Error:
                            raise TTSResponseError(
                                f"Doubao BigTTS error frame "
                                f"(code={msg.error_code}): "
                                f"{msg.payload.decode('utf-8', 'ignore')[:500]}"
                            )

                    try:
                        await finish_connection(websocket)
                        await wait_for_event(
                            websocket,
                            MsgType.FullServerResponse,
                            EventType.ConnectionFinished,
                        )
                    except Exception:
                        # Connection finalisation is best-effort — we already have audio.
                        pass

                    if not audio:
                        raise TTSResponseError("Doubao BigTTS produced no audio chunks")
                    return bytes(audio)
            except TTSResponseError:
                raise
            except Exception as exc:  # noqa: BLE001
                last_error = exc

        if last_error is not None:
            raise TTSResponseError(
                f"Doubao BigTTS WebSocket failed after retries: {last_error!r}"
            ) from last_error
        raise TTSResponseError("Doubao BigTTS WebSocket failed with no error captured")


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
        if settings.DOUBAO_TTS_MODE == "bigmodel":
            return DoubaoBigTTS(settings)
        return DoubaoTTS(settings)
    if provider == "qwen":
        return QwenTTS(settings)
    return UnimplementedTTSClient(provider)


def _bigtts_audio_bytes(response: httpx.Response) -> bytes:
    """Extract MP3 bytes from a BigTTS 2.0 HTTP response.

    The v3 endpoint can return audio in several shapes depending on whether
    the server treats the request as one-shot or chunked stream. Handle the
    three documented cases: raw audio body, JSON envelope with base64 ``data``,
    or a sequence of newline-delimited JSON events each carrying a base64
    ``audio`` chunk. If the response body looks like none of those, surface
    the first 500 chars as an error so we can adjust without guesswork.
    """
    content_type = response.headers.get("content-type", "").lower()
    body = response.content
    if content_type.startswith("audio/") or _looks_like_mp3(body):
        return body
    text = response.text
    # Try newline-delimited JSON events (SSE-ish streaming response).
    chunks: list[bytes] = []
    saw_event = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line in {"[DONE]", "DONE"}:
            continue
        try:
            event = _json_loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        saw_event = True
        if event.get("code") not in (None, 0, 3000):
            raise TTSResponseError(f"Doubao BigTTS event error: {event}")
        audio_b64 = event.get("audio") or event.get("data")
        if isinstance(audio_b64, str) and audio_b64:
            try:
                chunks.append(base64.b64decode(audio_b64))
            except ValueError as exc:
                raise TTSResponseError("Doubao BigTTS returned invalid base64") from exc
    if chunks:
        return b"".join(chunks)
    if saw_event:
        raise TTSResponseError("Doubao BigTTS event stream contained no audio chunks")
    # Single JSON envelope fallback.
    try:
        payload = response.json()
    except ValueError as exc:
        raise TTSResponseError(
            f"Doubao BigTTS response not understood: {text[:500]}"
        ) from exc
    if isinstance(payload, dict):
        if payload.get("code") not in (None, 0, 3000):
            raise TTSResponseError(f"Doubao BigTTS failed: {payload}")
        data = payload.get("data") or (payload.get("payload") or {}).get("audio")
        if isinstance(data, str) and data:
            try:
                return base64.b64decode(data)
            except ValueError as exc:
                raise TTSResponseError("Doubao BigTTS returned invalid base64") from exc
    raise TTSResponseError(f"Doubao BigTTS response missing audio: {text[:500]}")


def _looks_like_mp3(data: bytes) -> bool:
    if len(data) < 4:
        return False
    return data[:3] == b"ID3" or (data[0] == 0xFF and (data[1] & 0xE0) == 0xE0)


def _json_loads(line: str) -> Any:
    import json

    return json.loads(line)


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


def _split_text_for_tts(text: str, *, max_bytes: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        candidate = f"{current}\n{line}" if current else line
        if len(candidate.encode("utf-8")) > max_bytes and current:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    final: list[str] = []
    for chunk in chunks:
        if len(chunk.encode("utf-8")) <= max_bytes:
            final.append(chunk)
            continue
        buf = ""
        for ch in chunk:
            if len((buf + ch).encode("utf-8")) > max_bytes:
                final.append(buf)
                buf = ch
            else:
                buf += ch
        if buf:
            final.append(buf)
    return final


def _voice_type(settings: Settings, lang: str) -> str:
    # Chinese-dominant or mixed-language content uses the ZH voice. Only
    # explicit English ("en") routes to the EN voice. Passing the EN voice an
    # all-Chinese script makes BigTTS silently drop it and return zero audio.
    normalized = (lang or "").strip().lower()
    if normalized == "en":
        return settings.DOUBAO_TTS_VOICE_TYPE_EN
    return settings.DOUBAO_TTS_VOICE_TYPE_ZH


def _required_value(value: Any, name: str) -> str:
    if value is None or not str(value).strip():
        raise ValueError(f"{name} is required for TTS")
    return str(value)


def _required_secret(value: Any, name: str) -> str:
    if hasattr(value, "get_secret_value"):
        value = value.get_secret_value()
    return _required_value(value, name)
