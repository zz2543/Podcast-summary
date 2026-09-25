"""A link already in the library is refused before anything is downloaded."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from podsum.api import episodes as episodes_api
from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Episode

EXISTING = "01ARZ3NDEKTSV4RRFFQ69G5FB1"
LINK = "https://www.bilibili.com/video/BV14dYx6iEwC"


def test_duplicate_video_answers_with_the_existing_episode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_download(*args: object, **kwargs: object) -> None:
        raise AssertionError("a duplicate must not be downloaded")

    monkeypatch.setattr(episodes_api, "ingest_video", no_download)
    app = _app_with_episode(tmp_path)

    with TestClient(app) as client:
        # Share text with a tracking parameter normalises to the stored link.
        response = client.post(
            "/api/episodes",
            json={"source_type": "youtube", "source_ref": f"【标题】{LINK}?vd_source=e352aac"},
        )

    assert response.status_code == 409
    error = response.json()["error"]
    assert error["code"] == "conflict"
    assert error["details"] == {"episode_id": EXISTING}


def test_duplicate_matches_a_row_stored_in_the_old_format(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def no_download(*args: object, **kwargs: object) -> None:
        raise AssertionError("a duplicate must not be downloaded")

    monkeypatch.setattr(episodes_api, "ingest_video", no_download)
    # Early rows kept the address-bar form: trailing slash and tracking parameter.
    app = _app_with_episode(tmp_path, source_ref=f"{LINK}/?vd_source=4f10bf75")

    with TestClient(app) as client:
        response = client.post("/api/episodes", json={"source_type": "youtube", "source_ref": LINK})

    assert response.status_code == 409
    assert response.json()["error"]["details"] == {"episode_id": EXISTING}


def _app_with_episode(tmp_path: Path, source_ref: str = LINK) -> object:
    db_path = tmp_path / "podsum.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    now = datetime(2026, 9, 24, tzinfo=timezone.utc)
    with Session(engine) as session:
        session.add(
            Episode(
                id=EXISTING,
                source_type="youtube",
                source_ref=source_ref,
                status="done",
                created_at=now,
                updated_at=now,
                data_dir=str(tmp_path / "data" / EXISTING),
            )
        )
        session.commit()
    engine.dispose()

    return create_app(
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
