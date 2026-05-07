from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session
from tenacity import AsyncRetrying, RetryError, stop_after_attempt

from podsum.api.ws_progress import Broadcaster, broadcaster as default_broadcaster
from podsum.persistence.models import Job
from podsum.persistence.repo import JobRepo, SummaryArtifactRepo


StageResult = dict[str, Any] | None
StageRun = Callable[["PipelineContext"], StageResult | Awaitable[StageResult]]


@dataclass(frozen=True)
class Stage:
    name: str
    required: bool
    run: StageRun


@dataclass
class PipelineContext:
    session: Session
    job: Job
    stage: Stage
    stage_progress: dict[str, Any]


class Pipeline:
    def __init__(
        self,
        session: Session,
        *,
        retry_attempts: int = 3,
        broadcaster: Broadcaster = default_broadcaster,
    ) -> None:
        self.session = session
        self.retry_attempts = retry_attempts
        self.broadcaster = broadcaster
        self._stages: list[Stage] = []

    @property
    def stages(self) -> tuple[Stage, ...]:
        return tuple(self._stages)

    def register_stage(self, name: str, *, required: bool, run: StageRun) -> None:
        self._stages.append(Stage(name=name, required=required, run=run))

    async def run(self, job: Job) -> Job:
        optional_failed = False
        for stage in self._stages:
            await self._set_state(job, self._state_for_stage(stage.name))
            self._record_progress(job, stage.name, {"status": "running"})

            context = PipelineContext(
                session=self.session,
                job=job,
                stage=stage,
                stage_progress=dict(job.stage_progress or {}),
            )
            try:
                result = await self._run_with_retries(stage, context)
            except Exception as exc:
                self._record_progress(
                    job,
                    stage.name,
                    {"status": "failed_after_retries", "error": str(exc)},
                )
                if stage.required:
                    await self._set_state(job, "failed", error=str(exc))
                    return job
                optional_failed = True
                SummaryArtifactRepo(self.session).update_stage_status(
                    job.episode_id,
                    stage.name,
                    "failed_after_retries",
                )
                self.session.flush()
                continue

            self._record_progress(job, stage.name, {"status": "done", "result": result or {}})

        await self._set_state(job, "partial" if optional_failed else "done")
        return job

    async def _run_with_retries(self, stage: Stage, context: PipelineContext) -> StageResult:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.retry_attempts),
                reraise=True,
            ):
                with attempt:
                    result = stage.run(context)
                    if inspect.isawaitable(result):
                        result = await result
                    return result
        except RetryError as exc:
            raise exc.last_attempt.exception() from exc
        return None

    def _record_progress(self, job: Job, stage: str, payload: dict[str, Any]) -> None:
        progress = dict(job.stage_progress or {})
        progress[stage] = payload
        job.stage_progress = progress
        self.session.add(job)
        self.session.flush()

    async def _set_state(self, job: Job, state: str, *, error: str | None = None) -> None:
        job.state = state
        job.error = error
        self.session.add(job)
        self.session.flush()
        await self.broadcaster.publish_job_update(
            {
                "id": job.id,
                "episode_id": job.episode_id,
                "state": job.state,
                "stage_progress": job.stage_progress,
                "attempt": job.attempt,
                "error": job.error,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            },
            episode_status=self._episode_status_for_job(state),
        )

    @staticmethod
    def _state_for_stage(stage_name: str) -> str:
        if stage_name in {"fetch", "fetching"}:
            return "fetching"
        if stage_name in {"transcribe", "transcribing"}:
            return "transcribing"
        if stage_name == "tts":
            return "tts"
        return "summarizing"

    @staticmethod
    def _episode_status_for_job(state: str) -> str:
        if state in {"done", "partial", "failed"}:
            return state
        return "processing"


def recover_incomplete_jobs(
    session: Session,
    enqueue: Callable[[Job], None] | None = None,
) -> list[Job]:
    jobs = JobRepo(session).active()
    for job in jobs:
        job.state = "queued"
        session.add(job)
    session.flush()
    if enqueue is not None:
        for job in jobs:
            enqueue(job)
    return jobs
