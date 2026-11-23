"""Add matches for single-elimination brackets

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "tournament_id",
            sa.String(length=16),
            sa.ForeignKey("tournaments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("round", sa.Integer(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("team1_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("team2_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("winner_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=True),
        sa.Column("is_bye", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "next_match_id",
            sa.Integer(),
            sa.ForeignKey("matches.id"),
            nullable=True,
        ),
        sa.Column("next_slot", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "tournament_id",
            "round",
            "position",
            name="uq_matches_tournament_id_round_position",
        ),
    )


def downgrade() -> None:
    op.drop_table("matches")
