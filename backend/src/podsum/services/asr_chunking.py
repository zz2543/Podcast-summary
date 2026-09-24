"""Transcribe long uploads piece by piece.

A provider that takes audio inline gets the whole file in one request body:
about 30 MB for two hours once base64-encoded. Over a flaky link that request
is the likeliest thing to die, and when it does every retry starts from byte
zero — a 2-hour episode once failed nine uploads in a row this way while
every shorter episode went through.

So audio longer than ``ASR_CHUNK_SECONDS`` is cut into equal pieces, each cut
moved to the nearest pause so no word is split, and each piece goes through
the provider on its own. A finished piece's raw response stays on disk until
the whole episode is done, so a stage retry redoes only the pieces that failed.
"""

from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from podsum.persistence.models import TranscriptSegment
from podsum.services.asr_client import ASRClient, parse_segments

CHUNK_DIR_NAME = "asr_chunks"
RAW_NAME = "transcript.raw.json"
#: How far from an even split a cut may move to land in a pause.
SNAP_WINDOW_SECONDS = 90.0
_SILENCE_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SILENCE_END = re.compile(r"silence_end:\s*(-?[\d.]+)")


@dataclass(frozen=True)
class Chunk:
    index: int
    start: float
    end: float

    @property
    def offset_ms(self) -> int:
        return int(round(self.start * 1000))


class ChunkedASR:
    def __init__(self, inner: ASRClient, *, chunk_seconds: int, concurrency: int = 2) -> None:
        self.inner = inner
        self.chunk_seconds = chunk_seconds
        self.concurrency = concurrency

    def transcribe(
        self,
        audio_path: Path,
        language_hint: str | None,
        audio_url: str | None = None,
    ) -> list[TranscriptSegment]:
        # With a public URL the provider fetches the audio itself: nothing large
        # crosses our link, so there is nothing to gain from cutting it up.
        if audio_url or self.chunk_seconds <= 0:
            return self.inner.transcribe(audio_path, language_hint, audio_url)
        duration = probe_duration(audio_path)
        if duration <= self.chunk_seconds:
            return self.inner.transcribe(audio_path, language_hint)

        chunks = plan_chunks(duration, self.chunk_seconds, detect_silences(audio_path))
        work_dir = audio_path.parent / CHUNK_DIR_NAME
        _reset_if_plan_changed(work_dir, chunks)

        def run(chunk: Chunk) -> list[TranscriptSegment]:
            return self._transcribe_chunk(audio_path, work_dir, chunk, language_hint)

        with ThreadPoolExecutor(max_workers=self.concurrency) as pool:
            futures = [pool.submit(run, chunk) for chunk in chunks]
            # Let every piece finish before raising: each one that succeeds is
            # cached, and the stage retry only has the failed ones left to do.
            results: list[list[TranscriptSegment]] = []
            errors: list[BaseException] = []
            for future in futures:
                try:
                    results.append(future.result())
                except Exception as exc:  # noqa: BLE001 - re-raised below
                    errors.append(exc)
        if errors:
            raise errors[0]

        segments = merge(chunks, results)
        _write_combined_raw(audio_path.parent, work_dir, chunks)
        shutil.rmtree(work_dir, ignore_errors=True)
        return segments

    def _transcribe_chunk(
        self,
        audio_path: Path,
        work_dir: Path,
        chunk: Chunk,
        language_hint: str | None,
    ) -> list[TranscriptSegment]:
        chunk_dir = work_dir / f"{chunk.index:03d}"
        raw_path = chunk_dir / RAW_NAME
        if raw_path.exists():
            return parse_segments(json.loads(raw_path.read_text(encoding="utf-8")), language_hint=language_hint)
        chunk_dir.mkdir(parents=True, exist_ok=True)
        chunk_audio = chunk_dir / "audio.mp3"
        cut_audio(audio_path, chunk_audio, chunk.start, chunk.end)
        # Every provider writes its raw response next to the audio it was given,
        # which is what makes the piece count as done on the next attempt.
        segments = self.inner.transcribe(chunk_audio, language_hint)
        chunk_audio.unlink(missing_ok=True)
        return segments


