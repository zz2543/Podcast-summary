from __future__ import annotations

import asyncio
from typing import Any

from podsum.api.ws_progress import Broadcaster, ConnectionManager


class RecordingSocket:
    def __init__(self) -> None:
        self.frames: list[dict[str, Any]] = []

    async def send_json(self, frame: dict[str, Any]) -> None:
        self.frames.append(frame)


def _broadcaster() -> tuple[Broadcaster, RecordingSocket]:
    manager = ConnectionManager()
    socket = RecordingSocket()
    manager._connections.add(socket)  # type: ignore[arg-type]
    return Broadcaster(manager), socket


def _frame(state: str) -> dict[str, Any]:
    return {"id": "01JOB", "state": state}


async def test_terminal_update_is_never_throttled_away() -> None:
    """流水线尾部几个 stage 都是本地活儿，done 紧跟在上一帧后面发出。

    丢了这一帧，客户端的进度条就永远停在"生成摘要"。
    """
    broadcaster, socket = _broadcaster()

    for state in ("summarizing", "summarizing", "summarizing", "done"):
        await broadcaster.publish_job_update(_frame(state), episode_status="processing")

    assert [f["job"]["state"] for f in socket.frames] == ["summarizing", "done"]


async def test_failed_is_terminal_too() -> None:
    broadcaster, socket = _broadcaster()

    await broadcaster.publish_job_update(_frame("transcribing"), episode_status="processing")
    await broadcaster.publish_job_update(_frame("failed"), episode_status="failed")

    assert socket.frames[-1]["job"]["state"] == "failed"


async def test_same_state_refreshes_are_still_throttled() -> None:
    """限流本身要留着：一个 stage 内的进度刷新不该把 WebSocket 淹掉。"""
    broadcaster, socket = _broadcaster()

    for _ in range(50):
        await broadcaster.publish_job_update(_frame("summarizing"), episode_status="processing")
    assert len(socket.frames) == 1

    await asyncio.sleep(0.6)
    await broadcaster.publish_job_update(_frame("summarizing"), episode_status="processing")
    assert len(socket.frames) == 2


async def test_state_change_passes_immediately() -> None:
    broadcaster, socket = _broadcaster()

    for state in ("fetching", "transcribing", "summarizing"):
        await broadcaster.publish_job_update(_frame(state), episode_status="processing")

    assert [f["job"]["state"] for f in socket.frames] == [
        "fetching",
        "transcribing",
        "summarizing",
    ]


async def test_finished_jobs_do_not_pile_up() -> None:
    broadcaster, _ = _broadcaster()

    for n in range(5):
        job = {"id": f"J{n}", "state": "summarizing"}
        await broadcaster.publish_job_update(job, episode_status="processing")
        await broadcaster.publish_job_update({**job, "state": "done"}, episode_status="done")

    assert broadcaster._last_job_update == {}
