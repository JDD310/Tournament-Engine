"""Bracket generation and the public bracket endpoint (TE-26)."""

import pytest
from sqlalchemy import func, select

from app.models import Match, Team, Tournament
from app.routers import tournaments as tournaments_router
from app.routers.bracket import ALREADY_GENERATED, NOT_SINGLE_ELIMINATION
from app.routers.teams import TEAMS_LOCKED
from app.security import hash_admin_token
from app.teams import MAX_TEAMS, bracket_readiness_error

TOURNAMENT = {
    "name": "Friday Night Smash",
    "game": "Super Smash Bros.",
    "format": "single_elimination",
}


@pytest.fixture
def tournament(client):
    return client.post("/api/tournaments", json=TOURNAMENT).json()


@pytest.fixture
def admin(tournament):
    return {"X-Admin-Token": tournament["admin_token"]}


def url(tournament, path="/bracket"):
    return f"/api/tournaments/{tournament['id']}{path}"


def add_teams(client, tournament, admin, names, seeded=None):
    """Add ``names`` in order; seed the first ``seeded`` (default: all)."""
    ids = [
        client.post(url(tournament, "/teams"), json={"name": n}, headers=admin).json()[
            "id"
        ]
        for n in names
    ]
    count = len(ids) if seeded is None else seeded
    response = client.put(
        url(tournament, "/teams/seeding"),
        json={"team_ids": ids[:count]},
        headers=admin,
    )
    assert response.status_code == 200
    return ids


def generate(client, tournament, admin):
    return client.post(url(tournament), headers=admin)


def name(team):
    return None if team is None else team["name"]


def pairings(bracket, round_number):
    return [
        (name(m["team1"]), name(m["team2"]))
        for m in bracket["rounds"][round_number - 1]["matches"]
    ]


def match_count(db_session, tournament):
    return db_session.scalar(
        select(func.count()).where(Match.tournament_id == tournament["id"])
    )


def check_links(bracket):
    """Every winner feeds exactly one slot of a later match; the final none."""
    matches = {m["id"]: m for r in bracket["rounds"] for m in r["matches"]}
    final = bracket["rounds"][-1]["matches"]
    assert len(final) == 1
    assert final[0]["next_match_id"] is None and final[0]["next_slot"] is None
    fed = set()
    for round_ in bracket["rounds"][:-1]:
        for m in round_["matches"]:
            target = matches[m["next_match_id"]]
            assert target["round"] == m["round"] + 1
            assert target["position"] == m["position"] // 2
            assert m["next_slot"] == m["position"] % 2 + 1
            fed.add((target["id"], m["next_slot"]))
    later = [m for r in bracket["rounds"][1:] for m in r["matches"]]
    assert fed == {(m["id"], slot) for m in later for slot in (1, 2)}
    assert len(fed) == sum(len(r["matches"]) for r in bracket["rounds"][:-1])


# --- Generating -----------------------------------------------------------


def test_generate_8_teams(client, tournament, admin):
    add_teams(client, tournament, admin, [f"Seed {i}" for i in range(1, 9)])

    response = generate(client, tournament, admin)

    assert response.status_code == 201
    bracket = response.json()
    assert bracket["generated"] is True
    assert [(r["round"], r["name"]) for r in bracket["rounds"]] == [
        (1, "Quarterfinals"),
        (2, "Semifinals"),
        (3, "Final"),
    ]
    assert pairings(bracket, 1) == [
        ("Seed 1", "Seed 8"),
        ("Seed 4", "Seed 5"),
        ("Seed 2", "Seed 7"),
        ("Seed 3", "Seed 6"),
    ]
    assert pairings(bracket, 2) == [(None, None)] * 2
    check_links(bracket)
    first = bracket["rounds"][0]["matches"][0]
    assert first["team1"] == {"id": first["team1"]["id"], "name": "Seed 1", "seed": 1}


def test_generate_6_teams_advances_the_bye_winners(client, tournament, admin):
    add_teams(client, tournament, admin, [f"Seed {i}" for i in range(1, 7)])

    bracket = generate(client, tournament, admin).json()

    first = bracket["rounds"][0]["matches"]
    assert pairings(bracket, 1) == [
        ("Seed 1", None),
        ("Seed 4", "Seed 5"),
        ("Seed 2", None),
        ("Seed 3", "Seed 6"),
    ]
    assert [m["is_bye"] for m in first] == [True, False, True, False]
    assert first[0]["winner_id"] == first[0]["team1"]["id"]
    assert first[1]["winner_id"] is None
    assert pairings(bracket, 2) == [("Seed 1", None), ("Seed 2", None)]
    check_links(bracket)


