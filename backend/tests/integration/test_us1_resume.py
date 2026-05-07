from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Episode, Job, TranscriptSegment
from podsum.services.pipeline import create_us1_pipeline


class ResumeASRClient:
    def __init__(self) -> None:
        self.call_count = 1

    def transcribe(self, audio_path: Path, language_hint: str | None) -> list[TranscriptSegment]:
        self.call_count += 1
        raise AssertionError("resume should reuse persisted transcript segments")


class FakeLLMClient:
    def complete_json(self, prompt: str, schema: Any) -> dict[str, Any]:
        if "hook" in schema.model_fields:
            return {"hook": "A restart avoids duplicate cloud costs"}
        if "chapters" in schema.model_fields:
            return {
                "chapters": [
                    {
                        "title": "Cached transcript",
                        "key_points": ["The transcript was already saved."],
                        "candidate_quotes": [{"text": "hello world", "start_ms": 0}],
                    }
                ]
            }
        if "entities" in schema.model_fields:
            return {"entities": [{"name": "world", "kind": "product", "count": 1}]}
        return {
            "background": "The run already transcribed audio.",
            "core_argument": "Resume should skip ASR costs.",
            "conclusion": "Persisted segments make restart cheap.",
        }


def test_us1_resume_skips_retranscription_after_restart(tmp_path: Path) -> None:
    db_path = tmp_path / "podsum.sqlite3"
    episode_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    job_id = "01BRZ3NDEKTSV4RRFFQ69G5FAV"
    episode_dir = tmp_path / "data" / episode_id
    episode_dir.mkdir(parents=True)
    (episode_dir / "audio.normalized.mp3").write_bytes(b"cached")
    _seed_db(db_path, episode_id, job_id, episode_dir)

    settings = _settings(tmp_path, db_path)
    app = create_app(settings)
    enqueued: list[str] = []
    app.state.enqueue_job = lambda job: enqueued.append(job.id)

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    assert enqueued == [job_id]

    asr = ResumeASRClient()
    with Session(create_engine(f"sqlite:///{db_path}")) as session:
        job = session.scalar(select(Job).where(Job.id == job_id))
        assert job is not None
        assert job.state == "queued"
        pipeline = create_us1_pipeline(session, settings, asr_client=asr, llm_client=FakeLLMClient())
        asyncio.run(pipeline.run(job))
        session.commit()

        finished = session.scalar(select(Job).where(Job.id == job_id))
        assert finished is not None
        assert finished.state == "done"

    assert asr.call_count == 1


def _seed_db(db_path: Path, episode_id: str, job_id: str, episode_dir: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        episode = Episode(
            id=episode_id,
            source_type="local_file",
            source_ref="sample.wav",
            title="Cached transcript episode",
            duration_seconds=60,
            language="en",
            status="processing",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            data_dir=str(episode_dir),
        )
        job = Job(
            id=job_id,
            episode_id=episode_id,
            state="transcribing",
            stage_progress={"transcribe": {"status": "done"}},
            attempt=1,
        )
        segment = TranscriptSegment(
            episode_id=episode_id,
            idx=0,
            start_ms=0,
            end_ms=1000,
            text="hello world",
            language="en",
        )
        session.add_all([episode, job, segment])
        session.commit()
    engine.dispose()


def _settings(tmp_path: Path, db_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        DATA_DIR=tmp_path / "data",
        DB_PATH=db_path,
        VOLC_ACCESS_KEY_ID="ak",
        VOLC_SECRET_ACCESS_KEY="sk",
        DOUBAO_ASR_APP_ID="asr",
        DOUBAO_ASR_ACCESS_TOKEN="asr-token",
        DEEPSEEK_API_KEY="deepseek",
        DOUBAO_TTS_APP_ID="tts",
        DOUBAO_TTS_ACCESS_TOKEN="tts-token",
    )
