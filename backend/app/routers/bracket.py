from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.bracket import plan_bracket, round_name
from app.models import Match, Team, Tournament
from app.routers.teams import load_teams
from app.routers.tournaments import (
    AdminToken,
    DbSession,
    get_tournament_or_404,
    require_admin,
)
from app.schemas import BracketPublic, BracketTeam, MatchPublic, RoundPublic
from app.teams import bracket_readiness_error

ALREADY_GENERATED = "The bracket has already been generated."

router = APIRouter(prefix="/api/tournaments/{tournament_id}/bracket", tags=["bracket"])


def bracket_response(db: Session, tournament: Tournament) -> BracketPublic:
    if not tournament.bracket_generated:
        return BracketPublic(generated=False, rounds=[])
    teams = {
        team.id: BracketTeam.model_validate(team)
        for team in db.scalars(select(Team).where(Team.tournament_id == tournament.id))
    }
    matches = db.scalars(
        select(Match)
        .where(Match.tournament_id == tournament.id)
        .order_by(Match.round, Match.position)
    ).all()
    rounds = max((m.round for m in matches), default=0)
    by_round: list[RoundPublic] = [
        RoundPublic(round=r, name=round_name(r, rounds), matches=[])
        for r in range(1, rounds + 1)
    ]
    for match in matches:
        by_round[match.round - 1].matches.append(
            MatchPublic(
                id=match.id,
                round=match.round,
                position=match.position,
                team1=teams.get(match.team1_id),
                team2=teams.get(match.team2_id),
                winner_id=match.winner_id,
                is_bye=match.is_bye,
                next_match_id=match.next_match_id,
                next_slot=match.next_slot,
            )
        )
    return BracketPublic(generated=True, rounds=by_round)


@router.get("", response_model=BracketPublic)
def get_bracket(tournament_id: str, db: DbSession) -> BracketPublic:
    """Public: anyone with the tournament link can see the bracket."""
    return bracket_response(db, get_tournament_or_404(db, tournament_id))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=BracketPublic)
def generate_bracket(
    tournament_id: str, db: DbSession, x_admin_token: AdminToken = None
) -> BracketPublic:
    """Generate the single-elimination bracket from the seeded team list.

    Locks the team list. A bracket can only be generated once; there is no
    regenerate or reset.
    """
    # Lock first, so no team change can land between reading the teams and
    # committing the bracket, and two generations can't both pass the check.
    tournament = require_admin(db, tournament_id, x_admin_token, lock=True)
    if tournament.bracket_generated:
        raise HTTPException(status.HTTP_409_CONFLICT, ALREADY_GENERATED)
    teams = load_teams(db, tournament_id)
    error = bracket_readiness_error(len(teams))
    if error:
        raise HTTPException(status.HTTP_409_CONFLICT, error)

    plan = plan_bracket([team.id for team in teams])
    rows: dict[tuple[int, int], Match] = {}
    for planned in (m for round_ in plan for m in round_):
        row = Match(
            tournament_id=tournament_id,
            round=planned.round,
            position=planned.position,
            team1_id=planned.team1,
            team2_id=planned.team2,
            winner_id=planned.winner,
            is_bye=planned.is_bye,
            next_slot=planned.next_slot,
        )
        rows[(planned.round, planned.position)] = row
        db.add(row)
    db.flush()  # Assigns the IDs that next_match_id points at.
    for planned in (m for round_ in plan for m in round_):
        if planned.next is not None:
            rows[(planned.round, planned.position)].next_match_id = rows[
                planned.next
            ].id
    tournament.bracket_generated = True
    db.commit()
    return bracket_response(db, tournament)
