from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from podsum.persistence.models import TranscriptSegment
from podsum.services.asr_chunking import Chunk, ChunkedASR, merge, plan_chunks

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


def test_short_audio_is_split_into_one_piece() -> None:
    assert plan_chunks(1200.0, 1800, []) == [Chunk(0, 0.0, 1200.0)]


def test_cuts_are_even_without_pauses_and_snap_to_the_nearest_pause() -> None:
    even = plan_chunks(7365.0, 1800, [])
    assert len(even) == 5
    assert even[1].start == pytest.approx(1473.0)
    assert even[-1].end == 7365.0

    snapped = plan_chunks(7365.0, 1800, [(1440.0, 1441.0), (1500.0, 1501.0), (4000.0, 4001.0)])
    assert snapped[1].start == 1500.5  # 27.5 s from the even cut, closer than 1440.5
    assert snapped[2].start == pytest.approx(2946.0)  # nothing within reach: even cut
    assert [c.end for c in snapped[:-1]] == [c.start for c in snapped[1:]]


def test_merge_offsets_and_renumbers() -> None:
    chunks = [Chunk(0, 0.0, 10.0), Chunk(1, 10.0, 20.0)]
    pieces = [
        [TranscriptSegment(idx=0, start_ms=0, end_ms=900, text="a")],
        [TranscriptSegment(idx=0, start_ms=100, end_ms=900, text="b")],
    ]
    merged = merge(chunks, pieces)
    assert [(s.idx, s.start_ms, s.end_ms, s.text) for s in merged] == [
        (0, 0, 900, "a"),
        (1, 10_100, 10_900, "b"),
    ]


class FlakyInner:
    """Fails the second piece once, like a connection reset mid-upload."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.failed_once = False

    def transcribe(self, audio_path: Path, language_hint: str | None, audio_url: str | None = None):
        piece = audio_path.parent.name
        self.calls.append(piece)
        if piece == "001" and not self.failed_once:
            self.failed_once = True
            raise ConnectionResetError(54, "Connection reset by peer")
        raw = {"result": {"utterances": [{"start_time": 0, "end_time": 500, "text": f"piece {piece}"}]}}
        (audio_path.parent / "transcript.raw.json").write_text(json.dumps(raw))
        return [TranscriptSegment(idx=0, start_ms=0, end_ms=500, text=f"piece {piece}")]


@needs_ffmpeg
def test_a_retry_only_redoes_the_piece_that_failed(tmp_path: Path) -> None:
    audio = tmp_path / "audio.normalized.mp3"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=9",
         "-ar", "16000", "-ac", "1", str(audio)],
        check=True,
    )
    inner = FlakyInner()
    asr = ChunkedASR(inner, chunk_seconds=4, concurrency=1)

    with pytest.raises(ConnectionResetError):
        asr.transcribe(audio, "zh")
    assert sorted(inner.calls) == ["000", "001", "002"]

    inner.calls.clear()
    segments = asr.transcribe(audio, "zh")
    assert inner.calls == ["001"]
    assert [s.text for s in segments] == ["piece 000", "piece 001", "piece 002"]
    assert segments[2].start_ms == pytest.approx(6000, abs=60)
    assert not (tmp_path / "asr_chunks").exists()
    assert json.loads((tmp_path / "transcript.raw.json").read_text())["mode"] == "chunked"


def test_public_url_and_short_audio_go_straight_through(tmp_path: Path) -> None:
    class Inner:
        def __init__(self) -> None:
            self.args: list[tuple] = []

        def transcribe(self, audio_path, language_hint, audio_url=None):
            self.args.append((audio_path, audio_url))
            return []

    inner = Inner()
    ChunkedASR(inner, chunk_seconds=1).transcribe(tmp_path / "x.mp3", None, "https://example.com/a.mp3")
    ChunkedASR(inner, chunk_seconds=0).transcribe(tmp_path / "x.mp3", None)
    assert inner.args == [
        (tmp_path / "x.mp3", "https://example.com/a.mp3"),
        (tmp_path / "x.mp3", None),
    ]