def test_unseeded_teams_follow_the_seeded_ones_in_the_order_added(
    client, tournament, admin
):
    # Alpha and Bravo seeded 1 and 2; Charlie, Delta, Echo unseeded, so they
    # are placed as seeds 3, 4 and 5 in the order they were added.
    add_teams(
        client,
        tournament,
        admin,
        ["Alpha", "Bravo", "Charlie", "Delta", "Echo"],
        seeded=2,
    )

    bracket = generate(client, tournament, admin).json()

    assert pairings(bracket, 1) == [
        ("Alpha", None),
        ("Delta", "Echo"),
        ("Bravo", None),
        ("Charlie", None),
    ]
    assert pairings(bracket, 2) == [("Alpha", None), ("Bravo", "Charlie")]
    seeds = {
        t["name"]: t["seed"]
        for m in bracket["rounds"][0]["matches"]
        for t in (m["team1"], m["team2"])
        if t
    }
    # The API reports each team's own seed; unseeded teams stay None.
    assert seeds == {
        "Alpha": 1,
        "Bravo": 2,
        "Charlie": None,
        "Delta": None,
        "Echo": None,
    }


def test_all_unseeded_teams_are_placed_in_the_order_added(client, tournament, admin):
    add_teams(client, tournament, admin, ["W", "X", "Y", "Z"], seeded=0)

    bracket = generate(client, tournament, admin).json()

    assert pairings(bracket, 1) == [("W", "Z"), ("X", "Y")]


def test_generate_2_teams_is_a_single_final(client, tournament, admin):
    add_teams(client, tournament, admin, ["Alpha", "Bravo"])

    bracket = generate(client, tournament, admin).json()

    assert [r["name"] for r in bracket["rounds"]] == ["Final"]
    assert pairings(bracket, 1) == [("Alpha", "Bravo")]
    check_links(bracket)


def test_generate_the_maximum_of_256_teams(client, tournament, admin, db_session):
    add_teams(client, tournament, admin, [f"T{i:03}" for i in range(1, MAX_TEAMS + 1)])

    response = generate(client, tournament, admin)

    assert response.status_code == 201
    bracket = response.json()
    assert len(bracket["rounds"]) == 8
    assert [len(r["matches"]) for r in bracket["rounds"]] == [
        128,
        64,
        32,
        16,
        8,
        4,
        2,
        1,
    ]
    assert pairings(bracket, 1)[0] == ("T001", "T256")
    check_links(bracket)
    assert match_count(db_session, tournament) == 255


def test_generation_saves_the_matches_and_sets_the_flag(
    client, tournament, admin, db_session
):
    ids = add_teams(client, tournament, admin, ["A", "B", "C"])

    generate(client, tournament, admin)

    assert db_session.get(Tournament, tournament["id"]).bracket_generated is True
    rows = db_session.scalars(
        select(Match)
        .where(Match.tournament_id == tournament["id"])
        .order_by(Match.round, Match.position)
    ).all()
    assert [
        (m.round, m.position, m.team1_id, m.team2_id, m.winner_id, m.is_bye)
        for m in rows
    ] == [
        (1, 0, ids[0], None, ids[0], True),
        (1, 1, ids[1], ids[2], None, False),
        (2, 0, ids[0], None, None, False),
    ]
    final = rows[2]
    assert [(m.next_match_id, m.next_slot) for m in rows] == [
        (final.id, 1),
        (final.id, 2),
        (None, None),
    ]


# --- Refusals -------------------------------------------------------------


@pytest.mark.parametrize("count", [0, 1])
def test_fewer_than_two_teams_is_rejected(client, tournament, admin, db_session, count):
    add_teams(client, tournament, admin, ["Solo"][:count])

    response = generate(client, tournament, admin)

    assert response.status_code == 409
    assert response.json()["detail"] == bracket_readiness_error(count)
    assert "at least 2 teams" in response.json()["detail"]
    assert db_session.get(Tournament, tournament["id"]).bracket_generated is False
    assert match_count(db_session, tournament) == 0


def test_generating_a_second_time_is_rejected(client, tournament, admin, db_session):
    add_teams(client, tournament, admin, ["A", "B", "C", "D"])
    first = generate(client, tournament, admin).json()

    again = generate(client, tournament, admin)

    assert again.status_code == 409
    assert again.json()["detail"] == ALREADY_GENERATED
    assert match_count(db_session, tournament) == 3
    assert client.get(url(tournament)).json() == first


