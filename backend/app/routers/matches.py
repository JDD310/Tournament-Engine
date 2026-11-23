from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from app.models import Match
from app.routers.bracket import bracket_response
from app.routers.tournaments import AdminToken, DbSession, require_admin
from app.schemas import BracketPublic, ScoreReport

MATCH_NOT_FOUND = "Match not found."
BYE_MATCH = "A bye has no score to report: the team advanced automatically."
TEAMS_NOT_KNOWN = "Both teams must be known before this match's score can be reported."
TIE_NOT_ALLOWED = (
    "Elimination matches can't end in a tie. Enter the score that decided "
    "the winner."
)
NEXT_MATCH_PLAYED = (
    "This result can't be changed: the next match has already been reported."
)

router = APIRouter(prefix="/api/tournaments/{tournament_id}/matches", tags=["matches"])


@router.put("/{match_id}/score", response_model=BracketPublic)
def report_score(
    tournament_id: str,
    match_id: int,
    payload: ScoreReport,
    db: DbSession,
    x_admin_token: AdminToken = None,
) -> BracketPublic:
    """Report a match's score, or correct an earlier one.

    The higher score wins and moves into its slot of the next match. A
    correction may change the winner only while the next match is unplayed;
    the old winner is then replaced by the new one there. Reporting the final
    completes the tournament. Returns the updated bracket.
    """
    # Lock before reading any match, and hold it until commit, so reports and
    # corrections on one tournament run one at a time. Two reports feeding the
    # same match, or a correction and a report of the next match, would
    # otherwise each act on what the other is about to change.
    tournament = require_admin(db, tournament_id, x_admin_token, lock=True)
    match = db.get(Match, match_id, populate_existing=True)
    if match is None or match.tournament_id != tournament_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, MATCH_NOT_FOUND)
    if match.is_bye:
        raise HTTPException(status.HTTP_409_CONFLICT, BYE_MATCH)
    if match.team1_id is None or match.team2_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, TEAMS_NOT_KNOWN)
    # Single elimination needs a winner. TE-7: Swiss allows draws.
    if payload.team1_score == payload.team2_score:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, TIE_NOT_ALLOWED)

    next_match = (
        db.get(Match, match.next_match_id, populate_existing=True)
        if match.next_match_id is not None
        else None
    )
    # Once the next match has a result, this one is final: changing it would
    # mean the wrong team played (and maybe won) the next match.
    if next_match is not None and next_match.winner_id is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, NEXT_MATCH_PLAYED)

    winner = (
        match.team1_id if payload.team1_score > payload.team2_score else match.team2_id
    )
    match.team1_score = payload.team1_score
    match.team2_score = payload.team2_score
    match.winner_id = winner
    if next_match is not None:
        # Also replaces the old winner when a correction changes the result.
        if match.next_slot == 1:
            next_match.team1_id = winner
        else:
            next_match.team2_id = winner
    elif tournament.completed_at is None:
        # The final: the tournament is Complete. A later correction of the
        # final changes the champion but keeps the original completion time.
        tournament.completed_at = datetime.now(timezone.utc)
    db.commit()
    return bracket_response(db, tournament)
