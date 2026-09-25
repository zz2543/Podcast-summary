from __future__ import annotations

import asyncio
import json
import shutil
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from podsum.domain import summary_style as style_rules
from podsum.exporters.json_export import render as render_json
from podsum.persistence.models import Episode, Job, SummaryArtifact
from podsum.persistence.repo import (
    CategoryRepo,
    ChapterRepo,
    EntityRepo,
    EpisodeRepo,
    JobRepo,
    SegmentRepo,
    SummaryArtifactRepo,
)
from podsum.services import cover as cover_images
from podsum.services.ingest import (
    IngestedAudio,
    IngestError,
    PayloadTooLarge,
    UnsupportedMedia,
    extract_url,
    ingest_direct_url,
    ingest_local_file,
    ingest_video,
    normalize_video_url,
    video_identity,
)
from podsum.services.llm_client import create_llm_client
from podsum.services.pipeline import (
    create_tts_pipeline,
    create_us1_pipeline,
    derive_episode_status,
    is_digest_job,
)

router = APIRouter(prefix="/api/episodes", tags=["episodes"])


def get_session(request: Request) -> Any:
    session_factory = request.app.state.session_factory
    with session_factory() as session:
        yield session


SESSION_DEP = Depends(get_session)

USEFULNESS_BANDS = {"must_listen", "worth_listening", "skimmable", "skippable"}
SOURCE_TYPE_FORM = Form(default=None, alias="source_type")
SUMMARY_STYLE_FORM = Form(default=None, alias="summary_style")
STYLE_NOTE_FORM = Form(default=None, alias="style_note")
DETAIL_LEVEL_FORM = Form(default=None, alias="detail_level")
UPLOAD_FILE_FIELD = File(default=None)


class BatchConflict(ValueError):
    pass


class DuplicateSource(ValueError):
    """The link is already in the library; found before anything is downloaded."""

    def __init__(self, episode_id: str) -> None:
        super().__init__("episode already exists for this source")
        self.episode_id = episode_id


@router.post("")
async def create_episode(
    request: Request,
    source_type_form: str | None = SOURCE_TYPE_FORM,
    summary_style_form: str | None = SUMMARY_STYLE_FORM,
    style_note_form: str | None = STYLE_NOTE_FORM,
    detail_level_form: str | None = DETAIL_LEVEL_FORM,
    file: UploadFile | None = UPLOAD_FILE_FIELD,
    session: Session = SESSION_DEP,
) -> JSONResponse:
    try:
        source_type, source_ref, ingested, style = await _ingest_request(
            request,
            source_type_form,
            file,
            summary_style_form,
            style_note_form,
            detail_level_form,
            session,
        )
    except DuplicateSource as exc:
        return _api_error(409, "conflict", str(exc), {"episode_id": exc.episode_id})
    except PayloadTooLarge as exc:
        return _api_error(413, "payload_too_large", str(exc))
    except UnsupportedMedia as exc:
        return _api_error(415, "unsupported_media", str(exc))
    except (IngestError, ValueError) as exc:
        return _api_error(400, "bad_input", str(exc))

    # Checked again after the download: the same link may have been submitted
    # twice at once, and the first request won while this one was fetching.
    existing = _existing_episode_id(session, source_type, source_ref)
    if source_type in {"direct_url", "youtube"} and existing is not None:
        shutil.rmtree(ingested.normalized_path.parent, ignore_errors=True)
        return _api_error(409, "conflict", "episode already exists for this source", {"episode_id": existing})

    episode = _episode_from_ingest(source_type, source_ref, ingested, style)
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
    request: Request,
    limit: int = 50,
    cursor: str | None = None,
    status: str | None = None,
    band: str | None = None,
    min_score: int | None = None,
    sort: str = "created_at",
    session: Session = SESSION_DEP,
) -> Any:
    del cursor
    if band is not None and band not in USEFULNESS_BANDS:
        return _api_error(400, "bad_input", f"unknown band: {band}")
    if min_score is not None and not 0 <= min_score <= 100:
        return _api_error(400, "bad_input", "min_score must be within 0-100")
    if sort not in {"created_at", "usefulness_score"}:
        return _api_error(400, "bad_input", f"unknown sort: {sort}")
    items = EpisodeRepo(session).list_recent(
        limit=min(max(limit, 1), 200),
        status=status,
        band=band,
        min_score=min_score,
        sort=sort,
    )
    data_root = request.app.state.settings.DATA_DIR
    return {
        "items": [_episode_summary(session, episode, data_root) for episode in items],
        "next_cursor": None,
    }


