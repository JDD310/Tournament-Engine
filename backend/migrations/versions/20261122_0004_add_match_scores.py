"""Add match scores and tournament completion

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("matches", sa.Column("team1_score", sa.Integer(), nullable=True))
    op.add_column("matches", sa.Column("team2_score", sa.Integer(), nullable=True))
    op.add_column(
        "tournaments",
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    # Batch mode so SQLite (used by the tests) can drop the columns too.
    with op.batch_alter_table("tournaments") as batch_op:
        batch_op.drop_column("completed_at")
    with op.batch_alter_table("matches") as batch_op:
        batch_op.drop_column("team2_score")
        batch_op.drop_column("team1_score")
