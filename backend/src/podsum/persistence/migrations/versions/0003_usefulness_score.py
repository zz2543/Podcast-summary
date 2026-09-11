"""usefulness score (FR-027)

Revision ID: 0003_usefulness_score
Revises: 0002_episode_summary_style
Create Date: 2026-09-10 00:00:00.000000

Nullable columns, no backfill: episodes processed before scoring existed stay
unscored and are only rated when the user retries them, so the migration never
calls the LLM.

The CHECK constraints declared on the model apply to freshly created databases;
SQLite cannot add them to an existing table without a full table rebuild, so on
migrated databases the range/band invariants rest on ``parse_usefulness`` and
``band_for``, which are the only writers.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_usefulness_score"
down_revision = "0002_episode_summary_style"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("summary_artifact", sa.Column("usefulness_score", sa.Integer(), nullable=True))
    op.add_column(
        "summary_artifact", sa.Column("usefulness_band", sa.String(length=16), nullable=True)
    )
    op.add_column("summary_artifact", sa.Column("usefulness_rationale", sa.Text(), nullable=True))
    op.create_index("idx_summary_usefulness_score", "summary_artifact", ["usefulness_score"])


def downgrade() -> None:
    op.drop_index("idx_summary_usefulness_score", table_name="summary_artifact")
    op.drop_column("summary_artifact", "usefulness_rationale")
    op.drop_column("summary_artifact", "usefulness_band")
    op.drop_column("summary_artifact", "usefulness_score")
