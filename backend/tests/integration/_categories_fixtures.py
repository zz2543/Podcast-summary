"""Shared setup for the feature-004 integration tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from podsum.config import Settings
from podsum.main import create_app
from podsum.persistence.models import Base, Chapter, Entity, Episode, Job, SummaryArtifact

T0 = datetime(2026, 9, 24, tzinfo=timezone.utc)

# Startup re-derives every status from jobs and stage_status, so a "done"
# episode needs both to stay done.
DONE_STAGES = {"hook": "present", "three_act": "present", "chapters": "present"}


@dataclass
class Ep:
    id: str
    title: str
    hook: str | None = "一句话总结"
    status: str = "done"
    chapters: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)


def ulid(n: int) -> str:
    return f"01ARZ3NDEKTSV4RRFFQ69G{n:04d}"


def build_app(tmp_path: Path, episodes: list[Ep], *, orphan_hooks: int = 0, **settings: Any) -> Any:
    tmp_path.mkdir(parents=True, exist_ok=True)
    db_path = tmp_path / "podsum.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        for index, ep in enumerate(episodes):
            session.add(
                Episode(
                    id=ep.id,
                    source_type="youtube",
                    source_ref=f"https://www.youtube.com/watch?v={ep.id}",
                    title=ep.title,
                    status=ep.status,
                    created_at=T0 + timedelta(minutes=index),
                    updated_at=T0,
                    data_dir=str(tmp_path / "data" / ep.id),
                )
            )
            session.flush()
            done = ep.status == "done"
            if ep.hook is not None:
                session.add(
                    SummaryArtifact(
                        episode_id=ep.id,
                        hook=ep.hook,
                        stage_status=dict(DONE_STAGES) if done else {},
                        prompt_versions={},
                    )
                )
            if done:
                session.add(Job(episode_id=ep.id, state="done", attempt=1))
            for idx, title in enumerate(ep.chapters):
                session.add(Chapter(episode_id=ep.id, idx=idx, title=title, start_ms=idx * 1000, end_ms=idx * 1000 + 999))
            for rank, name in enumerate(ep.entities):
                session.add(Entity(episode_id=ep.id, name=name, kind="product", count=10 - rank))
        # Rows left behind by episodes deleted while foreign keys were off.
        for n in range(orphan_hooks):
            session.add(
                SummaryArtifact(episode_id=f"ORPHAN{n:020d}", hook="孤儿", stage_status={}, prompt_versions={})
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
            TTS_ENABLED=False,
            **settings,
        )
    )
