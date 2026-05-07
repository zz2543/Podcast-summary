from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Episode, Job


class MockASRClient:
    def __init__(self) -> None:
        self.call_count = 0

    def transcribe(self) -> None:
        self.call_count += 1


def test_restart_recovery_requeues_active_jobs(tmp_path) -> None:
    db_path = tmp_path / "podsum.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    episode_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    job_id = "01BRZ3NDEKTSV4RRFFQ69G5FAV"
    with Session(engine) as session:
        episode = Episode(
            id=episode_id,
            source_type="local_file",
            source_ref="sample.mp3",
            status="processing",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            data_dir=str(tmp_path / episode_id),
        )
        job = Job(
            id=job_id,
            episode_id=episode_id,
            state="transcribing",
            stage_progress={"transcribe": {"status": "running"}},
            attempt=1,
        )
        session.add_all([episode, job])
        session.commit()

    settings = Settings(
        _env_file=None,
        DB_PATH=db_path,
        VOLC_ACCESS_KEY_ID="ak",
        VOLC_SECRET_ACCESS_KEY="sk",
        DOUBAO_ASR_APP_ID="asr",
        DOUBAO_ASR_ACCESS_TOKEN="asr-token",
        DEEPSEEK_API_KEY="deepseek",
        DOUBAO_TTS_APP_ID="tts",
        DOUBAO_TTS_ACCESS_TOKEN="tts-token",
    )
    app = create_app(settings)
    asr = MockASRClient()
    enqueued: list[str] = []

    def enqueue(job: Job) -> None:
        enqueued.append(job.id)

    app.state.enqueue_job = enqueue
    app.state.asr_client = asr

    with TestClient(app) as client:
        assert client.get("/api/health").status_code == 200

    with Session(engine) as session:
        recovered = session.scalar(select(Job).where(Job.id == job_id))
        assert recovered is not None
        assert recovered.state == "queued"
        assert recovered.stage_progress == {"transcribe": {"status": "running"}}

    assert enqueued == [job_id]
    assert asr.call_count == 0
    engine.dispose()
