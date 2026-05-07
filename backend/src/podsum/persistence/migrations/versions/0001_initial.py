"""initial schema

Revision ID: 0001_initial
Revises: None
Create Date: 2026-05-07 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "episode",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("source_ref", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("podcast_name", sa.Text(), nullable=True),
        sa.Column("guests", sa.JSON(), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("data_dir", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('local_file', 'direct_url', 'youtube')",
            name="ck_episode_source_type",
        ),
        sa.CheckConstraint(
            "language IS NULL OR language IN ('zh', 'en', 'mixed')",
            name="ck_episode_language",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'done', 'failed', 'partial')",
            name="ck_episode_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("data_dir"),
    )
    op.create_index("idx_episode_status", "episode", ["status"])
    op.create_index("idx_episode_created", "episode", [sa.text("created_at DESC")])
    op.create_index(
        "uq_episode_source_ref_links",
        "episode",
        ["source_type", "source_ref"],
        unique=True,
        sqlite_where=sa.text("source_type IN ('direct_url', 'youtube')"),
    )

    op.create_table(
        "job",
        sa.Column("id", sa.String(length=26), nullable=False),
        sa.Column("episode_id", sa.String(length=26), nullable=False),
        sa.Column("state", sa.String(length=24), nullable=False),
        sa.Column("stage_progress", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "state IN ('queued', 'fetching', 'transcribing', 'summarizing', 'tts', "
            "'done', 'partial', 'failed')",
            name="ck_job_state",
        ),
        sa.CheckConstraint("attempt > 0", name="ck_job_attempt_positive"),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_job_episode", "job", ["episode_id"])
    op.create_index("idx_job_state", "job", ["state"])

    op.create_table(
        "transcript_segment",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("episode_id", sa.String(length=26), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("language", sa.String(length=16), nullable=True),
        sa.CheckConstraint("end_ms > start_ms", name="ck_segment_end_after_start"),
        sa.CheckConstraint(
            "language IS NULL OR language IN ('zh', 'en')",
            name="ck_segment_language",
        ),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_segment_episode_idx",
        "transcript_segment",
        ["episode_id", "idx"],
        unique=True,
    )
    op.create_index(
        "idx_segment_episode_start",
        "transcript_segment",
        ["episode_id", "start_ms"],
    )

    op.create_table(
        "chapter",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("episode_id", sa.String(length=26), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("end_ms", sa.Integer(), nullable=False),
        sa.Column("key_points", sa.JSON(), nullable=False),
        sa.CheckConstraint("end_ms > start_ms", name="ck_chapter_end_after_start"),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", "idx", name="uq_chapter_episode_idx"),
    )

    op.create_table(
        "entity",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("episode_id", sa.String(length=26), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("sample_timestamps_ms", sa.JSON(), nullable=False),
        sa.CheckConstraint("kind IN ('person', 'book', 'product')", name="ck_entity_kind"),
        sa.CheckConstraint("count > 0", name="ck_entity_count_positive"),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("episode_id", "name", "kind", name="uq_entity_episode_name_kind"),
    )

    op.create_table(
        "summary_artifact",
        sa.Column("episode_id", sa.String(length=26), nullable=False),
        sa.Column("hook", sa.Text(), nullable=True),
        sa.Column("three_act", sa.JSON(), nullable=True),
        sa.Column("markdown_path", sa.Text(), nullable=True),
        sa.Column("json_path", sa.Text(), nullable=True),
        sa.Column("tts_path", sa.Text(), nullable=True),
        sa.Column("stage_status", sa.JSON(), nullable=False),
        sa.Column("prompt_versions", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["episode_id"], ["episode.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("episode_id"),
    )

    op.create_table(
        "quote",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("chapter_id", sa.Integer(), nullable=False),
        sa.Column("idx", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_ms", sa.Integer(), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["chapter_id"], ["chapter.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("chapter_id", "idx", name="uq_quote_chapter_idx"),
    )


def downgrade() -> None:
    op.drop_table("quote")
    op.drop_table("summary_artifact")
    op.drop_table("entity")
    op.drop_table("chapter")
    op.drop_index("idx_segment_episode_start", table_name="transcript_segment")
    op.drop_index("idx_segment_episode_idx", table_name="transcript_segment")
    op.drop_table("transcript_segment")
    op.drop_index("idx_job_state", table_name="job")
    op.drop_index("idx_job_episode", table_name="job")
    op.drop_table("job")
    op.drop_index("uq_episode_source_ref_links", table_name="episode")
    op.drop_index("idx_episode_created", table_name="episode")
    op.drop_index("idx_episode_status", table_name="episode")
    op.drop_table("episode")
