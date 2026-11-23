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
    # Set when the final is reported (TE-9): the tournament is Complete and the
    # final's winner is the champion. NULL while the tournament is running.
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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


class Match(Base):
    """One match of a single-elimination bracket (TE-6).

    Rounds are numbered from 1 (the first round) to the final; ``position`` is
    the match's 0-based place in its round, top to bottom. Every match except
    the final feeds its winner into ``next_match_id`` as ``team1`` (when
    ``next_slot`` is 1) or ``team2`` (2), so score reporting (TE-9) only has to
    set ``winner_id`` and copy it into that slot.

    ``team1_score`` and ``team2_score`` are the reported result (both NULL
    until reported; always NULL for a bye). A best-of-N series (TE-13) can keep
    these as games won and store the individual games in a table of their own.

    A bye is a first-round match with no ``team2``. It is created already won
    by ``team1``, whose name is already in the next match.
    """

    __tablename__ = "matches"
    __table_args__ = (
        UniqueConstraint(
            "tournament_id",
            "round",
            "position",
            name="uq_matches_tournament_id_round_position",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tournament_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("tournaments.id", ondelete="CASCADE")
    )
    round: Mapped[int] = mapped_column(Integer)
    position: Mapped[int] = mapped_column(Integer)
    # NULL until the team is known (it comes from an unplayed earlier match),
    # or for team2 of a bye.
    team1_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    team2_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    winner_id: Mapped[int | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    is_bye: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    # NULL for the final.
    next_match_id: Mapped[int | None] = mapped_column(
        ForeignKey("matches.id"), nullable=True
    )
    next_slot: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team1_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    team2_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
