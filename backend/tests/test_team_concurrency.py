"""Concurrent team changes are serialized by a row lock on the tournament.

Every team change starts with ``lock_tournament`` (``SELECT ... FOR UPDATE``).

* The tests marked ``postgres`` run two transactions at once on real
  connections and check that the second one waits for the first. They need a
  database with row locks, so they are skipped on SQLite (which ignores
  ``FOR UPDATE``). Run them with::

      TEST_DATABASE_URL=postgresql://USER:PASS@HOST:5432/DB pytest tests/test_team_concurrency.py

* The other tests run everywhere. They only prove that every team change asks
  for the lock and that the lock query is ``FOR UPDATE`` on Postgres; they say
  nothing about how SQLite behaves under concurrency.
"""

import threading

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import sessionmaker

from app.models import Team
from app.routers import teams as teams_router
from app.routers import tournaments as tournaments_router
from app.routers.tournaments import lock_tournament, tournament_lock_query
from app.schemas import TeamName, TeamSeeding
from app.teams import renumber_seeds, seed_order

from .conftest import TEST_DATABASE_URL

# How long a request must stay blocked before we accept that it is waiting on
# the lock rather than just being slow.
BLOCKED_FOR = 0.5

TOURNAMENT = {
    "name": "Friday Night Smash",
    "game": "Super Smash Bros.",
    "format": "single_elimination",
}

postgres = pytest.mark.skipif(
    not (TEST_DATABASE_URL or "").startswith("postgres"),
    reason="needs row locks; set TEST_DATABASE_URL to a Postgres database",
)