def plan_chunks(duration: float, chunk_seconds: int, silences: list[tuple[float, float]]) -> list[Chunk]:
    """Equal pieces no longer than ``chunk_seconds``, cut at the nearest pause."""
    count = max(1, math.ceil(duration / chunk_seconds))
    length = duration / count
    cuts = [0.0]
    for k in range(1, count):
        target = k * length
        cuts.append(max(_snap(target, silences), cuts[-1] + 1.0))
    cuts.append(duration)
    return [Chunk(index=i, start=cuts[i], end=cuts[i + 1]) for i in range(count)]


def _snap(target: float, silences: list[tuple[float, float]]) -> float:
    candidates = [
        (start + end) / 2
        for start, end in silences
        if abs((start + end) / 2 - target) <= SNAP_WINDOW_SECONDS
    ]
    return min(candidates, key=lambda mid: abs(mid - target)) if candidates else target


def merge(chunks: list[Chunk], results: list[list[TranscriptSegment]]) -> list[TranscriptSegment]:
    merged: list[TranscriptSegment] = []
    for chunk, segments in zip(chunks, results, strict=True):
        for segment in segments:
            merged.append(
                TranscriptSegment(
                    idx=len(merged),
                    start_ms=segment.start_ms + chunk.offset_ms,
                    end_ms=segment.end_ms + chunk.offset_ms,
                    text=segment.text,
                    language=segment.language,
                )
            )
    return merged


def probe_duration(path: Path) -> float:
    completed = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True,
        check=True,
        text=True,
    )
    return float(json.loads(completed.stdout)["format"]["duration"])


def detect_silences(path: Path, *, noise_db: int = -35, min_seconds: float = 0.4) -> list[tuple[float, float]]:
    completed = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            f"silencedetect=noise={noise_db}dB:d={min_seconds}",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return []  # no pauses known: cuts fall on the even split instead
    silences: list[tuple[float, float]] = []
    start: float | None = None
    for line in completed.stderr.splitlines():
        if (match := _SILENCE_START.search(line)) is not None:
            start = float(match.group(1))
        elif (match := _SILENCE_END.search(line)) is not None and start is not None:
            silences.append((start, float(match.group(1))))
            start = None
    return silences


def cut_audio(source: Path, target: Path, start: float, end: float) -> None:
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            # Input-side seek is fast; output timestamps then restart at zero,
            # so the length has to be given as a duration, not an end time.
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{end - start:.3f}",
            "-i",
            str(source),
            "-c",
            "copy",
            str(target),
        ],
        capture_output=True,
        check=True,
    )


def _reset_if_plan_changed(work_dir: Path, chunks: list[Chunk]) -> None:
    """Cached pieces are only reusable if they were cut at the same places."""
    plan = [[chunk.start, chunk.end] for chunk in chunks]
    plan_path = work_dir / "plan.json"
    if plan_path.exists():
        try:
            if json.loads(plan_path.read_text(encoding="utf-8")) == plan:
                return
        except ValueError:
            pass
        shutil.rmtree(work_dir, ignore_errors=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan), encoding="utf-8")


def _write_combined_raw(episode_dir: Path, work_dir: Path, chunks: list[Chunk]) -> None:
    pieces: list[dict[str, Any]] = []
    for chunk in chunks:
        raw_path = work_dir / f"{chunk.index:03d}" / RAW_NAME
        raw = json.loads(raw_path.read_text(encoding="utf-8")) if raw_path.exists() else None
        pieces.append({"index": chunk.index, "start_s": chunk.start, "end_s": chunk.end, "raw": raw})
    (episode_dir / RAW_NAME).write_text(
        json.dumps({"mode": "chunked", "chunks": pieces}, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
