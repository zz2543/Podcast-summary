from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Chapter, Entity, Episode, Quote, SummaryArtifact


def test_episode_detail_includes_persisted_chapters_and_entities(tmp_path: Path) -> None:
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
            title="Detail episode",
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
            stage_status={
                "hook": "present",
                "three_act": "present",
                "chapters": "present",
                "entities": "present",
            },
            prompt_versions={},
        )
        chapter = Chapter(
            episode_id=episode_id,
            idx=0,
            title="Opening",
            start_ms=0,
            end_ms=60_000,
            key_points=["Point one"],
        )
        quote = Quote(
            chapter=chapter,
            idx=0,
            text="A verified quote.",
            start_ms=12_000,
            verified=True,
        )
        entity = Entity(
            episode_id=episode_id,
            name="DeepSeek",
            kind="product",
            count=2,
            sample_timestamps_ms=[12_000],
        )
        session.add_all([episode, artifact, chapter, quote, entity])
        session.commit()
    engine.dispose()

    app = create_app(_settings(tmp_path, db_path))
    with TestClient(app) as client:
        response = client.get(f"/api/episodes/{episode_id}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["chapters"] == [
        {
            "idx": 0,
            "title": "Opening",
            "start_ms": 0,
            "end_ms": 60_000,
            "key_points": ["Point one"],
            "quotes": [{"text": "A verified quote.", "start_ms": 12_000}],
        }
    ]
    assert detail["entities"] == [
        {
            "name": "DeepSeek",
            "kind": "product",
            "count": 2,
            "sample_timestamps_ms": [12_000],
        }
    ]


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
