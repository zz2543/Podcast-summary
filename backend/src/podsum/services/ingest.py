from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx
import yt_dlp

from podsum.config import Settings
from podsum.persistence.models import new_ulid


MAX_FILE_BYTES = 1_000_000_000
MAX_DURATION_SECONDS = 21_600
CHUNK_SIZE = 1024 * 1024


class IngestError(ValueError):
    pass


class PayloadTooLarge(IngestError):
    pass


class UnsupportedMedia(IngestError):
    pass


class UploadLike(Protocol):
    filename: str | None

    async def read(self, size: int = -1) -> bytes:
        raise NotImplementedError


@dataclass(frozen=True)
class IngestedAudio:
    episode_id: str
    original_path: Path
    normalized_path: Path
    duration_seconds: int
    file_size_bytes: int
    detected_ext: str
    title: str | None = None
    podcast_name: str | None = None
    source_ref: str | None = None


async def ingest_local_file(upload: UploadLike, settings: Settings) -> IngestedAudio:
    episode_id = new_ulid()
    episode_dir = settings.DATA_DIR / episode_id
    episode_dir.mkdir(parents=True, exist_ok=False)
    original_tmp = episode_dir / "audio.original.upload"

    try:
        file_size = await _write_upload(upload, original_tmp)
        detected_ext = _detect_audio_ext(original_tmp)
        original_path = episode_dir / f"audio.original.{detected_ext}"
        original_tmp.rename(original_path)

        duration_seconds = await _probe_duration_seconds(original_path)
        if duration_seconds > MAX_DURATION_SECONDS:
            raise PayloadTooLarge("audio duration exceeds 6 hour limit")

        normalized_path = episode_dir / "audio.normalized.mp3"
        await _run_ffmpeg_normalize(original_path, normalized_path)
        return IngestedAudio(
            episode_id=episode_id,
            original_path=original_path,
            normalized_path=normalized_path,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size,
            detected_ext=detected_ext,
        )
    except Exception:
        shutil.rmtree(episode_dir, ignore_errors=True)
        raise


async def ingest_direct_url(url: str, settings: Settings) -> IngestedAudio:
    episode_id = new_ulid()
    episode_dir = settings.DATA_DIR / episode_id
    episode_dir.mkdir(parents=True, exist_ok=False)
    original_tmp = episode_dir / "audio.original.download"

    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=60.0) as client:
            head = await client.head(url)
            head.raise_for_status()
            _validate_audio_content_type(head.headers.get("content-type"))
            content_length = head.headers.get("content-length")
            if content_length is not None and int(content_length) > MAX_FILE_BYTES:
                raise PayloadTooLarge("audio file exceeds 1 GB limit")

            async with client.stream("GET", url) as response:
                response.raise_for_status()
                _validate_audio_content_type(response.headers.get("content-type"))
                file_size = await _write_response_stream(response, original_tmp)

        detected_ext = _detect_audio_ext(original_tmp)
        original_path = episode_dir / f"audio.original.{detected_ext}"
        original_tmp.rename(original_path)

        duration_seconds = await _probe_duration_seconds(original_path)
        if duration_seconds > MAX_DURATION_SECONDS:
            raise PayloadTooLarge("audio duration exceeds 6 hour limit")

        normalized_path = episode_dir / "audio.normalized.mp3"
        await _run_ffmpeg_normalize(original_path, normalized_path)
        return IngestedAudio(
            episode_id=episode_id,
            original_path=original_path,
            normalized_path=normalized_path,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size,
            detected_ext=detected_ext,
        )
    except Exception:
        shutil.rmtree(episode_dir, ignore_errors=True)
        raise


