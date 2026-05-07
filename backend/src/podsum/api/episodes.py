from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from podsum.exporters.json_export import render as render_json
from podsum.persistence.models import Episode, Job, SummaryArtifact
from podsum.persistence.repo import EpisodeRepo, JobRepo, SummaryArtifactRepo
from podsum.services.ingest import (
    IngestedAudio,
    IngestError,
    PayloadTooLarge,
    UnsupportedMedia,
    ingest_direct_url,
    ingest_local_file,
    ingest_youtube,
)
from podsum.services.pipeline import create_tts_pipeline, create_us1_pipeline

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


def get_session(request: Request) -> Any:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session


SESSION_DEP = Depends(get_session)
SOURCE_TYPE_FORM = Form(default=None, alias="source_type")
UPLOAD_FILE_FIELD = File(default=None)


class BatchConflict(ValueError):
    pass


@router.post("")
async def create_episode(
    request: Request,
    source_type_form: str | None = SOURCE_TYPE_FORM,
    file: UploadFile | None = UPLOAD_FILE_FIELD,
    session: Session = SESSION_DEP,
) -> JSONResponse:
    try:
        source_type, source_ref, ingested = await _ingest_request(
            request,
            source_type_form,
            file,
        )
    except PayloadTooLarge as exc:
        return _api_error(413, "payload_too_large", str(exc))
    except UnsupportedMedia as exc:
        return _api_error(415, "unsupported_media", str(exc))
    except (IngestError, ValueError) as exc:
        return _api_error(400, "bad_input", str(exc))

    if source_type in {"direct_url", "youtube"} and _existing_link(session, source_type, source_ref):
        shutil.rmtree(ingested.normalized_path.parent, ignore_errors=True)
        return _api_error(409, "conflict", "episode already exists for this source")

    episode = _episode_from_ingest(source_type, source_ref, ingested)
    job = Job(episode_id=episode.id, state="queued", attempt=1)
    session.add_all([episode, job])
    session.commit()
    session.refresh(episode)
    session.refresh(job)
    _enqueue_job(request, job)
    return JSONResponse(
        status_code=201,
        content={"episode": _episode_summary(session, episode), "job": _job_payload(job)},
    )


@router.get("")
async def list_episodes(
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    session: Session = SESSION_DEP,
) -> dict[str, Any]:
    del cursor
    items = EpisodeRepo(session).list_recent(limit=min(max(limit, 1), 200), status=status)
    return {"items": [_episode_summary(session, episode) for episode in items], "next_cursor": None}


@router.post("/batch")
async def create_episode_batch(
    request: Request,
    session: Session = SESSION_DEP,
) -> JSONResponse:
    ingested_items: list[tuple[str, str, IngestedAudio]] = []
    try:
        ingested_items = await _ingest_batch_request(request)
        _check_batch_conflicts(session, ingested_items)
    except PayloadTooLarge as exc:
        _cleanup_ingested(ingested_items)
        return _api_error(413, "payload_too_large", str(exc))
    except UnsupportedMedia as exc:
        _cleanup_ingested(ingested_items)
        return _api_error(415, "unsupported_media", str(exc))
    except BatchConflict as exc:
        _cleanup_ingested(ingested_items)
        return _api_error(409, "conflict", str(exc))
    except (IngestError, ValueError) as exc:
        _cleanup_ingested(ingested_items)
        return _api_error(400, "bad_input", str(exc))

    rows: list[tuple[Episode, Job]] = []
    for source_type, source_ref, ingested in ingested_items:
        episode = _episode_from_ingest(source_type, source_ref, ingested)
        job = Job(episode_id=episode.id, state="queued", attempt=1)
        rows.append((episode, job))
        session.add_all([episode, job])
    session.commit()
    for episode, job in rows:
        session.refresh(episode)
        session.refresh(job)
        _enqueue_job(request, job)
    return JSONResponse(
        status_code=201,
        content={
            "items": [
                {"episode": _episode_summary(session, episode), "job": _job_payload(job)}
                for episode, job in rows
            ]
        },
    )


@router.get("/{episode_id}")
async def get_episode(
    episode_id: str,
    session: Session = SESSION_DEP,
) -> JSONResponse:
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found")
    return JSONResponse(content=render_json(_episode_detail(session, episode)))


@router.delete("/{episode_id}")
async def delete_episode(
    episode_id: str,
    session: Session = SESSION_DEP,
) -> Response:
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found")
    data_dir = Path(episode.data_dir)
    session.delete(episode)
    session.commit()
    shutil.rmtree(data_dir, ignore_errors=True)
    return Response(status_code=204)


