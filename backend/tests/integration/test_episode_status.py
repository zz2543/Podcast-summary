"""Episode status follows what the episode has, not whichever job ran last."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from podsum.api.ws_progress import Broadcaster, ConnectionManager
from podsum.domain.episode_status import derive
from podsum.persistence.models import Base, Episode, Job, SummaryArtifact
from podsum.services.pipeline import Pipeline, reconcile_episode_statuses

EPISODE_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
COMPLETE = {"hook": "present", "three_act": "present", "chapters": "present", "entities": "present"}


@pytest.mark.parametrize(
    ("stage_status", "active", "ran", "expected"),
    [
        (COMPLETE, False, True, "done"),
        ({**COMPLETE, "tts": "failed_after_retries"}, False, True, "done"),
        ({**COMPLETE, "usefulness": "failed_after_retries"}, False, True, "partial"),
        ({**COMPLETE, "entities": "failed_after_retries"}, False, True, "partial"),
        ({"hook": "present"}, False, True, "failed"),
        ({}, False, True, "failed"),
        ({}, False, False, "pending"),
        (None, True, False, "processing"),
        (COMPLETE, True, True, "processing"),
    ],
)
def test_derive(stage_status, active, ran, expected) -> None:
    assert derive(stage_status, summary_job_active=active, summary_job_ran=ran) == expected


def _session(tmp_path: Path) -> Session:
    engine = create_engine(f"sqlite:///{tmp_path / 'podsum.sqlite3'}")
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed(session: Session, tmp_path: Path, *, status: str, stage_status: dict, jobs: list[Job]) -> None:
    now = datetime(2026, 5, 7, tzinfo=timezone.utc)
    session.add(
        Episode(
            id=EPISODE_ID,
            source_type="youtube",
            source_ref="https://example.com/v",
            status=status,
            created_at=now,
            updated_at=now,
            data_dir=str(tmp_path / EPISODE_ID),
        )
    )
    session.add(SummaryArtifact(episode_id=EPISODE_ID, stage_status=stage_status, prompt_versions={}))
    session.add_all(jobs)
    session.commit()


def test_reconcile_repairs_rows_written_by_the_old_rule(tmp_path: Path) -> None:
    """The three real cases: a failed re-run, a failed digest, a failed first run."""
    session = _session(tmp_path)
    _seed(
        session,
        tmp_path,
        status="failed",
        stage_status={**COMPLETE, "tts": "failed_after_retries"},
        jobs=[
            Job(id="01B0000000000000000000000A", episode_id=EPISODE_ID, state="done", attempt=1),
            Job(
                id="01B0000000000000000000000B",
                episode_id=EPISODE_ID,
                state="failed",
                attempt=2,
                error="[Errno 17] File exists",
            ),
            Job(
                id="01B0000000000000000000000C",
                episode_id=EPISODE_ID,
                state="partial",
                attempt=3,
                stage_progress={"requested_stage": "tts"},
            ),
        ],
    )
    before = session.get(Episode, EPISODE_ID).updated_at

    assert reconcile_episode_statuses(session) == [EPISODE_ID]
    session.commit()
    session.expire_all()
    episode = session.get(Episode, EPISODE_ID)
    assert episode.status == "done"
    assert episode.updated_at == before


def test_failed_rerun_keeps_a_readable_episode_done(tmp_path: Path) -> None:
    session = _session(tmp_path)
    _seed(
        session,
        tmp_path,
        status="done",
        stage_status=COMPLETE,
        jobs=[
            Job(id="01B0000000000000000000000A", episode_id=EPISODE_ID, state="done", attempt=1),
            Job(id="01B0000000000000000000000B", episode_id=EPISODE_ID, state="queued", attempt=2),
        ],
    )

    def boom(_context):
        raise ConnectionResetError(54, "Connection reset by peer")

    pipeline = Pipeline(session, retry_attempts=1, broadcaster=Broadcaster(ConnectionManager()))
    pipeline.register_stage("fetch", required=True, run=boom)
    job = asyncio.run(pipeline.run(session.get(Job, "01B0000000000000000000000B")))

    assert job.state == "failed"
    assert job.started_at is not None and job.finished_at is not None
    assert session.get(Episode, EPISODE_ID).status == "done"


def test_first_run_failure_marks_episode_failed(tmp_path: Path) -> None:
    session = _session(tmp_path)
    _seed(
        session,
        tmp_path,
        status="pending",
        stage_status={},
        jobs=[Job(id="01B0000000000000000000000A", episode_id=EPISODE_ID, state="queued", attempt=1)],
    )

    def boom(_context):
        raise ConnectionResetError(54, "Connection reset by peer")

    pipeline = Pipeline(session, retry_attempts=1, broadcaster=Broadcaster(ConnectionManager()))
    pipeline.register_stage("transcribe", required=True, run=boom)
    asyncio.run(pipeline.run(session.get(Job, "01B0000000000000000000000A")))

    assert session.get(Episode, EPISODE_ID).status == "failed"


def test_digest_pipeline_never_touches_episode_status(tmp_path: Path) -> None:
    session = _session(tmp_path)
    _seed(
        session,
        tmp_path,
        status="done",
        stage_status=COMPLETE,
        jobs=[
            Job(id="01B0000000000000000000000A", episode_id=EPISODE_ID, state="done", attempt=1),
            Job(
                id="01B0000000000000000000000B",
                episode_id=EPISODE_ID,
                state="queued",
                attempt=2,
                stage_progress={"requested_stage": "tts"},
            ),
        ],
    )

    def boom(_context):
        raise RuntimeError("Insufficient Balance")

    pipeline = Pipeline(
        session,
        retry_attempts=1,
        broadcaster=Broadcaster(ConnectionManager()),
        owns_episode_status=False,
    )
    pipeline.register_stage("tts", required=False, run=boom)
    job = asyncio.run(pipeline.run(session.get(Job, "01B0000000000000000000000B")))

    assert job.state == "partial"
    assert session.get(Episode, EPISODE_ID).status == "done"


def test_last_failure_names_the_stage_and_ignores_digest_jobs(tmp_path: Path) -> None:
    from podsum.api.episodes import _last_failure

    session = _session(tmp_path)
    _seed(
        session,
        tmp_path,
        status="failed",
        stage_status={},
        jobs=[
            Job(
                id="01B0000000000000000000000A",
                episode_id=EPISODE_ID,
                state="failed",
                attempt=1,
                error="[Errno 54] Connection reset by peer",
                stage_progress={
                    "fetch": {"status": "done"},
                    "transcribe": {"status": "failed_after_retries", "error": "reset"},
                },
            ),
            # A later digest job must not hide the summary job's failure.
            Job(
                id="01B0000000000000000000000B",
                episode_id=EPISODE_ID,
                state="partial",
                attempt=2,
                stage_progress={"requested_stage": "tts"},
            ),
        ],
    )

    failure = _last_failure(session, EPISODE_ID)
    assert failure is not None
    assert failure["stage"] == "transcribe"
    assert failure["error"] == "[Errno 54] Connection reset by peer"

    session.add(Job(id="01B0000000000000000000000C", episode_id=EPISODE_ID, state="done", attempt=3))
    session.commit()
    assert _last_failure(session, EPISODE_ID) is None
