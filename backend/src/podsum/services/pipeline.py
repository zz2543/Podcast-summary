from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from tenacity import AsyncRetrying, RetryError, stop_after_attempt

from podsum.api.ws_progress import Broadcaster
from podsum.api.ws_progress import broadcaster as default_broadcaster
from podsum.config import Settings
from podsum.domain.chapter_segmenter import ChapterSpan
from podsum.domain.chapter_segmenter import segment as segment_chapters
from podsum.domain.entity_extractor import Entity as DomainEntity
from podsum.domain.entity_extractor import extract as extract_entities
from podsum.domain.prompt_assembler import PromptAssembler
from podsum.domain.quote_verifier import verify_against_segments
from podsum.domain.structured_parser import parse_chapter_payload, parse_one_liner, parse_three_act
from podsum.domain.transcript_postprocess import normalize
from podsum.persistence.models import Chapter, Entity, Episode, Job, TranscriptSegment
from podsum.persistence.repo import (
    ChapterRepo,
    EntityRepo,
    EpisodeRepo,
    JobRepo,
    QuoteRepo,
    SegmentRepo,
    SummaryArtifactRepo,
)
from podsum.services.asr_client import ASRClient, create_asr_client
from podsum.services.digest_script import build as build_digest_script
from podsum.services.ingest import (
    IngestedAudio,
    ingest_direct_url,
    ingest_local_file,
    ingest_youtube,
)
from podsum.services.llm_client import LLMClient, create_llm_client
from podsum.services.tts_client import TTSClient, create_tts_client

StageResult = dict[str, Any] | None
StageRun = Callable[["PipelineContext"], StageResult | Awaitable[StageResult]]


@dataclass(frozen=True)
class Stage:
    name: str
    required: bool
    run: StageRun


@dataclass
class PipelineContext:
    session: Session
    job: Job
    stage: Stage
    stage_progress: dict[str, Any]


class Pipeline:
    def __init__(
        self,
        session: Session,
        *,
        retry_attempts: int = 3,
        broadcaster: Broadcaster = default_broadcaster,
    ) -> None:
        self.session = session
        self.retry_attempts = retry_attempts
        self.broadcaster = broadcaster
        self._stages: list[Stage] = []

    @property
    def stages(self) -> tuple[Stage, ...]:
        return tuple(self._stages)

    def register_stage(self, name: str, *, required: bool, run: StageRun) -> None:
        self._stages.append(Stage(name=name, required=required, run=run))

    async def run(self, job: Job) -> Job:
        optional_failed = False
        for stage in self._stages:
            await self._set_state(job, self._state_for_stage(stage.name))
            await self._record_progress(job, stage.name, {"status": "running"})
            stage_status_before = self._stage_status(job.episode_id)

            context = PipelineContext(
                session=self.session,
                job=job,
                stage=stage,
                stage_progress=dict(job.stage_progress or {}),
            )
            try:
                result = await self._run_with_retries(stage, context)
            except Exception as exc:
                await self._record_progress(
                    job,
                    stage.name,
                    {"status": "failed_after_retries", "error": str(exc)},
                )
                if stage.required:
                    await self._set_state(job, "failed", error=str(exc))
                    return job
                optional_failed = True
                artifact_stage = self._artifact_stage_key(stage.name)
                SummaryArtifactRepo(self.session).update_stage_status(
                    job.episode_id,
                    artifact_stage,
                    "failed_after_retries",
                )
                self.session.commit()
                await self.broadcaster.publish_stage_status(
                    episode_id=job.episode_id,
                    stage=artifact_stage,
                    status="failed_after_retries",
                )
                continue

            await self._record_progress(job, stage.name, {"status": "done", "result": result or {}})
            await self._publish_stage_status_changes(job.episode_id, stage_status_before)

        await self._set_state(job, "partial" if optional_failed else "done")
        return job

    async def _run_with_retries(self, stage: Stage, context: PipelineContext) -> StageResult:
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.retry_attempts),
                reraise=True,
            ):
                with attempt:
                    result = stage.run(context)
                    if inspect.isawaitable(result):
                        result = await result
                    return result
        except RetryError as exc:
            raise exc.last_attempt.exception() from exc
        return None

    async def _record_progress(self, job: Job, stage: str, payload: dict[str, Any]) -> None:
        progress = dict(job.stage_progress or {})
        progress[stage] = payload
        job.stage_progress = progress
        self.session.add(job)
        self.session.commit()
        await self._publish_job_update(job)

    async def _set_state(self, job: Job, state: str, *, error: str | None = None) -> None:
        job.state = state
        job.error = error
        episode_status = self._episode_status_for_job(state)
        episode = EpisodeRepo(self.session).get(job.episode_id)
        if episode is not None:
            episode.status = episode_status
            self.session.add(episode)
        self.session.add(job)
        self.session.commit()
        await self._publish_job_update(job)

    async def _publish_job_update(self, job: Job) -> None:
        await self.broadcaster.publish_job_update(
            {
                "id": job.id,
                "episode_id": job.episode_id,
                "state": job.state,
                "stage_progress": job.stage_progress,
                "attempt": job.attempt,
                "error": job.error,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            },
            episode_status=self._episode_status_for_job(job.state),
        )

    def _stage_status(self, episode_id: str) -> dict[str, str]:
        artifact = SummaryArtifactRepo(self.session).get(episode_id)
        return dict(artifact.stage_status) if artifact is not None else {}

    async def _publish_stage_status_changes(
        self,
        episode_id: str,
        previous: dict[str, str],
    ) -> None:
        current = self._stage_status(episode_id)
        for stage, status in current.items():
            if previous.get(stage) != status:
                await self.broadcaster.publish_stage_status(
                    episode_id=episode_id,
                    stage=stage,
                    status=status,
                )

    @staticmethod
    def _state_for_stage(stage_name: str) -> str:
        if stage_name in {"fetch", "fetching"}:
            return "fetching"
        if stage_name in {"transcribe", "transcribing"}:
            return "transcribing"
        if stage_name == "tts":
            return "tts"
        return "summarizing"

    @staticmethod
    def _episode_status_for_job(state: str) -> str:
        if state in {"done", "partial", "failed"}:
            return state
        return "processing"

    @staticmethod
    def _artifact_stage_key(stage_name: str) -> str:
        if stage_name == "entity_extract":
            return "entities"
        if stage_name in {"chapter_outline", "quote_verify"}:
            return "chapters"
        if stage_name == "summarize_hook":
            return "hook"
        if stage_name == "summarize_three_act":
            return "three_act"
        return stage_name


