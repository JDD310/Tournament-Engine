"""Create tournaments table

Revision ID: 0001
Revises:
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tournaments",
        sa.Column("id", sa.String(length=16), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("game", sa.String(length=100), nullable=False),
        sa.Column("format", sa.String(length=32), nullable=False),
        sa.Column("admin_token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("tournaments")
