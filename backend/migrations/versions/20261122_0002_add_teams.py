"""Add teams and the tournaments.bracket_generated lock flag

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tournaments",
        sa.Column(
            "bracket_generated",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tournament_id",
            sa.String(length=16),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("name_key", sa.String(length=300), nullable=False),
        sa.Column("seed", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "tournament_id", "name_key", name="uq_teams_tournament_id_name_key"
        ),
    )


def downgrade() -> None:
    op.drop_table("teams")
    # Batch mode so SQLite (used by the tests) can drop the column too.
    with op.batch_alter_table("tournaments") as batch_op:
        batch_op.drop_column("bracket_generated")
