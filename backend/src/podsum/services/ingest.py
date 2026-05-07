from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

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