@router.post("/{episode_id}/retry")
async def retry_episode(
    request: Request,
    episode_id: str,
    session: Session = SESSION_DEP,
) -> JSONResponse:
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found")
    active = session.scalars(
        select(Job).where(Job.episode_id == episode_id, Job.state.in_(JobRepo.ACTIVE_STATES))
    ).first()
    if active is not None:
        return _api_error(409, "conflict", "episode already has an active job")

    latest = JobRepo(session).latest_for_episode(episode_id)
    job = Job(
        episode_id=episode_id,
        state="queued",
        attempt=(latest.attempt + 1) if latest is not None else 1,
        stage_progress=dict(latest.stage_progress) if latest is not None else {},
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    _enqueue_job(request, job)
    return JSONResponse(status_code=202, content=_job_payload(job))


@router.post("/{episode_id}/digest")
async def create_digest(
    request: Request,
    episode_id: str,
    session: Session = SESSION_DEP,
) -> JSONResponse:
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found")

    artifact = SummaryArtifactRepo(session).get_or_create(episode_id)
    if artifact.tts_path and artifact.stage_status.get("tts") == "present" and Path(artifact.tts_path).exists():
        return JSONResponse(content={"tts_path": artifact.tts_path, "status": "present"})

    active = session.scalars(
        select(Job).where(Job.episode_id == episode_id, Job.state.in_(JobRepo.ACTIVE_STATES))
    ).first()
    if active is not None:
        return _api_error(409, "conflict", "episode already has an active job")

    latest = JobRepo(session).latest_for_episode(episode_id)
    job = Job(
        episode_id=episode_id,
        state="queued",
        attempt=(latest.attempt + 1) if latest is not None else 1,
        stage_progress={"requested_stage": "tts"},
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    _enqueue_digest_job(request, job)
    return JSONResponse(status_code=202, content=_job_payload(job))


@router.get("/{episode_id}/files/markdown")
async def get_markdown_file(
    episode_id: str,
    session: Session = SESSION_DEP,
) -> Response:
    artifact = SummaryArtifactRepo(session).get(episode_id)
    return _file_response(artifact.markdown_path if artifact else None, "text/markdown")


@router.get("/{episode_id}/files/json")
async def get_json_file(
    episode_id: str,
    session: Session = SESSION_DEP,
) -> Response:
    artifact = SummaryArtifactRepo(session).get(episode_id)
    return _file_response(artifact.json_path if artifact else None, "application/json")


@router.get("/{episode_id}/files/digest")
async def get_digest_file(
    episode_id: str,
    session: Session = SESSION_DEP,
) -> Response:
    artifact = SummaryArtifactRepo(session).get(episode_id)
    return _file_response(artifact.tts_path if artifact else None, "audio/mpeg")


@router.get("/{episode_id}/files/audio")
async def get_audio_file(
    episode_id: str,
    session: Session = SESSION_DEP,
) -> Response:
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found")
    return _file_response(str(Path(episode.data_dir) / "audio.normalized.mp3"), "audio/mpeg")


async def _ingest_request(
    request: Request,
    source_type_form: str | None,
    file: UploadFile | None,
) -> tuple[str, str, IngestedAudio]:
    settings = request.app.state.settings
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        if source_type_form != "local_file" or file is None:
            raise ValueError("multipart upload requires source_type=local_file and file")
        ingested = await ingest_local_file(file, settings)
        return "local_file", file.filename or ingested.original_path.name, ingested

    payload = await request.json()
    source_type = payload.get("source_type")
    source_ref = payload.get("source_ref")
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise ValueError("source_ref is required")
    if source_type == "direct_url":
        return source_type, source_ref, await ingest_direct_url(source_ref, settings)
    if source_type == "youtube":
        return source_type, source_ref, await ingest_youtube(source_ref, settings)
    raise ValueError("source_type must be local_file, direct_url, or youtube")


async def _ingest_batch_request(request: Request) -> list[tuple[str, str, IngestedAudio]]:
    settings = request.app.state.settings
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        uploads = [item for item in [*form.getlist("files"), *form.getlist("file")] if isinstance(item, UploadFile)]
        if not uploads:
            raise ValueError("multipart batch requires at least one file")
        return [
            ("local_file", upload.filename or "audio", await ingest_local_file(upload, settings))
            for upload in uploads
        ]

    payload = await request.json()
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("batch payload must contain a non-empty items list")
    ingested: list[tuple[str, str, IngestedAudio]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each batch item must be an object")
        source_type = item.get("source_type")
        source_ref = item.get("source_ref")
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError("source_ref is required for URL batch items")
        if source_type == "direct_url":
            ingested.append((source_type, source_ref, await ingest_direct_url(source_ref, settings)))
        elif source_type == "youtube":
            ingested.append((source_type, source_ref, await ingest_youtube(source_ref, settings)))
        else:
            raise ValueError("batch source_type must be direct_url or youtube for JSON requests")
    return ingested


def _check_batch_conflicts(
    session: Session,
    ingested_items: list[tuple[str, str, IngestedAudio]],
) -> None:
    seen: set[tuple[str, str]] = set()
    for source_type, source_ref, _ in ingested_items:
        key = (source_type, source_ref)
        if source_type in {"direct_url", "youtube"}:
            if key in seen or _existing_link(session, source_type, source_ref):
                raise BatchConflict("episode already exists for this source")
            seen.add(key)


def _cleanup_ingested(ingested_items: list[tuple[str, str, IngestedAudio]]) -> None:
    for _, _, ingested in ingested_items:
        shutil.rmtree(ingested.normalized_path.parent, ignore_errors=True)


def _episode_from_ingest(source_type: str, source_ref: str, ingested: IngestedAudio) -> Episode:
    return Episode(
        id=ingested.episode_id,
        source_type=source_type,
        source_ref=source_ref,
        title=ingested.title,
        podcast_name=ingested.podcast_name,
        duration_seconds=ingested.duration_seconds,
        status="pending",
        data_dir=str(ingested.normalized_path.parent),
    )


def _existing_link(session: Session, source_type: str, source_ref: str) -> bool:
    return (
        session.scalars(
            select(Episode).where(Episode.source_type == source_type, Episode.source_ref == source_ref)
        ).first()
        is not None
    )


def _episode_summary(session: Session, episode: Episode) -> dict[str, Any]:
    artifact = SummaryArtifactRepo(session).get(episode.id)
    stage_status = dict(artifact.stage_status) if artifact else {}
    return {
        "id": episode.id,
        "title": episode.title,
        "podcast_name": episode.podcast_name,
        "source_type": episode.source_type,
        "duration_seconds": episode.duration_seconds,
        "language": episode.language,
        "status": episode.status,
        "stage_status": {
            "hook": stage_status.get("hook", "pending"),
            "three_act": stage_status.get("three_act", "pending"),
            "chapters": stage_status.get("chapters", "missing"),
            "entities": stage_status.get("entities", "missing"),
            "tts": stage_status.get("tts", "missing"),
        },
        "created_at": _isoformat(episode.created_at),
        "updated_at": _isoformat(episode.updated_at),
    }


def _episode_detail(session: Session, episode: Episode) -> dict[str, Any]:
    return {
        "episode": episode,
        "artifact": SummaryArtifactRepo(session).get(episode.id) or _empty_artifact(episode.id),
        "chapters": [],
        "entities": [],
    }


def _empty_artifact(episode_id: str) -> SummaryArtifact:
    return SummaryArtifact(
        episode_id=episode_id,
        stage_status={},
        prompt_versions={},
    )


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


def _enqueue_job(request: Request, job: Job) -> None:
    enqueue = getattr(request.app.state, "enqueue_job", None)
    if callable(enqueue):
        enqueue(job)
        return

    tasks: set[asyncio.Task[None]] = getattr(request.app.state, "background_job_tasks", set())
    request.app.state.background_job_tasks = tasks
    task = asyncio.create_task(_run_pipeline_job(request.app, job.id))
    tasks.add(task)
    task.add_done_callback(tasks.discard)


def _enqueue_digest_job(request: Request, job: Job) -> None:
    enqueue = getattr(request.app.state, "enqueue_digest_job", None)
    if callable(enqueue):
        enqueue(job)
        return

    tasks: set[asyncio.Task[None]] = getattr(request.app.state, "background_job_tasks", set())
    request.app.state.background_job_tasks = tasks
    task = asyncio.create_task(_run_digest_job(request.app, job.id))
    tasks.add(task)
    task.add_done_callback(tasks.discard)


async def _run_pipeline_job(app: Any, job_id: str) -> None:
    with app.state.session_factory() as session:
        job = JobRepo(session).get(job_id)
        if job is None:
            return
        pipeline = create_us1_pipeline(
            session,
            app.state.settings,
            asr_client=getattr(app.state, "asr_client", None),
            llm_client=getattr(app.state, "llm_client", None),
        )
        await pipeline.run(job)
        session.commit()


async def _run_digest_job(app: Any, job_id: str) -> None:
    with app.state.session_factory() as session:
        job = JobRepo(session).get(job_id)
        if job is None:
            return
        pipeline = create_tts_pipeline(
            session,
            app.state.settings,
            tts_client=getattr(app.state, "tts_client", None),
        )
        await pipeline.run(job)
        session.commit()


def _file_response(path_value: str | None, media_type: str) -> FileResponse | JSONResponse:
    if path_value is None:
        return _api_error(404, "not_found", "file not found")
    path = Path(path_value)
    if not path.exists():
        return _api_error(404, "not_found", "file not found")
    return FileResponse(path, media_type=media_type)


def _api_error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": {}}},
    )


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
