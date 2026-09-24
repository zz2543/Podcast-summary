from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["jobs"])
SnapshotProvider = Callable[[], Awaitable[list[dict[str, Any]]]]

#: 作业走到这三个状态之一就不会再动了。
TERMINAL_JOB_STATES = frozenset({"done", "partial", "failed"})


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
        self._last_job_update: dict[str, tuple[float, str]] = {}   # job_id → (时刻, 已发状态)

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
        """限流只针对"同一状态内的进度刷新"，状态变化一律放行。

        每个 stage 都会发两帧（record_progress 一帧、set_state 一帧），后半段
        那几个 stage 又都是本地活儿，几十毫秒就跑完——按时间一刀切地丢帧，
        丢掉的恰好是最后那帧 done：客户端的进度条从此停在"生成摘要"，
        卡片却已经是"已完成"。终态帧只有一次机会，不能省。
        """
        job_id = str(job.get("id", ""))
        state = str(job.get("state", ""))
        terminal = state in TERMINAL_JOB_STATES
        now = asyncio.get_running_loop().time()
        if job_id:
            last_at, last_state = self._last_job_update.get(job_id, (0.0, ""))
            if not terminal and state == last_state and now - last_at < 0.5:
                return
            if terminal:
                # 作业到头了，别把 id 攒在字典里
                self._last_job_update.pop(job_id, None)
            else:
                self._last_job_update[job_id] = (now, state)

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
