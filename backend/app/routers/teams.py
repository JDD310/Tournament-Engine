from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Team, Tournament
from app.routers.tournaments import (
    AdminToken,
    DbSession,
    get_tournament_or_404,
    require_admin,
)
from app.schemas import TeamList, TeamName, TeamPublic, TeamSeeding
from app.teams import (
    MAX_TEAMS,
    renumber_seeds,
    seed_order,
    team_name_key,
    too_many_teams_message,
)

TEAMS_LOCKED = "The bracket has been generated, so the teams can no longer be changed."

router = APIRouter(prefix="/api/tournaments/{tournament_id}/teams", tags=["teams"])


def duplicate_name_message(name: str) -> str:
    return f'A team named "{name}" is already in this tournament.'


def load_teams(db: Session, tournament_id: str) -> list[Team]:
    teams = db.scalars(select(Team).where(Team.tournament_id == tournament_id))
    return seed_order(teams.all())


def team_list(db: Session, tournament: Tournament) -> TeamList:
    return TeamList(
        locked=tournament.bracket_generated,
        teams=[TeamPublic.model_validate(t) for t in load_teams(db, tournament.id)],
    )


def require_editable(db: Session, tournament_id: str, token: str | None) -> Tournament:
    """The tournament, if the token is valid and the teams are not locked.

    Takes the tournament row lock first, so the lock check and the change that
    follows can't interleave with another team change or bracket generation.
    """
    tournament = require_admin(db, tournament_id, token, lock=True)
    if tournament.bracket_generated:
        raise HTTPException(status.HTTP_409_CONFLICT, TEAMS_LOCKED)
    return tournament


def get_team_or_404(db: Session, tournament_id: str, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None or team.tournament_id != tournament_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found.")
    return team


def ensure_name_available(
    db: Session, tournament_id: str, name: str, exclude_id: int | None = None
) -> str:
    key = team_name_key(name)
    query = select(Team.id).where(
        Team.tournament_id == tournament_id, Team.name_key == key
    )
    if exclude_id is not None:
        query = query.where(Team.id != exclude_id)
    if db.scalar(query) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, duplicate_name_message(name))
    return key


def commit_name_change(db: Session, name: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        # Another request added the same name between our check and commit;
        # the unique constraint caught it.
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, duplicate_name_message(name)
        ) from None


@router.get("", response_model=TeamList)
def list_teams(tournament_id: str, db: DbSession) -> TeamList:
    """Public: anyone with the tournament link can see the teams."""
    return team_list(db, get_tournament_or_404(db, tournament_id))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=TeamPublic)
def add_team(
    tournament_id: str,
    payload: TeamName,
    db: DbSession,
    x_admin_token: AdminToken = None,
) -> TeamPublic:
    """Add a team. New teams are unseeded until the organizer seeds them."""
    require_editable(db, tournament_id, x_admin_token)
    count = db.scalar(select(func.count()).where(Team.tournament_id == tournament_id))
    if count >= MAX_TEAMS:
        raise HTTPException(status.HTTP_409_CONFLICT, too_many_teams_message())
    key = ensure_name_available(db, tournament_id, payload.name)
    team = Team(tournament_id=tournament_id, name=payload.name, name_key=key)
    db.add(team)
    commit_name_change(db, payload.name)
    return TeamPublic.model_validate(team)


@router.patch("/{team_id}", response_model=TeamPublic)
def rename_team(
    tournament_id: str,
    team_id: int,
    payload: TeamName,
    db: DbSession,
    x_admin_token: AdminToken = None,
) -> TeamPublic:
    require_editable(db, tournament_id, x_admin_token)
    team = get_team_or_404(db, tournament_id, team_id)
    team.name_key = ensure_name_available(
        db, tournament_id, payload.name, exclude_id=team.id
    )
    team.name = payload.name
    commit_name_change(db, payload.name)
    return TeamPublic.model_validate(team)


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_team(
    tournament_id: str,
    team_id: int,
    db: DbSession,
    x_admin_token: AdminToken = None,
) -> Response:
    """Remove a team. Teams seeded below it move up one seed."""
    require_editable(db, tournament_id, x_admin_token)
    team = get_team_or_404(db, tournament_id, team_id)
    db.delete(team)
    db.flush()
    renumber_seeds(load_teams(db, tournament_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.put("/seeding", response_model=TeamList)
def set_seeding(
    tournament_id: str,
    payload: TeamSeeding,
    db: DbSession,
    x_admin_token: AdminToken = None,
) -> TeamList:
    """Replace the seed order. Listed teams get seeds 1..n in that order."""
    tournament = require_editable(db, tournament_id, x_admin_token)
    teams = {team.id: team for team in load_teams(db, tournament_id)}
    unknown = [team_id for team_id in payload.team_ids if team_id not in teams]
    if unknown:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"These teams are not in this tournament: {', '.join(map(str, unknown))}.",
        )
    for team in teams.values():
        team.seed = None
    for seed, team_id in enumerate(payload.team_ids, start=1):
        teams[team_id].seed = seed
    db.commit()
    return team_list(db, tournament)