class _OneLinerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    hook: str


class _ThreeActPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    background: str
    core_argument: str
    conclusion: str


class _CandidateQuotePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    text: str
    start_ms: int


class _ChapterPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    key_points: list[str]
    candidate_quotes: list[_CandidateQuotePayload] = []


class _ChapterOutlinePayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    chapters: list[_ChapterPayload]


class _PathUpload:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.filename = path.name
        self._handle: Any | None = None

    async def read(self, size: int = -1) -> bytes:
        if self._handle is None:
            self._handle = self.path.open("rb")
        return await asyncio.to_thread(self._handle.read, size)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.close()
            self._handle = None


def register_us1_stages(
    pipeline: Pipeline,
    settings: Settings,
    *,
    asr_client: ASRClient | None = None,
    llm_client: LLMClient | None = None,
    prompt_root: Path = Path("prompts"),
) -> Pipeline:
    asr_client = asr_client or create_asr_client(settings)
    llm_client = llm_client or create_llm_client(settings)
    prompt_assembler = PromptAssembler(prompt_root)

    pipeline.register_stage(
        "fetch",
        required=True,
        run=lambda context: _stage_fetch(context, settings),
    )
    pipeline.register_stage(
        "transcribe",
        required=True,
        run=lambda context: _stage_transcribe(context, asr_client),
    )
    pipeline.register_stage(
        "summarize_hook",
        required=True,
        run=lambda context: _stage_summarize_hook(context, llm_client, prompt_assembler),
    )
    pipeline.register_stage(
        "summarize_three_act",
        required=True,
        run=lambda context: _stage_summarize_three_act(context, llm_client, prompt_assembler),
    )
    pipeline.register_stage(
        "chapter_outline",
        required=True,
        run=lambda context: _stage_chapter_outline(context, llm_client, prompt_assembler),
    )
    pipeline.register_stage("quote_verify", required=True, run=_stage_quote_verify)
    pipeline.register_stage(
        "entity_extract",
        required=False,
        run=lambda context: _stage_entity_extract(context, llm_client),
    )
    pipeline.register_stage("export", required=True, run=_stage_export)
    return pipeline


def create_us1_pipeline(
    session: Session,
    settings: Settings,
    *,
    broadcaster: Broadcaster = default_broadcaster,
    asr_client: ASRClient | None = None,
    llm_client: LLMClient | None = None,
) -> Pipeline:
    pipeline = Pipeline(session, broadcaster=broadcaster)
    return register_us1_stages(
        pipeline,
        settings,
        asr_client=asr_client,
        llm_client=llm_client,
    )


