from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Chapter, Episode, SummaryArtifact


class FakeTTSClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    def synthesize(self, text: str, lang: str, out_path: Path) -> None:
        self.calls += 1
        if self.fail:
            raise RuntimeError("tts failed")
        assert "Hook" in text
        assert lang == "en"
        out_path.write_bytes(b"fake-mp3")


def test_digest_endpoint_returns_200_on_second_call(tmp_path: Path) -> None:
    db_path, episode_id = _seed_episode(tmp_path)
    app = create_app(_settings(tmp_path, db_path))
    app.state.tts_client = FakeTTSClient()

    with TestClient(app) as client:
        first = client.post(f"/api/episodes/{episode_id}/digest")
        assert first.status_code == 202
        job = _wait_for_job(client, first.json()["id"])
        assert job["state"] == "done"

        second = client.post(f"/api/episodes/{episode_id}/digest")
        assert second.status_code == 200
        assert second.json()["status"] == "present"

        digest = client.get(f"/api/episodes/{episode_id}/files/digest")
        assert digest.status_code == 200
        assert digest.content == b"fake-mp3"


def test_digest_failure_marks_tts_failed_after_retries(tmp_path: Path) -> None:
    db_path, episode_id = _seed_episode(tmp_path)
    fake_tts = FakeTTSClient(fail=True)
    app = create_app(_settings(tmp_path, db_path))
    app.state.tts_client = fake_tts

    with TestClient(app) as client:
        response = client.post(f"/api/episodes/{episode_id}/digest")
        assert response.status_code == 202
        job = _wait_for_job(client, response.json()["id"])
        assert job["state"] == "partial"

        detail = client.get(f"/api/episodes/{episode_id}").json()
        assert detail["stage_status"]["tts"] == "failed_after_retries"
        assert fake_tts.calls == 3


def _seed_episode(tmp_path: Path) -> tuple[Path, str]:
    db_path = tmp_path / "podsum.sqlite3"
    episode_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    episode_dir = tmp_path / "data" / episode_id
    episode_dir.mkdir(parents=True)
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        episode = Episode(
            id=episode_id,
            source_type="local_file",
            source_ref="sample.mp3",
            title="Digest episode",
            duration_seconds=120,
            language="en",
            status="done",
            created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
            updated_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
            data_dir=str(episode_dir),
        )
        artifact = SummaryArtifact(
            episode_id=episode_id,
            hook="A focused hook",
            three_act={
                "background": "Context.",
                "core_argument": "Argument.",
                "conclusion": "Ending.",
            },
            stage_status={"hook": "present", "three_act": "present", "chapters": "present"},
            prompt_versions={},
        )
        chapter = Chapter(
            episode_id=episode_id,
            idx=0,
            title="Opening",
            start_ms=0,
            end_ms=60_000,
            key_points=["Point one", "Point two"],
        )
        session.add_all([episode, artifact, chapter])
        session.commit()
    engine.dispose()
    return db_path, episode_id


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


def _wait_for_job(client: TestClient, job_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        response = client.get(f"/api/jobs/{job_id}")
        payload = response.json()
        if payload["state"] in {"done", "partial", "failed"}:
            return payload
        time.sleep(0.05)
    raise AssertionError("job did not finish")