@router.post("/batch")
async def create_episode_batch(
    request: Request,
    session: Session = SESSION_DEP,
) -> JSONResponse:
    ingested_items: list[tuple[str, str, IngestedAudio, style_rules.SummaryStyle]] = []
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
    for source_type, source_ref, ingested, style in ingested_items:
        episode = _episode_from_ingest(source_type, source_ref, ingested, style)
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
    payload = render_json(_episode_detail(session, episode))
    payload["last_failure"] = _last_failure(session, episode.id)
    payload.update(_category_payload(episode))
    return JSONResponse(content=payload)


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


@router.put("/{episode_id}/category")
async def set_episode_category(
    episode_id: str,
    body: dict[str, Any],
    session: Session = SESSION_DEP,
) -> JSONResponse:
    """Place a video in a category by hand, or take it out (null). Locks it (FR-009)."""
    if "category_id" not in body or not isinstance(body["category_id"], str | None):
        return _api_error(400, "bad_input", "category_id must be a string or null")
    category_id = body["category_id"]
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found", {"missing": "episode"})
    categories = CategoryRepo(session)
    if category_id is not None and categories.get(category_id) is None:
        return _api_error(404, "not_found", "category not found", {"missing": "category"})
    categories.set_manual(episode_id, category_id)
    session.commit()
    return JSONResponse(content=_category_payload(EpisodeRepo(session).get(episode_id)))


@router.post("/{episode_id}/category/release")
async def release_episode_category(
    episode_id: str,
    session: Session = SESSION_DEP,
) -> JSONResponse:
    """"Let AI categorize": unlock a manually placed video without moving it (FR-011)."""
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found", {"missing": "episode"})
    CategoryRepo(session).release(episode)
    session.commit()
    return JSONResponse(content=_category_payload(EpisodeRepo(session).get(episode_id)))


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
        # Start clean: every stage records its own progress again. Copying the
        # last job's map carried its failures — and a digest job's
        # ``requested_stage`` — into a run that had not reached them yet.
        stage_progress={},
    )
    session.add(job)
    session.flush()
    episode.status = derive_episode_status(session, episode_id)
    session.add(episode)
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
    if not request.app.state.settings.TTS_ENABLED:
        return _api_error(400, "tts_disabled", "audio digests are turned off in settings")

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


@router.get("/{episode_id}/files/cover")
async def get_cover_file(
    episode_id: str,
    request: Request,
    session: Session = SESSION_DEP,
) -> Response:
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found")
    path = cover_images.episode_cover_path(
        episode.data_dir, episode.id, request.app.state.settings.DATA_DIR
    )
    return _file_response(str(path), "image/jpeg")


@router.get("/{episode_id}/files/transcript")
async def get_transcript_file(
    episode_id: str,
    session: Session = SESSION_DEP,
) -> Response:
    segments = SegmentRepo(session).list_for_episode(episode_id)
    if not segments:
        return _api_error(404, "not_found", "no transcript available")
    text = "\n".join(seg.text for seg in segments)
    return Response(
        content=text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="transcript.txt"'},
    )


