from __future__ import annotations

import asyncio
import gzip
import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

from tenacity import AsyncRetrying, Retrying, stop_after_attempt

from podsum.config import ASRProvider, Settings
from podsum.persistence.models import TranscriptSegment


class ASRClient(Protocol):
    def transcribe(self, audio_path: Path, language_hint: str | None) -> list[TranscriptSegment]:
        raise NotImplementedError


class UnimplementedASRClient:
    def __init__(self, provider: str) -> None:
        self.provider = provider

    def transcribe(self, audio_path: Path, language_hint: str | None) -> list[TranscriptSegment]:
        raise NotImplementedError(f"ASR provider is not implemented yet: {self.provider}")


class ASRResponseError(RuntimeError):
    """Raised when a provider returns a payload that cannot satisfy the transcript contract."""


class DoubaoASR:
    endpoint = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"
    resource_id = "volc.bigasr.sauc.duration"
    chunk_size_bytes = 64 * 1024
    final_timeout_seconds = 60.0

    def __init__(self, settings: Settings, *, retry_attempts: int = 3) -> None:
        self.settings = settings
        self.retry_attempts = retry_attempts
        self.sdk_api = _build_volcengine_speech_api(settings)

    def transcribe(self, audio_path: Path, language_hint: str | None) -> list[TranscriptSegment]:
        return _run_async_blocking(self.transcribe_async(audio_path, language_hint))

    async def transcribe_async(
        self,
        audio_path: Path,
        language_hint: str | None,
    ) -> list[TranscriptSegment]:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(self.retry_attempts),
            reraise=True,
        ):
            with attempt:
                raw_response = await self._request_raw(audio_path, language_hint)
        self._persist_raw_response(audio_path, raw_response)
        return parse_segments(raw_response, language_hint=language_hint)

    async def _request_raw(self, audio_path: Path, language_hint: str | None) -> dict[str, Any]:
        try:
            from websockets.asyncio.client import connect
        except ImportError as exc:  # pragma: no cover - dependency is pulled in by uvicorn[standard]
            raise RuntimeError("websockets is required for Doubao ASR") from exc

        request_id = str(uuid.uuid4())
        headers = {
            "X-Api-App-Key": self._required_value(
                self.settings.DOUBAO_ASR_APP_ID,
                "DOUBAO_ASR_APP_ID",
            ),
            "X-Api-Access-Key": self._required_value(
                self.settings.DOUBAO_ASR_ACCESS_TOKEN,
                "DOUBAO_ASR_ACCESS_TOKEN",
            ),
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Connect-Id": request_id,
        }
        responses: list[dict[str, Any]] = []

        async with connect(
            self.endpoint,
            additional_headers=headers,
            max_size=1_000_000_000,
            compression=None,
        ) as websocket:
            await websocket.send(
                _build_client_frame(
                    _doubao_init_payload(audio_path, language_hint),
                    message_type=_MessageType.FULL_CLIENT_REQUEST,
                    flags=_MessageFlag.POS_SEQUENCE,
                    sequence=1,
                )
            )
            await self._drain_available(websocket, responses)

            sequence = 2
            with audio_path.open("rb") as source:
                chunk = source.read(self.chunk_size_bytes)
                while chunk:
                    next_chunk = source.read(self.chunk_size_bytes)
                    is_last = not next_chunk
                    await websocket.send(
                        _build_client_frame(
                            chunk,
                            message_type=_MessageType.AUDIO_ONLY_REQUEST,
                            flags=(
                                _MessageFlag.NEG_SEQUENCE
                                if is_last
                                else _MessageFlag.POS_SEQUENCE
                            ),
                            sequence=-sequence if is_last else sequence,
                        )
                    )
                    await self._drain_available(websocket, responses)
                    chunk = next_chunk
                    sequence += 1

            final_response = await self._recv_until_final(websocket, responses)

        return {
            "provider": "doubao",
            "request_id": request_id,
            "endpoint": self.endpoint,
            "resource_id": self.resource_id,
            "responses": responses,
            "result": final_response.get("result", final_response),
        }

    async def _drain_available(self, websocket: Any, responses: list[dict[str, Any]]) -> None:
        while True:
            try:
                frame = await asyncio.wait_for(websocket.recv(), timeout=0.01)
            except TimeoutError:
                return
            responses.append(_parse_server_frame(frame))

    async def _recv_until_final(
        self,
        websocket: Any,
        responses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        while True:
            frame = await asyncio.wait_for(websocket.recv(), timeout=self.final_timeout_seconds)
            payload = _parse_server_frame(frame)
            responses.append(payload)
            if _has_final_result(payload):
                return payload

    def _persist_raw_response(self, audio_path: Path, raw_response: dict[str, Any]) -> None:
        raw_path = audio_path.parent / "transcript.raw.json"
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(
            json.dumps(raw_response, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    @staticmethod
    def _required_value(value: Any, name: str) -> str:
        if hasattr(value, "get_secret_value"):
            value = value.get_secret_value()
        if value is None or not str(value).strip():
            raise ValueError(f"{name} is required for Doubao ASR")
        return str(value)


class WhisperASR:
    def __init__(self, settings: Settings, *, retry_attempts: int = 3) -> None:
        from openai import OpenAI

        self.settings = settings
        self.retry_attempts = retry_attempts
        self.client = OpenAI(api_key=_secret_value(settings.OPENAI_API_KEY))

    def transcribe(self, audio_path: Path, language_hint: str | None) -> list[TranscriptSegment]:
        for attempt in Retrying(stop=stop_after_attempt(self.retry_attempts), reraise=True):
            with attempt:
                with audio_path.open("rb") as audio_file:
                    response = self.client.audio.transcriptions.create(
                        file=audio_file,
                        model="whisper-1",
                        response_format="verbose_json",
                        timestamp_granularities=["segment"],
                        language=_openai_language(language_hint),
                    )
                raw_response = _to_plain_data(response)
                _write_raw_response(audio_path, "openai_whisper", raw_response)
                return parse_segments(raw_response, language_hint=language_hint)
        raise ASRResponseError("OpenAI Whisper transcription did not return")


class QwenASR:
    def __init__(self, settings: Settings, *, retry_attempts: int = 3) -> None:
        from dashscope.audio.qwen_asr import QwenTranscription

        self.settings = settings
        self.retry_attempts = retry_attempts
        self.transcription_api = QwenTranscription

    def transcribe(self, audio_path: Path, language_hint: str | None) -> list[TranscriptSegment]:
        for attempt in Retrying(stop=stop_after_attempt(self.retry_attempts), reraise=True):
            with attempt:
                response = self.transcription_api.call(
                    model="qwen-audio-asr",
                    file_url=audio_path.resolve().as_uri(),
                    api_key=_secret_value(self.settings.DASHSCOPE_API_KEY),
                    language_hints=[language_hint] if language_hint else None,
                )
                raw_response = _to_plain_data(response)
                _write_raw_response(audio_path, "qwen", raw_response)
                return parse_segments(raw_response, language_hint=language_hint)
        raise ASRResponseError("Qwen ASR transcription did not return")


def create_asr_client(settings: Settings) -> ASRClient:
    provider: ASRProvider = settings.ASR_PROVIDER
    if provider == "doubao":
        return DoubaoASR(settings)
    if provider == "openai_whisper":
        return WhisperASR(settings)
    if provider == "qwen":
        return QwenASR(settings)
    return UnimplementedASRClient(provider)


def parse_segments(raw_response: Any, *, language_hint: str | None = None) -> list[TranscriptSegment]:
    payload = _to_plain_data(raw_response)
    utterances = _find_first_list(
        payload,
        keys=("utterances", "segments", "sentences", "transcripts"),
    )
    if not utterances:
        raise ASRResponseError("ASR response did not contain segment-level timestamps")

    segments: list[TranscriptSegment] = []
    for item in utterances:
        if not isinstance(item, dict):
            continue
        text = _first_present(item, "text", "sentence", "transcript")
        if not isinstance(text, str) or not text.strip():
            continue
        start_key, start_value = _first_present_with_key(
            item,
            "start_ms",
            "start_time",
            "begin_time",
            "start",
        )
        end_key, end_value = _first_present_with_key(
            item,
            "end_ms",
            "end_time",
            "stop_time",
            "end",
        )
        start_ms = _coerce_time_to_ms(start_value, key=start_key)
        end_ms = _coerce_time_to_ms(end_value, key=end_key)
        if start_ms is None or end_ms is None or end_ms <= start_ms:
            continue
        segments.append(
            TranscriptSegment(
                idx=len(segments),
                start_ms=start_ms,
                end_ms=end_ms,
                text=text.strip(),
                language=_normalize_language(
                    _first_present(item, "language", "lang", "language_tag")
                    or _first_present(item.get("additions", {}), "lid_lang", "lang")
                    or language_hint
                ),
            )
        )

    if not segments:
        raise ASRResponseError("ASR response contained no usable transcript segments")
    return segments


def _build_volcengine_speech_api(settings: Settings) -> Any:
    from volcenginesdkcore import ApiClient
    from volcenginesdkcore.configuration import Configuration
    from volcenginesdkspeechsaasprod import SPEECHSAASPRODApi

    configuration = Configuration()
    configuration.ak = _secret_value(settings.VOLC_ACCESS_KEY_ID)
    configuration.sk = _secret_value(settings.VOLC_SECRET_ACCESS_KEY)
    configuration.region = "cn-north-1"
    return SPEECHSAASPRODApi(ApiClient(configuration))


def _doubao_init_payload(audio_path: Path, language_hint: str | None) -> dict[str, Any]:
    language = _doubao_language(language_hint)
    audio_format = "mp3" if audio_path.suffix.lower() == ".mp3" else audio_path.suffix.lower().lstrip(".")
    audio: dict[str, Any] = {
        "format": audio_format,
        "codec": "raw",
        "rate": 16000,
        "bits": 16,
        "channel": 1,
    }
    if language is not None:
        audio["language"] = language

    return {
        "user": {"uid": "podsum"},
        "audio": audio,
        "request": {
            "model_name": "bigmodel",
            "enable_itn": True,
            "enable_punc": True,
            "enable_ddc": False,
            "show_utterances": True,
            "enable_lid": True,
            "result_type": "full",
        },
    }


class _MessageType:
    FULL_CLIENT_REQUEST = 0b0001
    AUDIO_ONLY_REQUEST = 0b0010
    FULL_SERVER_RESPONSE = 0b1001
    SERVER_ACK = 0b1011
    SERVER_ERROR = 0b1111


class _MessageFlag:
    NO_SEQUENCE = 0b0000
    POS_SEQUENCE = 0b0001
    NEG_SEQUENCE = 0b0011


class _Serialization:
    NONE = 0b0000
    JSON = 0b0001


class _Compression:
    NONE = 0b0000
    GZIP = 0b0001


def _build_client_frame(
    payload: dict[str, Any] | bytes,
    *,
    message_type: int,
    flags: int,
    sequence: int,
) -> bytes:
    if isinstance(payload, dict):
        payload_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        serialization = _Serialization.JSON
    else:
        payload_bytes = payload
        serialization = _Serialization.NONE

    compressed = gzip.compress(payload_bytes)
    header = bytes(
        [
            (0b0001 << 4) | 0b0001,
            (message_type << 4) | flags,
            (serialization << 4) | _Compression.GZIP,
            0,
        ]
    )
    return b"".join(
        [
            header,
            int(sequence).to_bytes(4, "big", signed=True),
            len(compressed).to_bytes(4, "big"),
            compressed,
        ]
    )


def _parse_server_frame(frame: bytes | str) -> dict[str, Any]:
    if isinstance(frame, str):
        return json.loads(frame)
    if len(frame) < 4:
        raise ASRResponseError("ASR server frame is too short")

    header_size = (frame[0] & 0x0F) * 4
    message_type = frame[1] >> 4
    flags = frame[1] & 0x0F
    serialization = frame[2] >> 4
    compression = frame[2] & 0x0F
    cursor = header_size
    result: dict[str, Any] = {"message_type": message_type, "flags": flags}

    if flags in {_MessageFlag.POS_SEQUENCE, _MessageFlag.NEG_SEQUENCE} and len(frame) >= cursor + 4:
        result["sequence"] = int.from_bytes(frame[cursor : cursor + 4], "big", signed=True)
        cursor += 4

    if message_type == _MessageType.SERVER_ERROR and len(frame) >= cursor + 8:
        result["error_code"] = int.from_bytes(frame[cursor : cursor + 4], "big")
        cursor += 4

    if len(frame) < cursor + 4:
        return result
    payload_size = int.from_bytes(frame[cursor : cursor + 4], "big")
    cursor += 4
    payload = frame[cursor : cursor + payload_size]
    if compression == _Compression.GZIP:
        payload = gzip.decompress(payload)

    if serialization == _Serialization.JSON:
        payload_data = json.loads(payload.decode("utf-8"))
        if message_type == _MessageType.SERVER_ERROR:
            result["error"] = payload_data
        else:
            result.update(payload_data if isinstance(payload_data, dict) else {"payload": payload_data})
    else:
        result["payload"] = payload.decode("utf-8", errors="replace")
    if message_type == _MessageType.SERVER_ERROR:
        raise ASRResponseError(f"Doubao ASR server error: {result}")
    return result


def _has_final_result(payload: dict[str, Any]) -> bool:
    result = payload.get("result")
    if isinstance(result, dict) and (result.get("utterances") or result.get("text")):
        return True
    if payload.get("utterances") or payload.get("segments"):
        return True
    return False


def _run_async_blocking(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(lambda: asyncio.run(coro)).result()


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


def _write_raw_response(audio_path: Path, provider: str, raw_response: Any) -> None:
    payload = {"provider": provider, "result": _to_plain_data(raw_response)}
    raw_path = audio_path.parent / "transcript.raw.json"
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _find_first_list(value: Any, *, keys: tuple[str, ...]) -> list[Any] | None:
    value = _to_plain_data(value)
    if isinstance(value, list):
        if value and all(isinstance(item, dict) and _looks_like_segment(item) for item in value):
            return value
        for item in value:
            found = _find_first_list(item, keys=keys)
            if found:
                return found
        return None
    if not isinstance(value, dict):
        return None
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, list):
            return candidate
    for candidate in value.values():
        found = _find_first_list(candidate, keys=keys)
        if found:
            return found
    return None


def _looks_like_segment(item: dict[str, Any]) -> bool:
    return any(key in item for key in ("text", "sentence", "transcript")) and any(
        key in item for key in ("start_ms", "start_time", "begin_time", "start")
    )


def _first_present(mapping: Any, *keys: str) -> Any:
    if not isinstance(mapping, dict):
        return None
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return value
    return None


def _first_present_with_key(mapping: Any, *keys: str) -> tuple[str | None, Any]:
    if not isinstance(mapping, dict):
        return None, None
    for key in keys:
        value = mapping.get(key)
        if value is not None:
            return key, value
    return None, None


def _coerce_time_to_ms(value: Any, *, key: str | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if key in {"start", "end"}:
        numeric *= 1000
    return int(round(numeric))


def _normalize_language(value: Any) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().lower().replace("_", "-")
    if not normalized:
        return None
    if normalized.startswith("en") or "speech-en" in normalized or normalized.endswith("-en"):
        return "en"
    if (
        normalized.startswith("zh")
        or normalized.startswith("yue")
        or "mand" in normalized
        or "cant" in normalized
        or "dia-" in normalized
    ):
        return "zh"
    return None


def _doubao_language(language_hint: str | None) -> str | None:
    if language_hint == "zh":
        return "zh-CN"
    if language_hint == "en":
        return "en-US"
    return None


def _openai_language(language_hint: str | None) -> str | None:
    if language_hint in {"zh", "en"}:
        return language_hint
    return None


def _secret_value(value: Any) -> str:
    if hasattr(value, "get_secret_value"):
        return value.get_secret_value()
    if value is None:
        return ""
    return str(value)
