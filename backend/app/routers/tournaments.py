from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Tournament, generate_tournament_id
from app.schemas import (
    TournamentCreate,
    TournamentCreated,
    TournamentPublic,
    TournamentUpdate,
)
from app.security import generate_admin_token, hash_admin_token, verify_admin_token

# A 48-bit ID collision is astronomically unlikely, but retrying costs nothing.
CREATE_ATTEMPTS = 3

router = APIRouter(prefix="/api/tournaments", tags=["tournaments"])

AdminToken = Annotated[str | None, Header(alias="X-Admin-Token")]
DbSession = Annotated[Session, Depends(get_db)]


def public_path(tournament_id: str) -> str:
    return f"/t/{tournament_id}"


def admin_path(tournament_id: str, token: str) -> str:
    # The token goes in the fragment, which browsers never send to the server,
    # so it stays out of access logs. The page sends it as X-Admin-Token.
    return f"/t/{tournament_id}/manage#token={token}"


def to_public(tournament: Tournament) -> TournamentPublic:
    return TournamentPublic(
        id=tournament.id,
        name=tournament.name,
        game=tournament.game,
        format=tournament.format,
        created_at=tournament.created_at,
        public_path=public_path(tournament.id),
    )


def get_tournament_or_404(db: Session, tournament_id: str) -> Tournament:
    tournament = db.get(Tournament, tournament_id)
    if tournament is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tournament not found.")
    return tournament


def require_admin(db: Session, tournament_id: str, token: str | None) -> Tournament:
    tournament = get_tournament_or_404(db, tournament_id)
    if not verify_admin_token(token, tournament.admin_token_hash):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "A valid organizer link is required to manage this tournament.",
        )
    return tournament


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TournamentCreated)
def create_tournament(payload: TournamentCreate, db: DbSession) -> TournamentCreated:
    token = generate_admin_token()
    for attempt in range(CREATE_ATTEMPTS):
        tournament = Tournament(
            id=generate_tournament_id(),
            name=payload.name,
            game=payload.game,
            format=payload.format.value,
            admin_token_hash=hash_admin_token(token),
        )
        db.add(tournament)
        try:
            db.commit()
            break
        except IntegrityError:
            # The only unique constraint is the primary key, so this is an ID
            # collision. Roll back and try again with a fresh ID.
            db.rollback()
            if attempt == CREATE_ATTEMPTS - 1:
                raise
    return TournamentCreated(
        **to_public(tournament).model_dump(),
        admin_token=token,
        admin_path=admin_path(tournament.id, token),
    )


@router.get("/{tournament_id}", response_model=TournamentPublic)
def get_tournament(tournament_id: str, db: DbSession) -> TournamentPublic:
    return to_public(get_tournament_or_404(db, tournament_id))


@router.get("/{tournament_id}/admin", response_model=TournamentPublic)
def get_tournament_admin(
    tournament_id: str, db: DbSession, x_admin_token: AdminToken = None
) -> TournamentPublic:
    """Used by the management page to confirm the organizer link is valid."""
    return to_public(require_admin(db, tournament_id, x_admin_token))


@router.patch("/{tournament_id}", response_model=TournamentPublic)
def update_tournament(
    tournament_id: str,
    payload: TournamentUpdate,
    db: DbSession,
    x_admin_token: AdminToken = None,
) -> TournamentPublic:
    tournament = require_admin(db, tournament_id, x_admin_token)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(tournament, field, value)
    db.commit()
    return to_public(tournament)
