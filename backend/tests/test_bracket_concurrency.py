"""Bracket generation is serialized with team changes by the tournament lock.

Generation takes ``lock_tournament`` before it reads the teams or
``bracket_generated`` and holds it until it commits. The ``postgres`` tests
check this with real concurrent transactions and are skipped on SQLite (which
ignores ``FOR UPDATE``). Run them with::

    TEST_DATABASE_URL=postgresql://USER:PASS@HOST:5432/DB pytest tests/test_bracket_concurrency.py

``test_bracket_api.py`` checks on every database that generation asks for the
lock.
"""

import threading

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from app.models import Match, Team
from app.routers import bracket as bracket_router
from app.routers import teams as teams_router
from app.routers.bracket import ALREADY_GENERATED
from app.routers.tournaments import lock_tournament
from app.schemas import TeamName
from app.teams import team_name_key

from .test_team_concurrency import Request, postgres, start_while_locked

TOURNAMENT = {
    "name": "Friday Night Smash",
    "game": "Super Smash Bros.",
    "format": "single_elimination",
}


@pytest.fixture
def Session(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def setup(client):
    """A tournament with teams A-D seeded 1-4. Returns (id, token)."""
    created = client.post("/api/tournaments", json=TOURNAMENT).json()
    headers = {"X-Admin-Token": created["admin_token"]}
    url = f"/api/tournaments/{created['id']}/teams"
    ids = [
        client.post(url, json={"name": name}, headers=headers).json()["id"]
        for name in "ABCD"
    ]
    client.put(f"{url}/seeding", json={"team_ids": ids}, headers=headers)
    return created["id"], created["admin_token"]


def match_count(Session, tournament_id):
    with Session() as db:
        return db.scalar(
            select(func.count()).where(Match.tournament_id == tournament_id)
        )


def first_round(bracket):
    return [
        (m.team1 and m.team1.name, m.team2 and m.team2.name)
        for m in bracket.rounds[0].matches
    ]


@postgres
def test_generation_waits_for_a_team_change_and_sees_it(Session, setup):
    tournament_id, token = setup

    def add_e(holder):
        # What add_team does, held open while generation starts.
        holder.add(Team(tournament_id=tournament_id, name="E", name_key="e"))

    generation = Request(
        Session, bracket_router.generate_bracket, tournament_id, x_admin_token=token
    )
    start_while_locked(Session, tournament_id, generation, add_e)

    assert generation.error is None
    # E was committed before generation read the teams: 5 teams, unseeded E
    # is seed 5 and plays seed 4.
    assert first_round(generation.result) == [
        ("A", None),
        ("D", "E"),
        ("B", None),
        ("C", None),
    ]
    assert match_count(Session, tournament_id) == 7


@postgres
def test_generation_waiting_on_another_generation_is_rejected(Session, setup):
    tournament_id, token = setup

    def other_generation(holder):
        # Stands in for a generation that holds the lock and commits first.
        lock_tournament(holder, tournament_id).bracket_generated = True

    generation = Request(
        Session, bracket_router.generate_bracket, tournament_id, x_admin_token=token
    )
    start_while_locked(Session, tournament_id, generation, other_generation)

    assert isinstance(generation.error, HTTPException)
    assert generation.error.status_code == 409
    assert generation.error.detail == ALREADY_GENERATED
    assert match_count(Session, tournament_id) == 0


@postgres
def test_simultaneous_generations_make_one_bracket(Session, setup):
    tournament_id, token = setup
    barrier = threading.Barrier(4)

    def at_once(*args, **kwargs):
        barrier.wait()
        return bracket_router.generate_bracket(*args, **kwargs)

    requests = [
        Request(Session, at_once, tournament_id, x_admin_token=token) for _ in range(4)
    ]
    for request in requests:
        request.start()
    for request in requests:
        request.join(20)

    errors = [r.error for r in requests if r.error is not None]
    assert len(errors) == 3
    assert all(e.status_code == 409 and e.detail == ALREADY_GENERATED for e in errors)
    assert match_count(Session, tournament_id) == 3


@postgres
def test_team_changes_racing_generation_never_land_after_it(Session, setup):
    """Adds and generation at once: every add either made it into the bracket
    or was rejected as locked. None is left out of a generated bracket."""
    tournament_id, token = setup
    barrier = threading.Barrier(7)

    def at_once(endpoint):
        def call(*args, **kwargs):
            barrier.wait()
            return endpoint(*args, **kwargs)

        return call

    adds = [
        Request(
            Session,
            at_once(teams_router.add_team),
            tournament_id,
            TeamName(name=f"Late {i}"),
            x_admin_token=token,
        )
        for i in range(6)
    ]
    generation = Request(
        Session,
        at_once(bracket_router.generate_bracket),
        tournament_id,
        x_admin_token=token,
    )
    for request in [*adds, generation]:
        request.start()
    for request in [*adds, generation]:
        request.join(20)

    assert generation.error is None
    in_bracket = {
        t.name
        for m in generation.result.rounds[0].matches
        for t in (m.team1, m.team2)
        if t
    }
    for add in adds:
        if add.error is None:
            assert add.result.name in in_bracket
        else:
            assert add.error.status_code == 409
            assert add.error.detail == teams_router.TEAMS_LOCKED
    with Session() as db:
        stored = set(
            db.scalars(select(Team.name_key).where(Team.tournament_id == tournament_id))
        )
    assert stored == {team_name_key(n) for n in in_bracket}
