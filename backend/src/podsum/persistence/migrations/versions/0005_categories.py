"""user categories and per-episode category assignment

Revision ID: 0005_categories
Revises: 0004_detail_and_key_moments
Create Date: 2026-09-24 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_categories"
down_revision = "0004_detail_and_key_moments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "category",
        sa.Column("id", sa.String(length=26), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("name_key", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=8), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("origin IN ('user', 'ai')", name="ck_category_origin"),
        sa.UniqueConstraint("name_key", name="uq_category_name_key"),
    )
    op.create_index("idx_category_position", "category", ["position"])

    # SQLite cannot add a CHECK or a foreign key to an existing table in place;
    # batch mode rebuilds the table with them.
    with op.batch_alter_table("episode") as batch:
        batch.add_column(sa.Column("category_id", sa.String(length=26), nullable=True))
        batch.add_column(sa.Column("category_origin", sa.String(length=8), nullable=True))
        batch.add_column(
            sa.Column("category_updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.create_foreign_key(
            "fk_episode_category_id", "category", ["category_id"], ["id"]
        )
        batch.create_check_constraint(
            "ck_episode_category_origin",
            "category_origin IS NULL OR category_origin IN ('manual', 'auto')",
        )
        batch.create_index("idx_episode_category", ["category_id"])
    _restore_created_desc_index()


def downgrade() -> None:
    with op.batch_alter_table("episode") as batch:
        batch.drop_index("idx_episode_category")
        batch.drop_constraint("ck_episode_category_origin", type_="check")
        batch.drop_constraint("fk_episode_category_id", type_="foreignkey")
        batch.drop_column("category_updated_at")
        batch.drop_column("category_origin")
        batch.drop_column("category_id")
    _restore_created_desc_index()
    op.drop_index("idx_category_position", table_name="category")
    op.drop_table("category")


def _restore_created_desc_index() -> None:
    # The batch rebuild reflects idx_episode_created without its DESC.
    op.drop_index("idx_episode_created", table_name="episode")
    op.create_index("idx_episode_created", "episode", [sa.text("created_at DESC")])
