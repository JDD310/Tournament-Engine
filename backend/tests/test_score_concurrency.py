"""Score reports and corrections are serialized by the tournament lock (TE-9).

``report_score`` takes ``lock_tournament`` before it reads any match and holds
it until it commits. Without it, a correction that swaps the team in the next
match and a report of that next match can each act on what the other is about
to change, leaving a winner who never played the match. The ``postgres`` tests
check this with real concurrent transactions and are skipped on SQLite (which
ignores ``FOR UPDATE``). Run them with::

    TEST_DATABASE_URL=postgresql://USER:PASS@HOST:5432/DB pytest tests/test_score_concurrency.py

``test_scores.py`` checks on every database that reporting asks for the lock
before it reads a match.
"""

import threading

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.models import Match
from app.routers import matches as matches_router
from app.routers.matches import NEXT_MATCH_PLAYED
from app.routers.tournaments import lock_tournament
from app.schemas import ScoreReport

from .test_team_concurrency import Request, postgres, start_while_locked

TOURNAMENT = {
    "name": "Friday Night Smash",
    "game": "Super Smash Bros.",
    "format": "single_elimination",
}


@pytest.fixture
def Session(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def four_team_bracket(client):
    """A-D seeded 1-4 and generated. Returns (id, token, top semi, bottom
    semi, final) as match IDs; the top semi (A v D) feeds final slot 1."""
    created = client.post("/api/tournaments", json=TOURNAMENT).json()
    headers = {"X-Admin-Token": created["admin_token"]}
    base = f"/api/tournaments/{created['id']}"
    ids = [
        client.post(f"{base}/teams", json={"name": n}, headers=headers).json()["id"]
        for n in "ABCD"
    ]
    client.put(f"{base}/teams/seeding", json={"team_ids": ids}, headers=headers)
    bracket = client.post(f"{base}/bracket", headers=headers).json()
    top, bottom = (m["id"] for m in bracket["rounds"][0]["matches"])
    final = bracket["rounds"][1]["matches"][0]["id"]
    return created["id"], created["admin_token"], top, bottom, final


def put_score(client, tournament_id, token, match_id, team1_score, team2_score):
    response = client.put(
        f"/api/tournaments/{tournament_id}/matches/{match_id}/score",
        json={"team1_score": team1_score, "team2_score": team2_score},
        headers={"X-Admin-Token": token},
    )
    assert response.status_code == 200, response.text


@pytest.fixture
def setup(client):
    return four_team_bracket(client)


@pytest.fixture
def semis_played(client, setup):
    """A beat D and B beat C: the final is A v B, unplayed."""
    tournament_id, token, top, bottom, _ = setup
    put_score(client, tournament_id, token, top, 2, 0)
    put_score(client, tournament_id, token, bottom, 2, 0)
    return setup


def load(Session, tournament_id):
    with Session() as db:
        return {
            (m.round, m.position): m
            for m in db.scalars(
                select(Match).where(Match.tournament_id == tournament_id)
            )
        }


def check_consistent(matches):
    """Each winner played the match it won and holds the slot it feeds."""
    by_id = {m.id: m for m in matches.values()}
    for m in by_id.values():
        if m.winner_id is None:
            continue
        assert m.winner_id in {m.team1_id, m.team2_id}
        if m.next_match_id is not None:
            nxt = by_id[m.next_match_id]
            assert getattr(nxt, f"team{m.next_slot}_id") == m.winner_id


def flip_top_semi(holder, top_id):
    """What a correction of the top semi to D winning does, held open."""
    semi = holder.get(Match, top_id)
    final = holder.get(Match, semi.next_match_id)
    semi.team1_score, semi.team2_score, semi.winner_id = 0, 2, semi.team2_id
    final.team1_id = semi.team2_id


@postgres
def test_report_of_the_next_match_waits_for_a_correction_and_sees_it(
    Session, semis_played
):
    tournament_id, token, top, _, final = semis_played

    report_final = Request(
        Session,
        matches_router.report_score,
        tournament_id,
        final,
        ScoreReport(team1_score=3, team2_score=1),
        x_admin_token=token,
    )
    start_while_locked(
        Session, tournament_id, report_final, lambda h: flip_top_semi(h, top)
    )

    assert report_final.error is None
    # The report waited, so it saw D (not A) in slot 1 and D won the final.
    assert report_final.result.champion.name == "D"
    matches = load(Session, tournament_id)
    check_consistent(matches)
    assert matches[(2, 0)].winner_id == matches[(1, 0)].team2_id


@postgres
def test_correction_waiting_on_a_report_of_the_next_match_is_refused(
    Session, semis_played
):
    tournament_id, token, top, _, final = semis_played

    def report_the_final(holder):
        match = holder.get(Match, final)
        match.team1_score, match.team2_score = 3, 1
        match.winner_id = match.team1_id

    correction = Request(
        Session,
        matches_router.report_score,
        tournament_id,
        top,
        ScoreReport(team1_score=0, team2_score=2),
        x_admin_token=token,
    )
    start_while_locked(Session, tournament_id, correction, report_the_final)

    assert isinstance(correction.error, HTTPException)
    assert correction.error.status_code == 409
    assert correction.error.detail == NEXT_MATCH_PLAYED
    matches = load(Session, tournament_id)
    check_consistent(matches)
    assert matches[(1, 0)].winner_id == matches[(1, 0)].team1_id  # still A


@postgres
def test_reports_feeding_one_match_wait_for_each_other(Session, setup):
    tournament_id, token, top, bottom, _ = setup

    def report_top(holder):
        semi = holder.get(Match, top)
        semi.team1_score, semi.team2_score, semi.winner_id = 2, 0, semi.team1_id
        holder.get(Match, semi.next_match_id).team1_id = semi.team1_id

    report_bottom = Request(
        Session,
        matches_router.report_score,
        tournament_id,
        bottom,
        ScoreReport(team1_score=2, team2_score=0),
        x_admin_token=token,
    )
    start_while_locked(Session, tournament_id, report_bottom, report_top)

    assert report_bottom.error is None
    final = report_bottom.result.rounds[1].matches[0]
    assert (final.team1.name, final.team2.name) == ("A", "B")
    check_consistent(load(Session, tournament_id))


@postgres
def test_correction_racing_a_report_of_the_next_match_stays_consistent(client, Session):
    """The correction and the final's report start at the same moment, many
    times over. Either order is fine; a final won by a team that isn't in it
    is not."""
    for _ in range(15):
        tournament_id, token, top, bottom, final = four_team_bracket(client)
        put_score(client, tournament_id, token, top, 2, 0)
        put_score(client, tournament_id, token, bottom, 2, 0)
        barrier = threading.Barrier(2)

        def at_once(*args, **kwargs):
            barrier.wait()
            return matches_router.report_score(*args, **kwargs)

        correction = Request(
            Session,
            at_once,
            tournament_id,
            top,
            ScoreReport(team1_score=0, team2_score=2),
            x_admin_token=token,
        )
        report_final = Request(
            Session,
            at_once,
            tournament_id,
            final,
            ScoreReport(team1_score=3, team2_score=1),
            x_admin_token=token,
        )
        for request in (correction, report_final):
            request.start()
        for request in (correction, report_final):
            request.join(20)

        assert report_final.error is None
        if correction.error is not None:
            assert correction.error.detail == NEXT_MATCH_PLAYED
        check_consistent(load(Session, tournament_id))


@postgres
def test_lock_is_held_until_the_report_commits(Session, setup):
    """A transaction that wants the lock waits for an in-flight report."""
    tournament_id, token, top, _, _ = setup
    entered, release = threading.Event(), threading.Event()
    real_commit = None

    def slow_report(*args, db, **kwargs):
        nonlocal real_commit
        real_commit = db.commit

        def commit():
            entered.set()
            release.wait(5)
            real_commit()

        db.commit = commit
        return matches_router.report_score(*args, db=db, **kwargs)

    reporting = Request(
        Session,
        slow_report,
        tournament_id,
        top,
        ScoreReport(team1_score=2, team2_score=0),
        x_admin_token=token,
    )
    reporting.start()
    assert entered.wait(5)

    waiter_done = threading.Event()

    def take_lock():
        with Session() as other:
            lock_tournament(other, tournament_id)
            waiter_done.set()

    waiter = threading.Thread(target=take_lock, daemon=True)
    waiter.start()
    assert not waiter_done.wait(0.5), "the lock was released before commit"
    release.set()
    reporting.join(10)
    waiter.join(10)
    assert waiter_done.is_set()
    assert reporting.error is None