def create_tts_pipeline(
    session: Session,
    settings: Settings,
    *,
    broadcaster: Broadcaster = default_broadcaster,
    tts_client: TTSClient | None = None,
) -> Pipeline:
    pipeline = Pipeline(session, broadcaster=broadcaster)
    tts_client = tts_client or create_tts_client(settings)
    pipeline.register_stage("tts", required=False, run=lambda context: _stage_tts(context, tts_client))
    return pipeline


async def _stage_fetch(context: PipelineContext, settings: Settings) -> StageResult:
    episode = _get_episode(context)
    audio_path = _normalized_audio_path(episode)
    if audio_path.exists():
        return {"audio_path": str(audio_path), "cached": True}

    if episode.source_type == "direct_url":
        ingested = await ingest_direct_url(episode.source_ref, settings, episode_id=episode.id)
    elif episode.source_type == "youtube":
        ingested = await ingest_youtube(episode.source_ref, settings, episode_id=episode.id)
    elif episode.source_type == "local_file":
        upload = _PathUpload(Path(episode.source_ref))
        try:
            ingested = await ingest_local_file(upload, settings, episode_id=episode.id)
        finally:
            upload.close()
    else:
        raise ValueError(f"unsupported source type: {episode.source_type}")

    _apply_ingested_audio(episode, ingested)
    context.session.add(episode)
    context.session.flush()
    return {"audio_path": str(ingested.normalized_path), "cached": False}


async def _stage_transcribe(context: PipelineContext, asr_client: ASRClient) -> StageResult:
    episode = _get_episode(context)
    segment_repo = SegmentRepo(context.session)
    existing_segments = segment_repo.list_for_episode(episode.id)
    if existing_segments:
        return {"segments": len(existing_segments), "cached": True}

    audio_path = _normalized_audio_path(episode)
    raw_segments = await asyncio.to_thread(asr_client.transcribe, audio_path, episode.language)
    normalized_segments = normalize(raw_segments, episode.language)
    db_segments = [
        TranscriptSegment(
            episode_id=episode.id,
            idx=segment.idx,
            start_ms=segment.start_ms,
            end_ms=segment.end_ms,
            text=segment.text,
            language=segment.language,
        )
        for segment in normalized_segments
    ]
    segment_repo.replace_for_episode(episode.id, db_segments)
    episode.language = _episode_language(db_segments)
    _write_normalized_transcript(episode, db_segments)
    context.session.add(episode)
    context.session.flush()
    return {"segments": len(db_segments), "cached": False}


def _stage_summarize_hook(
    context: PipelineContext,
    llm_client: LLMClient,
    prompt_assembler: PromptAssembler,
) -> StageResult:
    episode = _get_episode(context)
    transcript = _transcript_text(context.session, episode.id)
    prompt = prompt_assembler.render(
        "one_liner",
        "v1",
        lang=episode.language or "mixed",
        episode_title=episode.title or "",
        transcript=transcript,
    )
    payload = llm_client.complete_json(prompt, _OneLinerPayload)
    hook = parse_one_liner(payload, episode.title or "", episode.language or "mixed")

    artifact = SummaryArtifactRepo(context.session).get_or_create(episode.id)
    artifact.hook = hook
    artifact.stage_status = {**dict(artifact.stage_status), "hook": "present"}
    artifact.prompt_versions = {**dict(artifact.prompt_versions), "one_liner": "v1"}
    context.session.add(artifact)
    context.session.flush()
    return {"hook": hook}


def _stage_summarize_three_act(
    context: PipelineContext,
    llm_client: LLMClient,
    prompt_assembler: PromptAssembler,
) -> StageResult:
    episode = _get_episode(context)
    transcript = _transcript_text(context.session, episode.id)
    prompt = prompt_assembler.render(
        "three_act_summary",
        "v1",
        lang=episode.language or "mixed",
        transcript=transcript,
    )
    payload = llm_client.complete_json(prompt, _ThreeActPayload)
    three_act = parse_three_act(payload)

    artifact = SummaryArtifactRepo(context.session).get_or_create(episode.id)
    artifact.three_act = three_act.model_dump()
    artifact.stage_status = {**dict(artifact.stage_status), "three_act": "present"}
    artifact.prompt_versions = {**dict(artifact.prompt_versions), "three_act": "v1"}
    context.session.add(artifact)
    context.session.flush()
    return {"three_act": artifact.three_act}


