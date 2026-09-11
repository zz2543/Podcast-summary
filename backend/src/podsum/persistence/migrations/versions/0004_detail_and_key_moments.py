"""detail level, chapter summary, key-moment takeaway

Revision ID: 0004_detail_and_key_moments
Revises: 0003_usefulness_score
Create Date: 2026-09-11 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_detail_and_key_moments"
down_revision = "0003_usefulness_score"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "episode",
        sa.Column(
            "detail_level",
            sa.String(length=16),
            nullable=False,
            server_default="standard",
        ),
    )
    op.add_column("chapter", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("quote", sa.Column("takeaway", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("quote", "takeaway")
    op.drop_column("chapter", "summary")
    op.drop_column("episode", "detail_level")
