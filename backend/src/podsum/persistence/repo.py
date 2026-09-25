from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select, delete, func, select, update
from sqlalchemy.orm import Session

from podsum.domain.categorizer import name_key, validate_name
from podsum.domain.quote_verifier import verify
from podsum.persistence.models import (
    Category,
    Chapter,
    Entity,
    Episode,
    Job,
    Quote,
    SummaryArtifact,
    TranscriptSegment,
    utc_now,
)


class EpisodeRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, episode: Episode) -> Episode:
        self.session.add(episode)
        return episode

    def get(self, episode_id: str) -> Episode | None:
        return self.session.get(Episode, episode_id)

    def list_recent(
        self,
        *,
        limit: int = 50,
        status: str | None = None,
        band: str | None = None,
        min_score: int | None = None,
        sort: str = "created_at",
    ) -> list[Episode]:
        """List episodes, newest first by default.

        ``sort="usefulness_score"`` orders by the FR-027 score, highest first,
        with unscored episodes last and ties broken by recency. ``band`` and
        ``min_score`` filter on the score, which excludes unscored episodes.
        """
        statement: Select[tuple[Episode]] = select(Episode)
        if band is not None or min_score is not None or sort == "usefulness_score":
            statement = statement.outerjoin(
                SummaryArtifact, SummaryArtifact.episode_id == Episode.id
            )
        if status is not None:
            statement = statement.where(Episode.status == status)
        if band is not None:
            statement = statement.where(SummaryArtifact.usefulness_band == band)
        if min_score is not None:
            statement = statement.where(SummaryArtifact.usefulness_score >= min_score)
        if sort == "usefulness_score":
            statement = statement.order_by(
                SummaryArtifact.usefulness_score.is_(None),
                SummaryArtifact.usefulness_score.desc(),
                Episode.created_at.desc(),
            )
        else:
            statement = statement.order_by(Episode.created_at.desc())
        return list(self.session.scalars(statement.limit(limit)))

    def delete(self, episode_id: str) -> bool:
        episode = self.get(episode_id)
        if episode is None:
            return False
        self.session.delete(episode)
        return True


class DuplicateCategory(ValueError):
    def __init__(self, existing_id: str) -> None:
        self.existing_id = existing_id
        super().__init__("a category with this name already exists")


class CategoryRepo:
    """Categories and the episode columns that point at them (feature 004).

    Assignment changes go through Core UPDATEs that keep `episode.updated_at`:
    filing a video away is not a change to the episode itself.
    """

    def __init__(self, session: Session) -> None:
        self.session = session

    def list_ordered(self) -> list[Category]:
        return list(self.session.scalars(select(Category).order_by(Category.position, Category.created_at)))

    def counts(self) -> dict[str, int]:
        rows = self.session.execute(
            select(Episode.category_id, func.count())
            .where(Episode.category_id.is_not(None))
            .group_by(Episode.category_id)
        )
        return {category_id: count for category_id, count in rows}

    def uncategorized_count(self) -> int:
        return self.session.scalar(
            select(func.count()).select_from(Episode).where(Episode.category_id.is_(None))
        ) or 0

    def get(self, category_id: str) -> Category | None:
        return self.session.get(Category, category_id)

    def get_by_key(self, key: str) -> Category | None:
        return self.session.scalar(select(Category).where(Category.name_key == key))

    def create(self, name: str, *, origin: str = "user") -> Category:
        display = validate_name(name)
        key = name_key(display)
        existing = self.get_by_key(key)
        if existing is not None:
            raise DuplicateCategory(existing.id)
        last = self.session.scalar(select(func.max(Category.position)))
        category = Category(
            name=display,
            name_key=key,
            position=(last + 1) if last is not None else 0,
            origin=origin,
        )
        self.session.add(category)
        self.session.flush()
        return category

    def rename(self, category: Category, name: str) -> Category:
        display = validate_name(name)
        key = name_key(display)
        existing = self.get_by_key(key)
        if existing is not None and existing.id != category.id:
            raise DuplicateCategory(existing.id)
        category.name = display
        category.name_key = key
        self.session.flush()
        return category

    def delete(self, category: Category) -> int:
        """Delete a category; its videos go back to Uncategorized, unlocked."""
        released = self.session.execute(
            update(Episode)
            .where(Episode.category_id == category.id)
            .values(
                category_id=None,
                category_origin=None,
                category_updated_at=utc_now(),
                updated_at=Episode.updated_at,
            )
        ).rowcount
        self.session.delete(category)
        self.session.flush()
        return released or 0

    def reorder(self, ids: list[str]) -> None:
        categories = {category.id: category for category in self.list_ordered()}
        if len(ids) != len(set(ids)) or set(ids) != set(categories):
            raise ValueError("ids must list every category exactly once")
        for position, category_id in enumerate(ids):
            categories[category_id].position = position
        self.session.flush()

    def assign(self, episode_id: str, category_id: str | None, origin: str | None) -> None:
        self.session.execute(
            update(Episode)
            .where(Episode.id == episode_id)
            .values(
                category_id=category_id,
                category_origin=origin,
                category_updated_at=utc_now(),
                updated_at=Episode.updated_at,
            )
        )
        self.session.expire_all()

    def set_manual(self, episode_id: str, category_id: str | None) -> None:
        """The user placed (or took out) this video: lock it against AI changes."""
        self.assign(episode_id, category_id, "manual")

    def release(self, episode: Episode) -> None:
        """Hand a manually placed video back to AI categorisation, keeping its place."""
        if episode.category_origin != "manual":
            return
        self.assign(episode.id, episode.category_id, "auto" if episode.category_id else None)


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
        # ULIDs sort by creation time. ``started_at`` does not work here: a job
        # gets it only once it runs, so a queued retry would rank below the
        # finished job it is retrying.
        return self.session.scalars(
            select(Job).where(Job.episode_id == episode_id).order_by(Job.id.desc())
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

    def delete_for_chapters(self, chapter_ids: list[int] | set[int]) -> int:
        """Remove all stored quotes for the given chapters.

        Used by the quote_verify stage on a re-run so that re-inserting verified
        quotes does not collide with the existing rows on the
        ``(chapter_id, idx)`` unique constraint.
        """
        ids = list(chapter_ids)
        if not ids:
            return 0
        result = self.session.execute(
            delete(Quote).where(Quote.chapter_id.in_(ids))
        )
        return result.rowcount or 0

    def insert_verified(
        self,
        *,
        chapter_id: int,
        idx: int,
        text: str,
        start_ms: int,
        transcript_text: str,
        takeaway: str | None = None,
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
            takeaway=takeaway,
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
