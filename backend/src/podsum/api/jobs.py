from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from podsum.persistence.models import Job
from podsum.persistence.repo import JobRepo

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def get_session(request: Request) -> Any:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session


SESSION_DEP = Depends(get_session)


@router.get("/{job_id}")
async def get_job(job_id: str, session: Session = SESSION_DEP) -> JSONResponse:
    job = JobRepo(session).get(job_id)
    if job is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "job not found", "details": {}}},
        )
    return JSONResponse(content=_job_payload(job))


def _job_payload(job: Job) -> dict[str, Any]:
    return {
        "id": job.id,
        "episode_id": job.episode_id,
        "state": job.state,
        "stage_progress": job.stage_progress,
        "attempt": job.attempt,
        "error": job.error,
        "started_at": _isoformat(job.started_at),
        "finished_at": _isoformat(job.finished_at),
    }


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
