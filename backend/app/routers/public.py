from fastapi import APIRouter
from sqlalchemy.orm import Session

from app.routers.bracket import bracket_response
from app.routers.teams import team_list
from app.routers.tournaments import DbSession, get_tournament_or_404, to_public
from app.schemas import TournamentView

router = APIRouter(prefix="/api/tournaments/{tournament_id}", tags=["public"])


def use_snapshot(db: Session) -> None:
    """Make every read in this session's transaction see the same snapshot.

    Postgres runs at READ COMMITTED by default, where each statement sees the
    latest commit: a score reported between reading the tournament and reading
    its matches could show a champion while the status still says In progress.
    REPEATABLE READ pins one snapshot for the transaction. It must be set
    before the first query. SQLite (tests, local use) serializes writes and
    doesn't accept this level, so it is left alone there.
    """
    if db.get_bind().dialect.name == "postgresql":
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})


@router.get("/public", response_model=TournamentView)
def get_public_view(tournament_id: str, db: DbSession) -> TournamentView:
    """Public, read-only: the tournament, its teams and its bracket.

    What the spectator page loads. Contains nothing an organizer link is
    needed for. A live-updates stream (TE-11) can push this same shape.
    """
    use_snapshot(db)
    tournament = get_tournament_or_404(db, tournament_id)
    return TournamentView(
        tournament=to_public(tournament),
        teams=team_list(db, tournament),
        bracket=bracket_response(db, tournament),
    )
