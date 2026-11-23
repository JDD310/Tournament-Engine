import secrets
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

TEAM_NAME_MAX_LENGTH = 100


def generate_tournament_id() -> str:
    # 8 URL-safe characters (~48 bits) keeps public links short.
    return secrets.token_urlsafe(6)


class Tournament(Base):
    __tablename__ = "tournaments"

    id: Mapped[str] = mapped_column(
        String(16), primary_key=True, default=generate_tournament_id
    )
    name: Mapped[str] = mapped_column(String(100))
    game: Mapped[str] = mapped_column(String(100))
    format: Mapped[str] = mapped_column(String(32))
    # Only a SHA-256 hash of the organizer token is stored, never the token.
    admin_token_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    # Set by bracket generation (TE-6). Once true, the team list is locked.
    bracket_generated: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )


class Team(Base):
    __tablename__ = "teams"
    __table_args__ = (
        UniqueConstraint(
            "tournament_id", "name_key", name="uq_teams_tournament_id_name_key"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("tournaments.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(TEAM_NAME_MAX_LENGTH))
    # The name trimmed, with inner whitespace collapsed and case-folded. Team
    # names must be unique on this key. Case folding can lengthen a string
    # (up to 3x), hence the wider column.
    name_key: Mapped[str] = mapped_column(String(TEAM_NAME_MAX_LENGTH * 3))
    # 1 is the top seed. Seeded teams are numbered 1..n with no gaps; NULL
    # means unseeded, and unseeded teams are placed after the seeded ones.
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