@router.post("/{episode_id}/chat", response_model=None)
async def chat_episode(
    episode_id: str,
    request: Request,
    session: Session = SESSION_DEP,
) -> StreamingResponse | JSONResponse:
    episode = EpisodeRepo(session).get(episode_id)
    if episode is None:
        return _api_error(404, "not_found", "episode not found")

    segments = SegmentRepo(session).list_for_episode(episode_id)
    if not segments:
        return _api_error(422, "no_transcript", "no transcript available for this episode")

    body = await request.json()
    message = str(body.get("message", "")).strip()
    if not message:
        return _api_error(400, "bad_input", "message is required")
    history: list[dict] = body.get("history", [])

    transcript = " ".join(seg.text for seg in segments)
    if len(transcript) > 80_000:
        transcript = transcript[:80_000] + "…"

    system_content = (
        "你是一个播客内容助手。以下是这期播客的转录文稿，请基于文稿内容回答用户的问题。\n\n"
        f"播客标题：{episode.title or '未知'}\n\n"
        f"转录文稿：\n{transcript}"
    )
    messages: list[dict] = [{"role": "system", "content": system_content}]
    for msg in history:
        if isinstance(msg, dict) and msg.get("role") in {"user", "assistant"}:
            messages.append({"role": msg["role"], "content": str(msg.get("content", ""))})
    messages.append({"role": "user", "content": message})

    llm = getattr(request.app.state, "llm_client", None) or create_llm_client(request.app.state.settings)

    async def event_stream() -> AsyncIterator[str]:
        try:
            async for token in llm.stream_chat(messages):
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'error': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _ingest_request(
    request: Request,
    source_type_form: str | None,
    file: UploadFile | None,
    summary_style_form: str | None,
    style_note_form: str | None,
    detail_level_form: str | None,
    session: Session,
) -> tuple[str, str, IngestedAudio, style_rules.SummaryStyle]:
    settings = request.app.state.settings
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        if source_type_form != "local_file" or file is None:
            raise ValueError("multipart upload requires source_type=local_file and file")
        # Style is validated before the upload is normalised, so a bad preset
        # fails fast instead of leaving a half-ingested directory behind.
        style = style_rules.parse(summary_style_form, style_note_form, detail_level_form)
        ingested = await ingest_local_file(file, settings)
        return "local_file", file.filename or ingested.original_path.name, ingested, style

    payload = await request.json()
    source_type = payload.get("source_type")
    source_ref = payload.get("source_ref")
    if not isinstance(source_ref, str) or not source_ref.strip():
        raise ValueError("source_ref is required")
    style = style_rules.parse(
        payload.get("summary_style"),
        payload.get("style_note"),
        payload.get("detail_level"),
    )
    if source_type == "direct_url":
        # Only the URL is extracted here: a direct link may be presigned, so its
        # query string has to survive intact.
        source_ref = extract_url(source_ref)
        _reject_duplicate(session, source_type, source_ref)
        return source_type, source_ref, await ingest_direct_url(source_ref, settings), style
    if source_type == "youtube":
        source_ref = normalize_video_url(source_ref)
        # A video already in the library answers at once instead of after a
        # full download that would only be thrown away.
        _reject_duplicate(session, source_type, source_ref)
        return source_type, source_ref, await ingest_video(source_ref, settings), style
    raise ValueError("source_type must be local_file, direct_url, or youtube")


async def _ingest_batch_request(
    request: Request,
) -> list[tuple[str, str, IngestedAudio, style_rules.SummaryStyle]]:
    settings = request.app.state.settings
    content_type = request.headers.get("content-type", "")
    if content_type.startswith("multipart/form-data"):
        form = await request.form()
        uploads = [item for item in [*form.getlist("files"), *form.getlist("file")] if isinstance(item, UploadFile)]
        if not uploads:
            raise ValueError("multipart batch requires at least one file")
        # One style for the whole batch: the submit modal styles a submission,
        # not a file.
        style = style_rules.parse(
            form.get("summary_style"),
            form.get("style_note"),
            form.get("detail_level"),
        )
        return [
            ("local_file", upload.filename or "audio", await ingest_local_file(upload, settings), style)
            for upload in uploads
        ]

    payload = await request.json()
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("batch payload must contain a non-empty items list")
    batch_style = style_rules.parse(
        payload.get("summary_style"),
        payload.get("style_note"),
        payload.get("detail_level"),
    )
    ingested: list[tuple[str, str, IngestedAudio, style_rules.SummaryStyle]] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("each batch item must be an object")
        source_type = item.get("source_type")
        source_ref = item.get("source_ref")
        if not isinstance(source_ref, str) or not source_ref.strip():
            raise ValueError("source_ref is required for URL batch items")
        style = (
            style_rules.parse(
                item.get("summary_style"),
                item.get("style_note"),
                item.get("detail_level"),
            )
            if {"summary_style", "style_note", "detail_level"} & item.keys()
            else batch_style
        )
        if source_type == "direct_url":
            source_ref = extract_url(source_ref)
            ingested.append((source_type, source_ref, await ingest_direct_url(source_ref, settings), style))
        elif source_type == "youtube":
            source_ref = normalize_video_url(source_ref)
            ingested.append((source_type, source_ref, await ingest_video(source_ref, settings), style))
        else:
            raise ValueError("batch source_type must be direct_url or youtube for JSON requests")
    return ingested


def _check_batch_conflicts(
    session: Session,
    ingested_items: list[tuple[str, str, IngestedAudio, style_rules.SummaryStyle]],
) -> None:
    seen: set[tuple[str, str]] = set()
    for source_type, source_ref, _, _ in ingested_items:
        key = (source_type, source_ref)
        if source_type in {"direct_url", "youtube"}:
            if key in seen or _existing_link(session, source_type, source_ref):
                raise BatchConflict("episode already exists for this source")
            seen.add(key)


def _cleanup_ingested(
    ingested_items: list[tuple[str, str, IngestedAudio, style_rules.SummaryStyle]],
) -> None:
    for _, _, ingested, _ in ingested_items:
        shutil.rmtree(ingested.normalized_path.parent, ignore_errors=True)


