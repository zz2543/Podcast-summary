from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from podsum.domain.quote_verifier import verify
from podsum.persistence.models import (
    Chapter,
    Entity,
    Episode,
    Job,
    Quote,
    SummaryArtifact,
    TranscriptSegment,
)


class EpisodeRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, episode: Episode) -> Episode:
        self.session.add(episode)
        return episode

    def get(self, episode_id: str) -> Episode | None:
        return self.session.get(Episode, episode_id)

    def list_recent(self, *, limit: int = 50, status: str | None = None) -> list[Episode]:
        statement: Select[tuple[Episode]] = select(Episode).order_by(Episode.created_at.desc())
        if status is not None:
            statement = statement.where(Episode.status == status)
        return list(self.session.scalars(statement.limit(limit)))

    def delete(self, episode_id: str) -> bool:
        episode = self.get(episode_id)
        if episode is None:
            return False
        self.session.delete(episode)
        return True


class JobRepo:
    ACTIVE_STATES = {"queued", "fetching", "transcribing", "summarizing", "tts"}

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, job: Job) -> Job:
        self.session.add(job)
        return job

    def get(self, job_id: str) -> Job | None:
        return self.session.get(Job, job_id)

    def active(self) -> list[Job]:
        return list(self.session.scalars(select(Job).where(Job.state.in_(self.ACTIVE_STATES))))

    def latest_for_episode(self, episode_id: str) -> Job | None:
        return self.session.scalars(
            select(Job).where(Job.episode_id == episode_id).order_by(Job.started_at.desc(), Job.id.desc())
        ).first()

    def set_state(self, job: Job, state: str, *, error: str | None = None) -> Job:
        job.state = state
        job.error = error
        return job


class SegmentRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def replace_for_episode(self, episode_id: str, segments: Sequence[TranscriptSegment]) -> None:
        self.session.query(TranscriptSegment).filter_by(episode_id=episode_id).delete()
        for idx, segment in enumerate(segments):
            segment.episode_id = episode_id
            segment.idx = idx
            self.session.add(segment)

    def list_for_episode(self, episode_id: str) -> list[TranscriptSegment]:
        return list(
            self.session.scalars(
                select(TranscriptSegment)
                .where(TranscriptSegment.episode_id == episode_id)
                .order_by(TranscriptSegment.idx)
            )
        )


class ChapterRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, chapter: Chapter) -> Chapter:
        self.session.add(chapter)
        return chapter

    def list_for_episode(self, episode_id: str) -> list[Chapter]:
        return list(
            self.session.scalars(
                select(Chapter).where(Chapter.episode_id == episode_id).order_by(Chapter.idx)
            )
        )


class QuoteRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def insert_verified(
        self,
        *,
        chapter_id: int,
        idx: int,
        text: str,
        start_ms: int,
        transcript_text: str,
    ) -> Quote:
        """Insert a quote only after the FR-012 verifier proves it is verbatim.

        This is the only repository path that sets `Quote.verified=True`; callers must not
        construct verified quotes directly. Read paths also filter to `verified=True`.
        """

        if not verify(text, transcript_text):
            raise ValueError("quote text is not a verified transcript substring")
        quote = Quote(
            chapter_id=chapter_id,
            idx=idx,
            text=text,
            start_ms=start_ms,
            verified=True,
        )
        self.session.add(quote)
        return quote

    def list_verified_for_chapter(self, chapter_id: int) -> list[Quote]:
        return list(
            self.session.scalars(
                select(Quote)
                .where(Quote.chapter_id == chapter_id, Quote.verified.is_(True))
                .order_by(Quote.idx)
            )
        )


class EntityRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, entity: Entity) -> Entity:
        self.session.add(entity)
        return entity

    def list_for_episode(self, episode_id: str) -> list[Entity]:
        return list(
            self.session.scalars(
                select(Entity).where(Entity.episode_id == episode_id).order_by(Entity.kind, Entity.name)
            )
        )


class SummaryArtifactRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get(self, episode_id: str) -> SummaryArtifact | None:
        return self.session.get(SummaryArtifact, episode_id)

    def add(self, artifact: SummaryArtifact) -> SummaryArtifact:
        self.session.add(artifact)
        return artifact

    def get_or_create(self, episode_id: str) -> SummaryArtifact:
        artifact = self.get(episode_id)
        if artifact is not None:
            return artifact
        artifact = SummaryArtifact(
            episode_id=episode_id,
            stage_status={},
            prompt_versions={},
        )
        self.session.add(artifact)
        return artifact

    def update_stage_status(self, episode_id: str, stage: str, status: str) -> SummaryArtifact:
        artifact = self.get_or_create(episode_id)
        stage_status: dict[str, Any] = dict(artifact.stage_status)
        stage_status[stage] = status
        artifact.stage_status = stage_status
        return artifact
