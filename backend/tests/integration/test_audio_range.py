from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Episode


def test_audio_endpoint_supports_range_requests(tmp_path: Path) -> None:
    db_path = tmp_path / "podsum.sqlite3"
    episode_id = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
    episode_dir = tmp_path / "data" / episode_id
    episode_dir.mkdir(parents=True)
    audio_path = episode_dir / "audio.normalized.mp3"
    audio_path.write_bytes(b"0123456789")

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            Episode(
                id=episode_id,
                source_type="local_file",
                source_ref="sample.mp3",
                title="Range episode",
                status="done",
                data_dir=str(episode_dir),
            )
        )
        session.commit()
    engine.dispose()

    app = create_app(_settings(tmp_path, db_path))
    with TestClient(app) as client:
        response = client.get(
            f"/api/episodes/{episode_id}/files/audio",
            headers={"Range": "bytes=2-5"},
        )

    assert response.status_code == 206
    assert response.content == b"2345"
    assert response.headers["content-range"] == "bytes 2-5/10"


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
