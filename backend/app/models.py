import secrets
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


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
