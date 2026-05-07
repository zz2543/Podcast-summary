from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


router = APIRouter(tags=["jobs"])
SnapshotProvider = Callable[[], Awaitable[list[dict[str, Any]]]]


async def empty_snapshot() -> list[dict[str, Any]]:
    return []


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections.add(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.discard(websocket)

    async def broadcast(self, frame: dict[str, Any]) -> None:
        async with self._lock:
            connections = list(self._connections)

        disconnected: list[WebSocket] = []
        for websocket in connections:
            try:
                await websocket.send_json(frame)
            except RuntimeError:
                disconnected.append(websocket)

        if disconnected:
            async with self._lock:
                for websocket in disconnected:
                    self._connections.discard(websocket)


class Broadcaster:
    def __init__(
        self,
        manager: ConnectionManager,
        snapshot_provider: SnapshotProvider = empty_snapshot,
    ) -> None:
        self.manager = manager
        self.snapshot_provider = snapshot_provider
        self._last_job_update: dict[str, float] = {}

    def set_snapshot_provider(self, snapshot_provider: SnapshotProvider) -> None:
        self.snapshot_provider = snapshot_provider

    async def send_hello(self, websocket: WebSocket) -> None:
        await websocket.send_json(
            {
                "type": "hello",
                "server_version": "0.1.0",
                "now": datetime.now(timezone.utc).isoformat(),
            }
        )

    async def send_snapshot(self, websocket: WebSocket) -> None:
        await websocket.send_json({"type": "snapshot", "jobs": await self.snapshot_provider()})

    async def publish_job_update(self, job: dict[str, Any], episode_status: str) -> None:
        job_id = str(job.get("id", ""))
        now = asyncio.get_running_loop().time()
        if job_id:
            last = self._last_job_update.get(job_id, 0.0)
            if now - last < 0.5:
                return
            self._last_job_update[job_id] = now

        await self.manager.broadcast(
            {
                "type": "job_update",
                "job": job,
                "episode_status": episode_status,
            }
        )

    async def publish_stage_status(
        self,
        *,
        episode_id: str,
        stage: str,
        status: str,
    ) -> None:
        await self.manager.broadcast(
            {
                "type": "stage_status_update",
                "episode_id": episode_id,
                "stage": stage,
                "status": status,
            }
        )

    async def publish_error(self, *, code: str, message: str) -> None:
        await self.manager.broadcast({"type": "error", "code": code, "message": message})


manager = ConnectionManager()
broadcaster = Broadcaster(manager)


@router.websocket("/api/ws/jobs")
async def job_events(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        await broadcaster.send_hello(websocket)
        await broadcaster.send_snapshot(websocket)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(websocket)