def test_generation_is_rejected_for_other_formats(
    client, tournament, admin, db_session
):
    # The API only accepts single_elimination today, so there is no way to
    # create another format through it. Write a stand-in format onto the row
    # directly to exercise the guard that a Swiss tournament (TE-7) will hit.
    add_teams(client, tournament, admin, ["A", "B", "C", "D"])
    row = db_session.get(Tournament, tournament["id"])
    row.format = "swiss"
    db_session.commit()

    response = generate(client, tournament, admin)

    assert response.status_code == 409
    assert response.json()["detail"] == NOT_SINGLE_ELIMINATION
    db_session.expire_all()
    assert db_session.get(Tournament, tournament["id"]).bracket_generated is False
    assert match_count(db_session, tournament) == 0
    # The teams stay editable, since nothing was locked.
    added = client.post(url(tournament, "/teams"), json={"name": "E"}, headers=admin)
    assert added.status_code == 201


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}])
def test_generation_requires_the_organizer_token(
    client, tournament, admin, db_session, headers
):
    add_teams(client, tournament, admin, ["A", "B"])

    response = client.post(url(tournament), headers=headers)

    assert response.status_code == 403
    assert db_session.get(Tournament, tournament["id"]).bracket_generated is False
    assert match_count(db_session, tournament) == 0


def test_generation_for_an_unknown_tournament_is_404(client, admin):
    response = client.post("/api/tournaments/nope/bracket", headers=admin)

    assert response.status_code == 404


def test_generation_locks_the_team_list(client, tournament, admin):
    ids = add_teams(client, tournament, admin, ["A", "B"])
    generate(client, tournament, admin)

    add = client.post(url(tournament, "/teams"), json={"name": "C"}, headers=admin)
    remove = client.delete(url(tournament, f"/teams/{ids[0]}"), headers=admin)

    assert add.status_code == remove.status_code == 409
    assert add.json()["detail"] == TEAMS_LOCKED
    assert client.get(url(tournament, "/teams")).json()["locked"] is True


def test_generation_takes_the_tournament_lock(client, tournament, admin, monkeypatch):
    add_teams(client, tournament, admin, ["A", "B"])
    locked = []
    real_lock = tournaments_router.lock_tournament

    def spy(db, tid):
        locked.append(tid)
        return real_lock(db, tid)

    monkeypatch.setattr(tournaments_router, "lock_tournament", spy)

    assert generate(client, tournament, admin).status_code == 201
    assert locked == [tournament["id"]]


# --- Reading --------------------------------------------------------------


def test_bracket_before_generation_is_empty(client, tournament):
    response = client.get(url(tournament))

    assert response.status_code == 200
    assert response.json() == {"generated": False, "rounds": []}


def test_bracket_is_public_and_matches_the_generation_response(
    client, tournament, admin, monkeypatch
):
    add_teams(client, tournament, admin, ["A", "B", "C", "D", "E"])
    generated = generate(client, tournament, admin).json()
    monkeypatch.setattr(
        tournaments_router,
        "lock_tournament",
        lambda *a: pytest.fail("GET must not lock the tournament"),
    )

    response = client.get(url(tournament))

    assert response.status_code == 200
    assert response.json() == generated


def test_bracket_never_exposes_the_token(client, tournament, admin):
    add_teams(client, tournament, admin, ["A", "B"])
    token = tournament["admin_token"]
    bodies = [
        generate(client, tournament, admin).text,
        client.get(url(tournament)).text,
    ]

    for body in bodies:
        assert token not in body
        assert hash_admin_token(token) not in body
        assert "admin" not in body


def test_bracket_for_an_unknown_tournament_is_404(client):
    assert client.get("/api/tournaments/nope/bracket").status_code == 404


def test_brackets_are_per_tournament(client, tournament, admin, db_session):
    add_teams(client, tournament, admin, ["A", "B"])
    other = client.post("/api/tournaments", json=TOURNAMENT).json()
    other_admin = {"X-Admin-Token": other["admin_token"]}
    add_teams(client, other, other_admin, ["X", "Y", "Z"])

    generate(client, tournament, admin)

    assert client.get(url(other)).json() == {"generated": False, "rounds": []}
    assert generate(client, other, other_admin).status_code == 201
    assert pairings(client.get(url(tournament)).json(), 1) == [("A", "B")]
    teams_in_other = set(
        db_session.scalars(select(Team.id).where(Team.tournament_id == other["id"]))
    )
    other_matches = db_session.scalars(
        select(Match).where(Match.tournament_id == other["id"])
    ).all()
    for m in other_matches:
        assert {m.team1_id, m.team2_id} - {None} <= teams_in_other
