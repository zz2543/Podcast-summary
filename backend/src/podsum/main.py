from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from podsum.api import episodes, jobs, ws_progress
from podsum.api._logging import configure_logging
from podsum.config import Settings, get_settings
from podsum.services.job_queue import JobQueue
from podsum.services.pipeline import recover_incomplete_jobs

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if getattr(app.state, "settings", None) is None:
        app.state.settings = get_settings()
    configure_logging(app.state.settings.LOG_LEVEL)
    app.state.engine = create_engine(app.state.settings.database_url)
    app.state.session_factory = sessionmaker(bind=app.state.engine)
    app.state.job_queue = JobQueue(app)
    if not callable(getattr(app.state, "enqueue_job", None)):
        app.state.enqueue_job = app.state.job_queue.enqueue
    app.state.job_queue.start()
    db_path = app.state.settings.DB_PATH
    recovered_jobs = []
    if db_path.exists():
        with app.state.session_factory() as session:
            recovered_jobs = recover_incomplete_jobs(
                session,
                getattr(app.state, "enqueue_job", None),
            )
            session.commit()
    app.state.recovered_jobs = recovered_jobs
    try:
        yield
    finally:
        await app.state.job_queue.stop()
        app.state.engine.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    app = FastAPI(title="Podcast Summary System", version=VERSION, lifespan=lifespan)
    app.state.settings = settings

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": VERSION}

    app.include_router(episodes.router)
    app.include_router(jobs.router)
    app.include_router(ws_progress.router)
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("podsum.main:app", host="127.0.0.1", port=8000)