def _stage_chapter_outline(
    context: PipelineContext,
    llm_client: LLMClient,
    prompt_assembler: PromptAssembler,
) -> StageResult:
    episode = _get_episode(context)
    segments = SegmentRepo(context.session).list_for_episode(episode.id)
    spans = segment_chapters(segments)
    prompt = prompt_assembler.render(
        "chapter_outline",
        "v1",
        lang=episode.language or "mixed",
        transcript=_chapter_prompt_transcript(spans),
    )
    payload = llm_client.complete_json(prompt, _ChapterOutlinePayload)
    drafts = parse_chapter_payload(payload)

    for chapter in ChapterRepo(context.session).list_for_episode(episode.id):
        context.session.delete(chapter)
    context.session.flush()

    quote_candidates: list[dict[str, Any]] = []
    for idx, draft in enumerate(drafts):
        span = spans[min(idx, len(spans) - 1)] if spans else None
        chapter = Chapter(
            episode_id=episode.id,
            idx=idx,
            title=draft.title,
            start_ms=span.start_ms if span is not None else 0,
            end_ms=span.end_ms if span is not None else max(1, episode.duration_seconds or 1) * 1000,
            key_points=draft.key_points,
        )
        context.session.add(chapter)
        context.session.flush()
        for quote in draft.candidate_quotes:
            quote_candidates.append(
                {
                    "chapter_id": chapter.id,
                    "chapter_idx": idx,
                    "text": quote.text,
                    "start_ms": quote.start_ms,
                }
            )

    progress = dict(context.job.stage_progress or {})
    progress["quote_candidates"] = quote_candidates
    context.job.stage_progress = progress
    context.session.add(context.job)

    artifact = SummaryArtifactRepo(context.session).get_or_create(episode.id)
    artifact.prompt_versions = {**dict(artifact.prompt_versions), "chapter_outline": "v1"}
    context.session.add(artifact)
    context.session.flush()
    return {"chapters": len(drafts), "quote_candidates": len(quote_candidates)}


def _stage_quote_verify(context: PipelineContext) -> StageResult:
    episode = _get_episode(context)
    segments = SegmentRepo(context.session).list_for_episode(episode.id)
    transcript = _transcript_text(context.session, episode.id)
    candidates = (context.job.stage_progress or {}).get("quote_candidates", [])
    if not isinstance(candidates, list):
        candidates = []

    verified_count = 0
    quote_indexes_by_chapter: dict[int, int] = {}
    quote_repo = QuoteRepo(context.session)
    chapter_ids = {chapter.id for chapter in ChapterRepo(context.session).list_for_episode(episode.id)}
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        chapter_id = candidate.get("chapter_id")
        text = candidate.get("text")
        if not isinstance(chapter_id, int) or chapter_id not in chapter_ids or not isinstance(text, str):
            continue
        ok, matched_start_ms = verify_against_segments(text, segments)
        if not ok:
            continue
        quote_index = quote_indexes_by_chapter.get(chapter_id, 0)
        quote_repo.insert_verified(
            chapter_id=chapter_id,
            idx=quote_index,
            text=text,
            start_ms=matched_start_ms if matched_start_ms is not None else int(candidate.get("start_ms", 0)),
            transcript_text=transcript,
        )
        quote_indexes_by_chapter[chapter_id] = quote_index + 1
        verified_count += 1

    artifact = SummaryArtifactRepo(context.session).get_or_create(episode.id)
    artifact.stage_status = {**dict(artifact.stage_status), "chapters": "present"}
    context.session.add(artifact)
    context.session.flush()
    return {"verified_quotes": verified_count}


def _stage_entity_extract(context: PipelineContext, llm_client: LLMClient) -> StageResult:
    episode = _get_episode(context)
    segments = SegmentRepo(context.session).list_for_episode(episode.id)
    entities = extract_entities(segments, llm_client)

    for entity in EntityRepo(context.session).list_for_episode(episode.id):
        context.session.delete(entity)
    for entity in entities:
        context.session.add(_entity_row(episode.id, entity))

    artifact = SummaryArtifactRepo(context.session).get_or_create(episode.id)
    artifact.stage_status = {**dict(artifact.stage_status), "entities": "present"}
    artifact.prompt_versions = {**dict(artifact.prompt_versions), "entity_extraction": "v1"}
    context.session.add(artifact)
    context.session.flush()
    return {"entities": len(entities)}


