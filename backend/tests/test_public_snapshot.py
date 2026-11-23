"""The public view reads one snapshot (``use_snapshot`` in routers/public.py).

The ``postgres`` tests check, on a real Postgres database, that the view runs
at REPEATABLE READ, that the level doesn't leak into later requests on the
same pooled connection, and that a score committed in the middle of the read
doesn't give a champion while the status still says In progress. They are
skipped on SQLite, which doesn't support this level. Run them with::

    TEST_DATABASE_URL=postgresql://USER:PASS@HOST:5432/DB pytest tests/test_public_snapshot.py

The other tests run everywhere.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import normalize_database_url
from app.db import get_db
from app.main import app
from app.routers import matches as matches_router
from app.routers import public as public_router
from app.routers.public import use_snapshot
from app.schemas import ScoreReport

from .conftest import TEST_DATABASE_URL
from .test_public_view import add_teams, generate, report, url, view
from .test_team_concurrency import postgres

TOURNAMENT = {
    "name": "Friday Night Smash",
    "game": "Super Smash Bros.",
    "format": "single_elimination",
}


@pytest.fixture
def one_connection(engine):
    """A pool holding a single connection, so every request reuses it.

    Depends on ``engine`` for the migrated schema.
    """
    single = create_engine(
        normalize_database_url(TEST_DATABASE_URL), pool_size=1, max_overflow=0
    )
    yield sessionmaker(bind=single, autoflush=False, expire_on_commit=False)
    single.dispose()


@pytest.fixture
def pooled_client(tournament, one_connection):
    """A client whose requests all run on ``one_connection``. Each request's
    session reports its backend and isolation level before it closes.

    Takes ``tournament`` so it is created (through the default client) first.
    """
    seen = []

    def override_get_db():
        with one_connection() as session:
            yield session
            seen.append(connection_state(session))

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), seen
    app.dependency_overrides.clear()


def connection_state(db):
    """(backend pid, isolation level) of the session's current transaction."""
    return (
        db.scalar(text("SELECT pg_backend_pid()")),
        db.scalar(text("SHOW transaction_isolation")),
    )


@pytest.fixture
def tournament(client):
    return client.post("/api/tournaments", json=TOURNAMENT).json()


@pytest.fixture
def admin(tournament):
    return {"X-Admin-Token": tournament["admin_token"]}


def semis_played(client, tournament, admin):
    """A-D seeded 1-4 with both semifinals reported; returns the final."""
    add_teams(client, tournament, admin, ["A", "B", "C", "D"])
    semis = generate(client, tournament, admin)["rounds"][0]["matches"]
    report(client, tournament, admin, semis[0], 3, 1)
    bracket = report(client, tournament, admin, semis[1], 2, 0)
    return bracket["rounds"][1]["matches"][0]


# --- Everywhere -----------------------------------------------------------


def test_use_snapshot_refuses_a_session_that_has_already_queried(db_session):
    # SQLAlchemy would only warn and run at READ COMMITTED; fail loudly instead.
    db_session.execute(text("SELECT 1"))
    with pytest.raises(RuntimeError, match="before the session's first query"):
        use_snapshot(db_session)


def test_use_snapshot_accepts_a_fresh_session(db_session):
    use_snapshot(db_session)
    assert db_session.execute(text("SELECT 1")).scalar() == 1


# --- Postgres -------------------------------------------------------------


@postgres
def test_public_view_on_postgres(client, tournament, admin):
    final = semis_played(client, tournament, admin)
    report(client, tournament, admin, final, 5, 4)

    body = view(client, tournament)

    assert body["tournament"] == client.get(url(tournament)).json()
    assert body["teams"] == client.get(url(tournament, "/teams")).json()
    assert body["bracket"] == client.get(url(tournament, "/bracket")).json()
    assert body["tournament"]["status"] == "complete"
    assert body["bracket"]["champion"]["name"] == "A"


@postgres
def test_public_view_reads_at_repeatable_read(client, tournament, monkeypatch):
    inside = []
    team_list = public_router.team_list

    def recording_team_list(db, t):
        # Runs between the tournament read and the bracket read.
        inside.append(connection_state(db)[1])
        return team_list(db, t)

    monkeypatch.setattr(public_router, "team_list", recording_team_list)

    view(client, tournament)

    assert inside == ["repeatable read"]


@postgres
def test_snapshot_does_not_leak_into_later_requests(pooled_client, tournament):
    client, seen = pooled_client

    view(client, tournament)
    assert client.get(url(tournament)).status_code == 200
    assert client.get(url(tournament, "/teams")).status_code == 200

    (public_pid, public_level), *later = seen
    assert public_level == "repeatable read"
    # The same pooled connection, back at the server default.
    assert later == [(public_pid, "read committed")] * 2


@postgres
def test_score_committed_mid_read_does_not_show_a_champion_in_progress(
    client, engine, tournament, admin, monkeypatch
):
    final = semis_played(client, tournament, admin)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    team_list = public_router.team_list

    def report_final_then_list(db, t):
        # The tournament has been read (In progress); the final is reported
        # and committed elsewhere before the bracket is read.
        with Session() as other:
            matches_router.report_score(
                tournament["id"],
                final["id"],
                ScoreReport(team1_score=5, team2_score=4),
                db=other,
                x_admin_token=admin["X-Admin-Token"],
            )
        return team_list(db, t)

    monkeypatch.setattr(public_router, "team_list", report_final_then_list)
    body = view(client, tournament)
    monkeypatch.undo()

    # Everything from before the report: no half-finished mix.
    assert body["tournament"]["status"] == "in_progress"
    assert body["bracket"]["champion"] is None
    assert body["bracket"]["rounds"][-1]["matches"][0]["winner_id"] is None
    # The report did land; the next read sees all of it.
    after = view(client, tournament)
    assert after["tournament"]["status"] == "complete"
    assert after["bracket"]["champion"]["name"] == "A"
