from __future__ import annotations

from fastapi import APIRouter, WebSocket


router = APIRouter(tags=["jobs"])


@router.websocket("/api/ws/jobs")
async def job_events(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.close()
