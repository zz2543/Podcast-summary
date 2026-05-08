from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Episode, Job


class SlowASR:
    def transcribe(
        self,
        audio_path: Path,
        language_hint: str | None,
        audio_url: str | None = None,
    ) -> list[dict[str, Any]]:
        _ = audio_path, language_hint, audio_url
        time.sleep(0.2)
        return [{"idx": 0, "start_ms": 0, "end_ms": 1_000, "text": "hello world", "language": "en"}]


class FakeLLM:
    def complete_json(self, prompt: str, schema: Any) -> dict[str, Any]:
        _ = prompt
        if "hook" in schema.model_fields:
            return {"hook": "Concurrency stays bounded"}
        if "chapters" in schema.model_fields:
            return {
                "chapters": [
                    {
                        "title": "Opening",
                        "key_points": ["The queue is bounded."],
                        "candidate_quotes": [{"text": "hello world", "start_ms": 0}],
                    }
                ]
            }
        if "entities" in schema.model_fields:
            return {"entities": [{"name": "world", "kind": "product", "count": 1}]}
        return {
            "background": "Several jobs are queued.",
            "core_argument": "The semaphore limits concurrent transcription.",
            "conclusion": "No more than two jobs transcribe at once.",
        }


def test_us4_concurrency_limit_keeps_transcribing_jobs_at_or_below_two(tmp_path: Path) -> None:
    db_path = tmp_path / "podsum.sqlite3"
    _seed_jobs(tmp_path, db_path, count=5)
    app = create_app(_settings(tmp_path, db_path))
    app.state.asr_client = SlowASR()
    app.state.llm_client = FakeLLM()

    observed_counts: list[int] = []
    engine = create_engine(f"sqlite:///{db_path}")
    with TestClient(app) as client:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with Session(engine) as session:
                active = session.scalar(select(func.count()).select_from(Job).where(Job.state == "transcribing"))
                terminal = session.scalar(
                    select(func.count()).select_from(Job).where(Job.state.in_(("done", "partial", "failed")))
                )
            observed_counts.append(int(active or 0))
            if terminal == 5:
                break
            time.sleep(0.05)

        assert client.get("/api/health").status_code == 200
    engine.dispose()

    assert observed_counts
    assert max(observed_counts) <= 2
    assert max(observed_counts) == 2


def _seed_jobs(tmp_path: Path, db_path: Path, *, count: int) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for index in range(count):
            episode_id = f"01ARZ3NDEKTSV4RRFFQ69G5FA{index}"
            job_id = f"01BRZ3NDEKTSV4RRFFQ69G5FA{index}"
            episode_dir = tmp_path / "data" / episode_id
            episode_dir.mkdir(parents=True)
            (episode_dir / "audio.normalized.mp3").write_bytes(b"cached")
            episode = Episode(
                id=episode_id,
                source_type="local_file",
                source_ref=f"sample-{index}.mp3",
                title=f"Episode {index}",
                duration_seconds=60,
                language="en",
                status="pending",
                created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
                updated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
                data_dir=str(episode_dir),
            )
            job = Job(id=job_id, episode_id=episode_id, state="queued", attempt=1)
            session.add_all([episode, job])
        session.commit()
    engine.dispose()


def _settings(tmp_path: Path, db_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        DATA_DIR=tmp_path / "data",
        DB_PATH=db_path,
        MAX_CONCURRENCY=2,
        VOLC_ACCESS_KEY_ID="ak",
        VOLC_SECRET_ACCESS_KEY="sk",
        DOUBAO_ASR_APP_ID="asr",
        DOUBAO_ASR_ACCESS_TOKEN="asr-token",
        DEEPSEEK_API_KEY="deepseek",
        DOUBAO_TTS_APP_ID="tts",
        DOUBAO_TTS_ACCESS_TOKEN="tts-token",
    )
