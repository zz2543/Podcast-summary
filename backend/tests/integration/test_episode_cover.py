"""The list says which episodes have a cover, and the cover is served as a file."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Episode

WITH_COVER = "01ARZ3NDEKTSV4RRFFQ69G5FA1"
WITHOUT_COVER = "01ARZ3NDEKTSV4RRFFQ69G5FA2"
# Stored as "data/<id>" by an early run from the repository root.
RELATIVE_DIR = "01ARZ3NDEKTSV4RRFFQ69G5FA3"


def test_list_flags_covers_and_serves_them(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The packaged app runs the server from inside its bundle, not the repo root.
    elsewhere = tmp_path / "bundle"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    db_path = tmp_path / "podsum.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 24, tzinfo=timezone.utc)
    with Session(engine) as session:
        for episode_id in (WITH_COVER, WITHOUT_COVER, RELATIVE_DIR):
            episode_dir = tmp_path / "data" / episode_id
            episode_dir.mkdir(parents=True)
            stored_dir = f"data/{episode_id}" if episode_id == RELATIVE_DIR else str(episode_dir)
            session.add(
                Episode(
                    id=episode_id,
                    source_type="youtube",
                    source_ref=f"https://example.com/{episode_id}",
                    status="done",
                    created_at=now,
                    updated_at=now,
                    data_dir=stored_dir,
                )
            )
        session.commit()
    (tmp_path / "data" / WITH_COVER / "cover.jpg").write_bytes(b"\xff\xd8jpeg")
    (tmp_path / "data" / RELATIVE_DIR / "cover.jpg").write_bytes(b"\xff\xd8old")

    app = create_app(
        Settings(
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
    )
    with TestClient(app) as client:
        items = {item["id"]: item for item in client.get("/api/episodes").json()["items"]}
        assert items[WITH_COVER]["has_cover"] is True
        assert items[WITHOUT_COVER]["has_cover"] is False
        assert items[RELATIVE_DIR]["has_cover"] is True
        assert client.get(f"/api/episodes/{RELATIVE_DIR}/files/cover").content == b"\xff\xd8old"

        served = client.get(f"/api/episodes/{WITH_COVER}/files/cover")
        assert served.status_code == 200
        assert served.headers["content-type"] == "image/jpeg"
        assert served.content == b"\xff\xd8jpeg"

        assert client.get(f"/api/episodes/{WITHOUT_COVER}/files/cover").status_code == 404
        assert client.get("/api/episodes/01ARZ3NDEKTSV4RRFFQ69G5FA9/files/cover").status_code == 404