async def ingest_youtube(url: str, settings: Settings) -> IngestedAudio:
    episode_id = new_ulid()
    episode_dir = settings.DATA_DIR / episode_id
    episode_dir.mkdir(parents=True, exist_ok=False)

    try:
        info, original_path = await asyncio.to_thread(_download_youtube_audio, url, episode_dir)
        duration = info.get("duration")
        duration_seconds = int(round(float(duration))) if duration is not None else await _probe_duration_seconds(original_path)
        if duration_seconds > MAX_DURATION_SECONDS:
            raise PayloadTooLarge("audio duration exceeds 6 hour limit")

        file_size = original_path.stat().st_size
        if file_size > MAX_FILE_BYTES:
            raise PayloadTooLarge("audio file exceeds 1 GB limit")

        normalized_path = episode_dir / "audio.normalized.mp3"
        await _run_ffmpeg_normalize(original_path, normalized_path)
        return IngestedAudio(
            episode_id=episode_id,
            original_path=original_path,
            normalized_path=normalized_path,
            duration_seconds=duration_seconds,
            file_size_bytes=file_size,
            detected_ext=original_path.suffix.lstrip(".") or "mp3",
            title=info.get("title"),
            podcast_name=info.get("channel") or info.get("uploader"),
            source_ref=info.get("webpage_url") or url,
        )
    except yt_dlp.utils.DownloadError as exc:
        shutil.rmtree(episode_dir, ignore_errors=True)
        raise UnsupportedMedia(_youtube_error_message(exc)) from exc
    except Exception:
        shutil.rmtree(episode_dir, ignore_errors=True)
        raise


def _download_youtube_audio(url: str, episode_dir: Path) -> tuple[dict[str, object], Path]:
    output_template = str(episode_dir / "audio.original.%(ext)s")
    options: dict[str, object] = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
    }
    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)

    mp3_path = episode_dir / "audio.original.mp3"
    if mp3_path.exists():
        return info, mp3_path

    candidates = sorted(episode_dir.glob("audio.original.*"))
    if not candidates:
        raise UnsupportedMedia("YouTube audio extraction produced no file")
    return info, candidates[0]


def _youtube_error_message(exc: Exception) -> str:
    message = str(exc)
    lower = message.lower()
    if any(token in lower for token in ("age", "region", "drm", "private", "login")):
        return "YouTube link is restricted or requires login"
    return "YouTube link could not be resolved"


async def _write_upload(upload: UploadLike, out_path: Path) -> int:
    total = 0
    with out_path.open("wb") as handle:
        while True:
            chunk = await upload.read(CHUNK_SIZE)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise PayloadTooLarge("audio file exceeds 1 GB limit")
            handle.write(chunk)
    if total == 0:
        raise UnsupportedMedia("empty upload")
    return total


async def _write_response_stream(response: httpx.Response, out_path: Path) -> int:
    total = 0
    with out_path.open("wb") as handle:
        async for chunk in response.aiter_bytes():
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_FILE_BYTES:
                raise PayloadTooLarge("audio file exceeds 1 GB limit")
            handle.write(chunk)
    if total == 0:
        raise UnsupportedMedia("empty response")
    return total


def _validate_audio_content_type(content_type: str | None) -> None:
    if content_type is None or not content_type.lower().split(";", 1)[0].strip().startswith("audio/"):
        raise UnsupportedMedia("direct URL did not return an audio Content-Type")


def _detect_audio_ext(path: Path) -> str:
    header = path.read_bytes()[:64]
    if header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and header[1] & 0xE0):
        return "mp3"
    if header.startswith(b"RIFF") and header[8:12] == b"WAVE":
        return "wav"
    if header[4:8] == b"ftyp":
        major_brand = header[8:12]
        if major_brand in {b"M4A ", b"mp42", b"isom", b"qt  "}:
            return "m4a"
    raise UnsupportedMedia("unsupported audio magic bytes")


async def _probe_duration_seconds(path: Path) -> int:
    process = await asyncio.create_subprocess_exec(
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_entries",
        "format=duration",
        str(path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise UnsupportedMedia(stderr.decode("utf-8", errors="replace").strip())
    payload = json.loads(stdout.decode("utf-8"))
    duration = float(payload["format"]["duration"])
    return int(round(duration))


async def _run_ffmpeg_normalize(in_path: Path, out_path: Path) -> None:
    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-y",
        "-i",
        str(in_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(out_path),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await process.communicate()
    if process.returncode != 0:
        raise UnsupportedMedia(stderr.decode("utf-8", errors="replace").strip())
