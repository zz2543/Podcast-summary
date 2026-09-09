"""episode summary style

Revision ID: 0002_episode_summary_style
Revises: 0001_initial
Create Date: 2026-09-09 00:00:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_episode_summary_style"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "episode",
        sa.Column(
            "summary_style",
            sa.String(length=32),
            nullable=False,
            server_default="default",
        ),
    )
    op.add_column("episode", sa.Column("style_note", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("episode", "style_note")
    op.drop_column("episode", "summary_style")
