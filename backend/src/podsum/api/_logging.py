from __future__ import annotations

import contextlib
import contextvars
import json
import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

_DEFAULT_CONTEXT = {"job_id": None, "episode_id": None, "stage": None}
_log_context: contextvars.ContextVar[dict[str, str | None] | None] = contextvars.ContextVar(
    "podsum_log_context",
    default=None,
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        context = _current_context()
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "job_id": getattr(record, "job_id", None) or context.get("job_id"),
            "episode_id": getattr(record, "episode_id", None) or context.get("episode_id"),
            "stage": getattr(record, "stage", None) or context.get("stage"),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


@contextlib.contextmanager
def bind_log_context(
    *,
    job_id: str | None = None,
    episode_id: str | None = None,
    stage: str | None = None,
) -> Iterator[None]:
    current = _current_context()
    token = _log_context.set(
        {
            "job_id": job_id if job_id is not None else current.get("job_id"),
            "episode_id": episode_id if episode_id is not None else current.get("episode_id"),
            "stage": stage if stage is not None else current.get("stage"),
        }
    )
    try:
        yield
    finally:
        _log_context.reset(token)


def _current_context() -> dict[str, str | None]:
    return _log_context.get() or dict(_DEFAULT_CONTEXT)
