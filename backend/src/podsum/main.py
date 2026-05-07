from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from podsum.api import episodes, jobs, ws_progress
from podsum.config import Settings, get_settings

VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    if getattr(app.state, "settings", None) is None:
        app.state.settings = get_settings()
    yield


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