@pytest.fixture
def Session(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture
def setup(client):
    """A tournament with teams A-D seeded 1-4. Returns (id, token, team ids)."""
    created = client.post("/api/tournaments", json=TOURNAMENT).json()
    headers = {"X-Admin-Token": created["admin_token"]}
    url = f"/api/tournaments/{created['id']}/teams"
    ids = [
        client.post(url, json={"name": name}, headers=headers).json()["id"]
        for name in "ABCD"
    ]
    client.put(f"{url}/seeding", json={"team_ids": ids}, headers=headers)
    return created["id"], created["admin_token"], dict(zip("ABCD", ids))


def seeds(Session, tournament_id):
    with Session() as db:
        teams = db.scalars(select(Team).where(Team.tournament_id == tournament_id))
        return [(t.name, t.seed) for t in seed_order(teams.all())]


class Request(threading.Thread):
    """Runs one endpoint call in its own session and keeps the outcome."""

    def __init__(self, Session, endpoint, *args, **kwargs):
        super().__init__(daemon=True)
        self.Session, self.endpoint = Session, endpoint
        self.args, self.kwargs = args, kwargs
        self.result = self.error = None

    def run(self):
        with self.Session() as db:
            try:
                self.result = self.endpoint(*self.args, db=db, **self.kwargs)
            except Exception as exc:  # noqa: BLE001  (reported by the test)
                self.error = exc


def start_while_locked(Session, tournament_id, request, change):
    """Hold the tournament lock, start ``request``, check it waits, then make
    ``change`` in the locking transaction and commit it."""
    with Session() as holder:
        lock_tournament(holder, tournament_id)
        request.start()
        request.join(BLOCKED_FOR)
        assert request.is_alive(), "the request did not wait for the lock"
        change(holder)
        holder.commit()
    request.join(10)
    assert not request.is_alive()


# --- Postgres: real concurrent transactions ------------------------------


@postgres
def test_concurrent_removes_keep_seeds_contiguous(Session, setup):
    """Seeds 1-4; B (2) and C (3) are removed at the same time."""
    tournament_id, token, ids = setup

    def remove_b(holder):
        # What remove_team does, but held open while C's removal starts.
        holder.delete(holder.get(Team, ids["B"]))
        holder.flush()
        renumber_seeds(teams_router.load_teams(holder, tournament_id))

    remove_c = Request(
        Session,
        teams_router.remove_team,
        tournament_id,
        ids["C"],
        x_admin_token=token,
    )
    start_while_locked(Session, tournament_id, remove_c, remove_b)

    assert remove_c.error is None
    assert seeds(Session, tournament_id) == [("A", 1), ("D", 2)]


@postgres
def test_reorder_naming_a_concurrently_removed_team_is_rejected(Session, setup):
    tournament_id, token, ids = setup

    def remove_b(holder):
        holder.delete(holder.get(Team, ids["B"]))
        holder.flush()
        renumber_seeds(teams_router.load_teams(holder, tournament_id))

    reorder = Request(
        Session,
        teams_router.set_seeding,
        tournament_id,
        TeamSeeding(team_ids=[ids["D"], ids["C"], ids["B"], ids["A"]]),
        x_admin_token=token,
    )
    start_while_locked(Session, tournament_id, reorder, remove_b)

    # A clean 422 from the fresh list, not a stale write or a 500.
    assert isinstance(reorder.error, HTTPException)
    assert reorder.error.status_code == 422
    assert seeds(Session, tournament_id) == [("A", 1), ("C", 2), ("D", 3)]


@postgres
def test_team_change_waits_for_bracket_generation(Session, setup):
    """Stand-in for TE-6: lock, set bracket_generated, commit."""
    tournament_id, token, _ = setup

    def generate_bracket(holder):
        lock_tournament(holder, tournament_id).bracket_generated = True

    add = Request(
        Session,
        teams_router.add_team,
        tournament_id,
        TeamName(name="Late Entry"),
        x_admin_token=token,
    )
    start_while_locked(Session, tournament_id, add, generate_bracket)

    assert isinstance(add.error, HTTPException)
    assert add.error.status_code == 409
    assert add.error.detail == teams_router.TEAMS_LOCKED
    assert [name for name, _ in seeds(Session, tournament_id)] == list("ABCD")


@postgres
def test_many_concurrent_changes_leave_seeds_1_to_n(Session, client):
    """No scripted order: 8 seeded teams, then 6 removes and 2 reorders at once."""
    created = client.post("/api/tournaments", json=TOURNAMENT).json()
    tournament_id, token = created["id"], created["admin_token"]
    url = f"/api/tournaments/{tournament_id}/teams"
    headers = {"X-Admin-Token": token}
    ids = [
        client.post(url, json={"name": f"T{i}"}, headers=headers).json()["id"]
        for i in range(12)
    ]
    client.put(f"{url}/seeding", json={"team_ids": ids[:8]}, headers=headers)

    barrier = threading.Barrier(8)

    def at_once(endpoint):
        def call(*args, **kwargs):
            barrier.wait()
            return endpoint(*args, **kwargs)

        return call

    requests = [
        Request(
            Session,
            at_once(teams_router.remove_team),
            tournament_id,
            team_id,
            x_admin_token=token,
        )
        for team_id in ids[1:7]
    ] + [
        Request(
            Session,
            at_once(teams_router.set_seeding),
            tournament_id,
            TeamSeeding(team_ids=[ids[0], ids[7], ids[8]]),
            x_admin_token=token,
        )
        for _ in range(2)
    ]
    for request in requests:
        request.start()
    for request in requests:
        request.join(20)

    # The reorders name only teams that nobody removes, so every request
    # should succeed whatever order the lock lets them through in.
    assert [r.error for r in requests] == [None] * len(requests)
    final = seeds(Session, tournament_id)
    seeded = [seed for _, seed in final if seed is not None]
    assert seeded == list(range(1, len(seeded) + 1))
    assert len(final) == 6


# --- Everywhere: every change takes the lock -----------------------------


def test_lock_query_is_select_for_update():
    sql = str(tournament_lock_query("abc").compile(dialect=postgresql.dialect()))

    assert sql.endswith("FOR UPDATE")


def test_every_team_change_takes_the_tournament_lock(client, setup, monkeypatch):
    tournament_id, token, ids = setup
    locked = []
    real_lock = tournaments_router.lock_tournament

    def spy(db, tid):
        locked.append(tid)
        return real_lock(db, tid)

    monkeypatch.setattr(tournaments_router, "lock_tournament", spy)
    url = f"/api/tournaments/{tournament_id}/teams"
    headers = {"X-Admin-Token": token}
    responses = [
        client.post(url, json={"name": "E"}, headers=headers),
        client.patch(f"{url}/{ids['A']}", json={"name": "A2"}, headers=headers),
        client.delete(f"{url}/{ids['B']}", headers=headers),
        client.put(f"{url}/seeding", json={"team_ids": [ids["C"]]}, headers=headers),
    ]

    assert [r.status_code for r in responses] == [201, 200, 204, 200]
    assert locked == [tournament_id] * 4


def test_public_reads_do_not_lock(client, setup, monkeypatch):
    tournament_id, _, _ = setup
    monkeypatch.setattr(
        tournaments_router,
        "lock_tournament",
        lambda *a: pytest.fail("GET must not lock the tournament"),
    )

    assert client.get(f"/api/tournaments/{tournament_id}/teams").status_code == 200