def _stage_tts(context: PipelineContext, tts_client: TTSClient) -> StageResult:
    from podsum.exporters import json_export

    episode = _get_episode(context)
    artifact = SummaryArtifactRepo(context.session).get_or_create(episode.id)
    digest_path = Path(episode.data_dir) / "digest.mp3"
    if digest_path.exists() and artifact.stage_status.get("tts") == "present":
        artifact.tts_path = str(digest_path)
        context.session.add(artifact)
        context.session.flush()
        return {"tts_path": str(digest_path), "cached": True}

    detail = json_export.render(_episode_detail(context.session, episode))
    script = build_digest_script(detail, episode.language or "en")
    if not script:
        raise ValueError("cannot build an empty digest script")
    tts_client.synthesize(script, episode.language or "en", digest_path)

    artifact.tts_path = str(digest_path)
    artifact.stage_status = {**dict(artifact.stage_status), "tts": "present"}
    context.session.add(artifact)
    context.session.flush()
    return {"tts_path": str(digest_path), "cached": False}


def _stage_export(context: PipelineContext) -> StageResult:
    from podsum.exporters import json_export, markdown

    episode = _get_episode(context)
    detail = _episode_detail(context.session, episode)
    episode_dir = Path(episode.data_dir)

    markdown_path = episode_dir / "summary.md"
    markdown_path.write_text(markdown.render(detail), encoding="utf-8")

    json_path = episode_dir / "summary.json"
    json_path.write_text(
        json.dumps(json_export.render(detail), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    artifact = SummaryArtifactRepo(context.session).get_or_create(episode.id)
    artifact.markdown_path = str(markdown_path)
    artifact.json_path = str(json_path)
    context.session.add(artifact)
    context.session.flush()
    return {"markdown_path": str(markdown_path), "json_path": str(json_path)}


def _get_episode(context: PipelineContext) -> Episode:
    episode = EpisodeRepo(context.session).get(context.job.episode_id)
    if episode is None:
        raise ValueError(f"episode not found: {context.job.episode_id}")
    return episode


def _normalized_audio_path(episode: Episode) -> Path:
    return Path(episode.data_dir) / "audio.normalized.mp3"


def _apply_ingested_audio(episode: Episode, ingested: IngestedAudio) -> None:
    episode.data_dir = str(ingested.normalized_path.parent)
    episode.duration_seconds = ingested.duration_seconds
    episode.title = ingested.title or episode.title
    episode.podcast_name = ingested.podcast_name or episode.podcast_name
    episode.source_ref = ingested.source_ref or episode.source_ref


def _episode_language(segments: list[TranscriptSegment]) -> str | None:
    languages = {segment.language for segment in segments if segment.language}
    if not languages:
        return None
    return languages.pop() if len(languages) == 1 else "mixed"


def _write_normalized_transcript(episode: Episode, segments: list[TranscriptSegment]) -> None:
    path = Path(episode.data_dir) / "transcript.normalized.json"
    payload = [
        {
            "idx": segment.idx,
            "start_ms": segment.start_ms,
            "end_ms": segment.end_ms,
            "text": segment.text,
            "language": segment.language,
        }
        for segment in segments
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _transcript_text(session: Session, episode_id: str) -> str:
    return "\n".join(segment.text for segment in SegmentRepo(session).list_for_episode(episode_id))


def _chapter_prompt_transcript(spans: list[ChapterSpan]) -> str:
    return "\n\n".join(
        f"[{_format_ms(span.start_ms)}-{_format_ms(span.end_ms)}]\n{span.text_window}"
        for span in spans
    )


def _format_ms(value: int) -> str:
    total_seconds = max(0, value // 1000)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def _entity_row(episode_id: str, entity: DomainEntity) -> Entity:
    return Entity(
        episode_id=episode_id,
        name=entity.name,
        kind=entity.kind,
        count=entity.count,
        sample_timestamps_ms=entity.sample_timestamps_ms,
    )


def _episode_detail(session: Session, episode: Episode) -> dict[str, Any]:
    artifact = SummaryArtifactRepo(session).get_or_create(episode.id)
    return {
        "episode": episode,
        "segments": SegmentRepo(session).list_for_episode(episode.id),
        "artifact": artifact,
        "chapters": ChapterRepo(session).list_for_episode(episode.id),
        "entities": EntityRepo(session).list_for_episode(episode.id),
    }


def recover_incomplete_jobs(
    session: Session,
    enqueue: Callable[[Job], None] | None = None,
) -> list[Job]:
    jobs = JobRepo(session).active()
    for job in jobs:
        job.state = "queued"
        session.add(job)
    session.flush()
    if enqueue is not None:
        for job in jobs:
            enqueue(job)
    return jobs