def _episode_from_ingest(
    source_type: str,
    source_ref: str,
    ingested: IngestedAudio,
    style: style_rules.SummaryStyle,
) -> Episode:
    return Episode(
        id=ingested.episode_id,
        source_type=source_type,
        source_ref=source_ref,
        title=ingested.title,
        podcast_name=ingested.podcast_name,
        duration_seconds=ingested.duration_seconds,
        status="pending",
        summary_style=style.preset,
        style_note=style.note,
        detail_level=style.detail,
        data_dir=str(ingested.normalized_path.parent),
    )


def _existing_link(session: Session, source_type: str, source_ref: str) -> bool:
    return _existing_episode_id(session, source_type, source_ref) is not None


def _existing_episode_id(session: Session, source_type: str, source_ref: str) -> str | None:
    exact = session.scalars(
        select(Episode.id).where(Episode.source_type == source_type, Episode.source_ref == source_ref)
    ).first()
    if exact is not None or source_type != "youtube":
        return exact
    # The same video written another way (trailing slash, tracking parameters,
    # youtu.be vs watch?v=), including rows stored before links were normalised.
    identity = video_identity(source_ref)
    if identity is None:
        return None
    rows = session.execute(
        select(Episode.id, Episode.source_ref).where(Episode.source_type == "youtube")
    )
    return next((episode_id for episode_id, ref in rows if video_identity(ref) == identity), None)


def _reject_duplicate(session: Session, source_type: str, source_ref: str) -> None:
    existing = _existing_episode_id(session, source_type, source_ref)
    if existing is not None:
        raise DuplicateSource(existing)


def _episode_summary(
    session: Session, episode: Episode, data_root: Path | None = None
) -> dict[str, Any]:
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
            "usefulness": stage_status.get("usefulness", "missing"),
            "tts": stage_status.get("tts", "missing"),
        },
        "usefulness": _usefulness_payload(artifact, stage_status),
        "last_failure": _last_failure(session, episode.id),
        "has_cover": _has_cover(episode, data_root),
        **_category_payload(episode),
        "created_at": _isoformat(episode.created_at),
        "updated_at": _isoformat(episode.updated_at),
    }


def _category_payload(episode: Episode) -> dict[str, Any]:
    category = episode.category
    return {
        "category": {"id": category.id, "name": category.name} if category is not None else None,
        "category_origin": episode.category_origin,
    }


def _has_cover(episode: Episode, data_root: Path | None) -> bool:
    if not episode.data_dir:
        return False
    return cover_images.episode_cover_path(episode.data_dir, episode.id, data_root).is_file()


def _last_failure(session: Session, episode_id: str) -> dict[str, Any] | None:
    """Why the latest summary job stopped, or None when it did not fail.

    Kept apart from ``status``: an episode whose re-run failed is still ``done``
    when the first run's sections are all there, and the reader should see
    both facts — a readable summary, and that the re-run did not take.
    """
    job = next(
        (
            job
            for job in session.scalars(
                select(Job).where(Job.episode_id == episode_id).order_by(Job.id.desc())
            )
            if not is_digest_job(job)
        ),
        None,
    )
    if job is None or job.state != "failed":
        return None
    failed_stages = [
        name
        for name, entry in (job.stage_progress or {}).items()
        if isinstance(entry, dict) and entry.get("status") == "failed_after_retries"
    ]
    return {
        "job_id": job.id,
        "stage": failed_stages[-1] if failed_stages else None,
        "error": job.error or "",
        "attempt": job.attempt,
        "finished_at": _isoformat(job.finished_at),
    }


def _usefulness_payload(
    artifact: SummaryArtifact | None,
    stage_status: dict[str, Any],
) -> dict[str, Any] | None:
    """FR-027 rating, or None when unscored — the UI shows "未评分", never a 0."""
    if artifact is None or stage_status.get("usefulness") != "present":
        return None
    if artifact.usefulness_score is None or not artifact.usefulness_band:
        return None
    return {
        "score": artifact.usefulness_score,
        "band": artifact.usefulness_band,
        "rationale": artifact.usefulness_rationale or "",
    }


def _episode_detail(session: Session, episode: Episode) -> dict[str, Any]:
    return {
        "episode": episode,
        "artifact": SummaryArtifactRepo(session).get(episode.id) or _empty_artifact(episode.id),
        "chapters": ChapterRepo(session).list_for_episode(episode.id),
        "entities": EntityRepo(session).list_for_episode(episode.id),
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
            llm_client=getattr(app.state, "llm_client", None),
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


def _api_error(
    status_code: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "details": details or {}}},
    )


def _isoformat(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None
