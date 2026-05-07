from __future__ import annotations

import asyncio
from typing import Any

from podsum.persistence.repo import JobRepo
from podsum.services.pipeline import create_us1_pipeline


class JobQueue:
    def __init__(self, app: Any) -> None:
        self.app = app
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(app.state.settings.MAX_CONCURRENCY)
        self.worker: asyncio.Task[None] | None = None
        self.active_tasks: set[asyncio.Task[None]] = set()

    def start(self) -> None:
        if self.worker is None or self.worker.done():
            self.worker = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self.worker is not None:
            self.worker.cancel()
            try:
                await self.worker
            except asyncio.CancelledError:
                pass
        if self.active_tasks:
            for task in self.active_tasks:
                task.cancel()
            await asyncio.gather(*self.active_tasks, return_exceptions=True)

    def enqueue(self, job: Any) -> None:
        self.queue.put_nowait(str(job.id))

    async def _worker(self) -> None:
        while True:
            job_id = await self.queue.get()
            task = asyncio.create_task(self._run_job(job_id))
            self.active_tasks.add(task)
            task.add_done_callback(self.active_tasks.discard)
            self.queue.task_done()

    async def _run_job(self, job_id: str) -> None:
        async with self.semaphore:
            with self.app.state.session_factory() as session:
                job = JobRepo(session).get(job_id)
                if job is None:
                    return
                pipeline = create_us1_pipeline(
                    session,
                    self.app.state.settings,
                    asr_client=getattr(self.app.state, "asr_client", None),
                    llm_client=getattr(self.app.state, "llm_client", None),
                )
                await pipeline.run(job)
                session.commit()
