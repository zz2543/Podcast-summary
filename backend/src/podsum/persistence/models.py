from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.ext.mutable import MutableDict, MutableList
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_ulid() -> str:
    from ulid import ULID

    return str(ULID())


class Base(DeclarativeBase):
    pass


class Episode(Base):
    __tablename__ = "episode"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('local_file', 'direct_url', 'youtube')",
            name="ck_episode_source_type",
        ),
        CheckConstraint(
            "language IS NULL OR language IN ('zh', 'en', 'mixed')",
            name="ck_episode_language",
        ),
        CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed', 'partial')",
            name="ck_episode_status",
        ),
        Index("idx_episode_status", "status"),
        Index("idx_episode_created", text("created_at DESC")),
        Index(
            "uq_episode_source_ref_links",
            "source_type",
            "source_ref",
            unique=True,
            sqlite_where=text("source_type IN ('direct_url', 'youtube')"),
        ),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    podcast_name: Mapped[str | None] = mapped_column(Text)
    guests: Mapped[list[str] | None] = mapped_column(MutableList.as_mutable(JSON))
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    language: Mapped[str | None] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)
    data_dir: Mapped[str] = mapped_column(Text, nullable=False, unique=True)

    jobs: Mapped[list[Job]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    transcript_segments: Mapped[list[TranscriptSegment]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    chapters: Mapped[list[Chapter]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    entities: Mapped[list[Entity]] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    summary_artifact: Mapped[SummaryArtifact | None] = relationship(
        back_populates="episode",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )


class Job(Base):
    __tablename__ = "job"
    __table_args__ = (
        CheckConstraint(
            "state IN ('queued', 'fetching', 'transcribing', 'summarizing', 'tts', "
            "'done', 'partial', 'failed')",
            name="ck_job_state",
        ),
        CheckConstraint("attempt > 0", name="ck_job_attempt_positive"),
        Index("idx_job_episode", "episode_id"),
        Index("idx_job_state", "state"),
    )

    id: Mapped[str] = mapped_column(String(26), primary_key=True, default=new_ulid)
    episode_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("episode.id", ondelete="CASCADE"),
        nullable=False,
    )
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    stage_progress: Mapped[dict[str, Any]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    episode: Mapped[Episode] = relationship(back_populates="jobs")


class TranscriptSegment(Base):
    __tablename__ = "transcript_segment"
    __table_args__ = (
        CheckConstraint("end_ms > start_ms", name="ck_segment_end_after_start"),
        CheckConstraint(
            "language IS NULL OR language IN ('zh', 'en')",
            name="ck_segment_language",
        ),
        Index("idx_segment_episode_idx", "episode_id", "idx", unique=True),
        Index("idx_segment_episode_start", "episode_id", "start_ms"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("episode.id", ondelete="CASCADE"),
        nullable=False,
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String(16))

    episode: Mapped[Episode] = relationship(back_populates="transcript_segments")


class Chapter(Base):
    __tablename__ = "chapter"
    __table_args__ = (
        CheckConstraint("end_ms > start_ms", name="ck_chapter_end_after_start"),
        UniqueConstraint("episode_id", "idx", name="uq_chapter_episode_idx"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("episode.id", ondelete="CASCADE"),
        nullable=False,
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    end_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    key_points: Mapped[list[str]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )

    episode: Mapped[Episode] = relationship(back_populates="chapters")
    quotes: Mapped[list[Quote]] = relationship(
        back_populates="chapter",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Quote(Base):
    __tablename__ = "quote"
    __table_args__ = (UniqueConstraint("chapter_id", "idx", name="uq_quote_chapter_idx"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chapter_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("chapter.id", ondelete="CASCADE"),
        nullable=False,
    )
    idx: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    chapter: Mapped[Chapter] = relationship(back_populates="quotes")


class Entity(Base):
    __tablename__ = "entity"
    __table_args__ = (
        CheckConstraint("kind IN ('person', 'book', 'product')", name="ck_entity_kind"),
        CheckConstraint("count > 0", name="ck_entity_count_positive"),
        UniqueConstraint("episode_id", "name", "kind", name="uq_entity_episode_name_kind"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    episode_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("episode.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_timestamps_ms: Mapped[list[int]] = mapped_column(
        MutableList.as_mutable(JSON),
        nullable=False,
        default=list,
    )

    episode: Mapped[Episode] = relationship(back_populates="entities")


class SummaryArtifact(Base):
    __tablename__ = "summary_artifact"

    episode_id: Mapped[str] = mapped_column(
        String(26),
        ForeignKey("episode.id", ondelete="CASCADE"),
        primary_key=True,
    )
    hook: Mapped[str | None] = mapped_column(Text)
    three_act: Mapped[dict[str, str] | None] = mapped_column(MutableDict.as_mutable(JSON))
    markdown_path: Mapped[str | None] = mapped_column(Text)
    json_path: Mapped[str | None] = mapped_column(Text)
    tts_path: Mapped[str | None] = mapped_column(Text)
    stage_status: Mapped[dict[str, str]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )
    prompt_versions: Mapped[dict[str, str]] = mapped_column(
        MutableDict.as_mutable(JSON),
        nullable=False,
        default=dict,
    )

    episode: Mapped[Episode] = relationship(back_populates="summary_artifact")
