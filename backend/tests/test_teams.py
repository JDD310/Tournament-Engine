import pytest

from app.models import Team, Tournament
from app.teams import MIN_BRACKET_TEAMS, bracket_readiness_error, team_name_key

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


def teams_url(tournament, suffix=""):
    return f"/api/tournaments/{tournament['id']}/teams{suffix}"


def add(client, tournament, admin, name):
    return client.post(teams_url(tournament), json={"name": name}, headers=admin)


def add_all(client, tournament, admin, *names):
    return [add(client, tournament, admin, name).json()["id"] for name in names]


def listing(client, tournament):
    return client.get(teams_url(tournament)).json()


def names(client, tournament):
    return [t["name"] for t in listing(client, tournament)["teams"]]


def seeds(client, tournament):
    return [(t["name"], t["seed"]) for t in listing(client, tournament)["teams"]]


def seed(client, tournament, admin, team_ids):
    return client.put(
        teams_url(tournament, "/seeding"), json={"team_ids": team_ids}, headers=admin
    )


def lock(db_session, tournament):
    """Stand-in for bracket generation (TE-6), which will set this flag."""
    db_session.get(Tournament, tournament["id"]).bracket_generated = True
    db_session.commit()


# --- Add, rename, remove -------------------------------------------------


def test_add_team(client, tournament, admin):
    response = add(client, tournament, admin, "  Team Liquid  ")

    assert response.status_code == 201
    body = response.json()
    assert body == {"id": body["id"], "name": "Team Liquid", "seed": None}
    assert listing(client, tournament) == {"locked": False, "teams": [body]}


def test_new_teams_are_unseeded_in_the_order_added(client, tournament, admin):
    add_all(client, tournament, admin, "Charlie", "Alpha", "Bravo")

    assert seeds(client, tournament) == [
        ("Charlie", None),
        ("Alpha", None),
        ("Bravo", None),
    ]


def test_rename_team(client, tournament, admin):
    (team_id,) = add_all(client, tournament, admin, "Liquid")

    response = client.patch(
        teams_url(tournament, f"/{team_id}"),
        json={"name": "Team Liquid"},
        headers=admin,
    )

    assert response.status_code == 200
    assert response.json() == {"id": team_id, "name": "Team Liquid", "seed": None}
    assert names(client, tournament) == ["Team Liquid"]


def test_rename_keeps_seed(client, tournament, admin):
    a, b = add_all(client, tournament, admin, "A", "B")
    seed(client, tournament, admin, [b, a])

    client.patch(teams_url(tournament, f"/{b}"), json={"name": "Bee"}, headers=admin)

    assert seeds(client, tournament) == [("Bee", 1), ("A", 2)]


def test_remove_team(client, tournament, admin):
    a, _ = add_all(client, tournament, admin, "A", "B")

    response = client.delete(teams_url(tournament, f"/{a}"), headers=admin)

    assert response.status_code == 204
    assert names(client, tournament) == ["B"]


def test_removed_name_can_be_reused(client, tournament, admin):
    (a,) = add_all(client, tournament, admin, "A")
    client.delete(teams_url(tournament, f"/{a}"), headers=admin)

    assert add(client, tournament, admin, "A").status_code == 201


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_unknown_team_is_404(client, tournament, admin, method):
    kwargs = {"json": {"name": "X"}} if method == "patch" else {}

    response = getattr(client, method)(
        teams_url(tournament, "/9999"), headers=admin, **kwargs
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Team not found."


@pytest.mark.parametrize("method", ["patch", "delete"])
def test_team_from_another_tournament_is_404(client, tournament, admin, method):
    other = client.post("/api/tournaments", json=TOURNAMENT).json()
    other_admin = {"X-Admin-Token": other["admin_token"]}
    (other_team,) = add_all(client, other, other_admin, "Theirs")
    kwargs = {"json": {"name": "Mine"}} if method == "patch" else {}

    # Our own token, our tournament's URL, their team's ID.
    response = getattr(client, method)(
        teams_url(tournament, f"/{other_team}"), headers=admin, **kwargs
    )

    assert response.status_code == 404
    assert names(client, other) == ["Theirs"]


def test_list_teams_of_unknown_tournament_is_404(client):
    assert client.get("/api/tournaments/nope/teams").status_code == 404


# --- Names ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({}, "Team name is required."),
        ({"name": None}, "Team name is required."),
        ({"name": "   "}, "Team name is required."),
        ({"name": 7}, "Team name must be text."),
        ({"name": "x" * 101}, "Team name must be 100 characters or fewer."),
    ],
)
def test_invalid_team_names(client, tournament, admin, body, message):
    response = client.post(teams_url(tournament), json=body, headers=admin)

    assert response.status_code == 422
    assert response.json()["errors"] == [{"field": "name", "message": message}]


def test_team_name_at_max_length_is_allowed(client, tournament, admin):
    assert add(client, tournament, admin, "x" * 100).status_code == 201


@pytest.mark.parametrize(
    "duplicate", ["Team Liquid", "team liquid", "TEAM LIQUID", "  Team   Liquid "]
)
def test_duplicate_names_ignore_case_and_whitespace(
    client, tournament, admin, duplicate
):
    add(client, tournament, admin, "Team Liquid")

    response = add(client, tournament, admin, duplicate)

    assert response.status_code == 409
    assert response.json()["detail"] == (
        f'A team named "{duplicate.strip()}" is already in this tournament.'
    )
    assert names(client, tournament) == ["Team Liquid"]


def test_similar_but_different_names_are_allowed(client, tournament, admin):
    for name in ["Team Liquid", "TeamLiquid", "Team Liquid 2"]:
        assert add(client, tournament, admin, name).status_code == 201


def test_same_name_is_allowed_in_another_tournament(client, tournament, admin):
    other = client.post("/api/tournaments", json=TOURNAMENT).json()
    add(client, tournament, admin, "Team Liquid")

    response = add(
        client, other, {"X-Admin-Token": other["admin_token"]}, "Team Liquid"
    )

    assert response.status_code == 201


def test_rename_to_another_teams_name_is_rejected(client, tournament, admin):
    _, b = add_all(client, tournament, admin, "Alpha", "Bravo")

    response = client.patch(
        teams_url(tournament, f"/{b}"), json={"name": "ALPHA"}, headers=admin
    )

    assert response.status_code == 409
    assert names(client, tournament) == ["Alpha", "Bravo"]


def test_rename_can_change_only_the_case_of_its_own_name(client, tournament, admin):
    (a,) = add_all(client, tournament, admin, "team liquid")

    response = client.patch(
        teams_url(tournament, f"/{a}"), json={"name": "Team Liquid"}, headers=admin
    )

    assert response.status_code == 200
    assert names(client, tournament) == ["Team Liquid"]


def test_rename_validates_name(client, tournament, admin):
    (a,) = add_all(client, tournament, admin, "Alpha")

    response = client.patch(teams_url(tournament, f"/{a}"), json={}, headers=admin)

    assert response.status_code == 422
    assert names(client, tournament) == ["Alpha"]


def test_database_enforces_unique_names(client, tournament, admin, db_session):
    """The unique constraint backs up the check if two requests race."""
    add(client, tournament, admin, "Alpha")
    db_session.add(
        Team(
            tournament_id=tournament["id"],
            name="ALPHA",
            name_key=team_name_key("ALPHA"),
        )
    )

    with pytest.raises(Exception, match="(?i)unique"):
        db_session.commit()


def test_duplicate_caught_by_constraint_returns_409(
    client, tournament, admin, monkeypatch
):
    """If the pre-check misses a race, the IntegrityError becomes a 409."""
    from app.routers import teams

    add(client, tournament, admin, "Alpha")
    monkeypatch.setattr(
        teams,
        "ensure_name_available",
        lambda db, tid, name, **kw: (team_name_key(name)),
    )

    response = add(client, tournament, admin, "alpha")

    assert response.status_code == 409
    assert names(client, tournament) == ["Alpha"]


@pytest.mark.parametrize(
    ("name", "key"),
    [
        ("Team Liquid", "team liquid"),
        ("  Team \t Liquid  ", "team liquid"),
        ("STRASSE", "strasse"),
        ("Straße", "strasse"),
    ],
)
def test_team_name_key(name, key):
    assert team_name_key(name) == key


# --- Seeding -------------------------------------------------------------


def test_seed_teams(client, tournament, admin):
    a, b, c = add_all(client, tournament, admin, "A", "B", "C")

    response = seed(client, tournament, admin, [c, a, b])

    assert response.status_code == 200
    assert [(t["name"], t["seed"]) for t in response.json()["teams"]] == [
        ("C", 1),
        ("A", 2),
        ("B", 3),
    ]
    assert seeds(client, tournament) == [("C", 1), ("A", 2), ("B", 3)]


def test_unseeded_teams_come_after_seeded_ones(client, tournament, admin):
    a, b, c, d = add_all(client, tournament, admin, "A", "B", "C", "D")

    seed(client, tournament, admin, [d, b])

    assert seeds(client, tournament) == [
        ("D", 1),
        ("B", 2),
        ("A", None),
        ("C", None),
    ]


def test_reorder_replaces_previous_seeding(client, tournament, admin):
    a, b, c = add_all(client, tournament, admin, "A", "B", "C")
    seed(client, tournament, admin, [a, b, c])

    seed(client, tournament, admin, [c, a])

    assert seeds(client, tournament) == [("C", 1), ("A", 2), ("B", None)]


def test_empty_seeding_unseeds_everyone(client, tournament, admin):
    a, b = add_all(client, tournament, admin, "A", "B")
    seed(client, tournament, admin, [b, a])

    seed(client, tournament, admin, [])

    assert seeds(client, tournament) == [("A", None), ("B", None)]


def test_new_team_after_seeding_is_unseeded(client, tournament, admin):
    a, b = add_all(client, tournament, admin, "A", "B")
    seed(client, tournament, admin, [b, a])

    add(client, tournament, admin, "C")

    assert seeds(client, tournament) == [("B", 1), ("A", 2), ("C", None)]


def test_removing_a_middle_seed_moves_lower_seeds_up(client, tournament, admin):
    a, b, c, d = add_all(client, tournament, admin, "A", "B", "C", "D")
    seed(client, tournament, admin, [a, b, c])

    client.delete(teams_url(tournament, f"/{b}"), headers=admin)

    assert seeds(client, tournament) == [("A", 1), ("C", 2), ("D", None)]


def test_removing_an_unseeded_team_keeps_seeds(client, tournament, admin):
    a, b, c = add_all(client, tournament, admin, "A", "B", "C")
    seed(client, tournament, admin, [b, a])

    client.delete(teams_url(tournament, f"/{c}"), headers=admin)

    assert seeds(client, tournament) == [("B", 1), ("A", 2)]


def test_seeding_rejects_duplicate_ids(client, tournament, admin):
    a, b = add_all(client, tournament, admin, "A", "B")

    response = seed(client, tournament, admin, [a, b, a])

    assert response.status_code == 422
    assert response.json()["errors"] == [
        {"field": "team_ids", "message": "Each team can only be seeded once."}
    ]
    assert seeds(client, tournament) == [("A", None), ("B", None)]


def test_seeding_rejects_teams_from_elsewhere(client, tournament, admin):
    (a,) = add_all(client, tournament, admin, "A")
    other = client.post("/api/tournaments", json=TOURNAMENT).json()
    (theirs,) = add_all(
        client, other, {"X-Admin-Token": other["admin_token"]}, "Theirs"
    )

    response = seed(client, tournament, admin, [a, theirs, 9999])

    assert response.status_code == 422
    assert response.json()["detail"] == (
        f"These teams are not in this tournament: {theirs}, 9999."
    )
    assert seeds(client, tournament) == [("A", None)]
    assert seeds(client, other) == [("Theirs", None)]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({}, "Team order is required."),
        ({"team_ids": "1,2"}, "Input should be a valid list"),
        ({"team_ids": ["1"]}, "Input should be a valid integer"),
    ],
)
def test_seeding_validates_body(client, tournament, admin, body, message):
    response = client.put(teams_url(tournament, "/seeding"), json=body, headers=admin)

    assert response.status_code == 422
    assert response.json()["errors"][0]["field"] == "team_ids"
    assert response.json()["errors"][0]["message"] == message


# --- Organizer-only access -----------------------------------------------


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}])
def test_changes_need_the_organizer_token(client, tournament, admin, headers):
    (a,) = add_all(client, tournament, admin, "A")
    requests = [
        ("post", teams_url(tournament), {"json": {"name": "B"}}),
        ("patch", teams_url(tournament, f"/{a}"), {"json": {"name": "B"}}),
        ("delete", teams_url(tournament, f"/{a}"), {}),
        ("put", teams_url(tournament, "/seeding"), {"json": {"team_ids": [a]}}),
    ]

    for method, url, kwargs in requests:
        response = getattr(client, method)(url, headers=headers, **kwargs)
        assert response.status_code == 403, (method, url)

    assert seeds(client, tournament) == [("A", None)]


def test_another_tournaments_token_cannot_change_teams(client, tournament, admin):
    other = client.post("/api/tournaments", json=TOURNAMENT).json()

    response = add(client, tournament, {"X-Admin-Token": other["admin_token"]}, "A")

    assert response.status_code == 403


def test_public_team_list_never_exposes_the_token(client, tournament, admin):
    add(client, tournament, admin, "A")

    response = client.get(teams_url(tournament))

    assert response.status_code == 200
    text = response.text
    assert tournament["admin_token"] not in text
    assert "admin_token" not in text
    assert "token" not in text
    assert set(response.json()["teams"][0]) == {"id", "name", "seed"}


# --- Lock after bracket generation ---------------------------------------


def test_list_reports_lock(client, tournament, db_session):
    assert listing(client, tournament)["locked"] is False

    lock(db_session, tournament)

    assert listing(client, tournament)["locked"] is True


def test_teams_are_locked_once_bracket_is_generated(
    client, tournament, admin, db_session
):
    a, b = add_all(client, tournament, admin, "A", "B")
    seed(client, tournament, admin, [b, a])
    lock(db_session, tournament)
    requests = [
        ("post", teams_url(tournament), {"json": {"name": "C"}}),
        ("patch", teams_url(tournament, f"/{a}"), {"json": {"name": "Z"}}),
        ("delete", teams_url(tournament, f"/{a}"), {}),
        ("put", teams_url(tournament, "/seeding"), {"json": {"team_ids": [a, b]}}),
    ]

    for method, url, kwargs in requests:
        response = getattr(client, method)(url, headers=admin, **kwargs)
        assert response.status_code == 409, (method, url)
        assert "can no longer be changed" in response.json()["detail"]

    assert seeds(client, tournament) == [("B", 1), ("A", 2)]


def test_locked_check_still_requires_the_token(client, tournament, db_session):
    """Without a valid token the answer is 403, not a hint about the lock."""
    lock(db_session, tournament)

    response = client.post(teams_url(tournament), json={"name": "A"})

    assert response.status_code == 403


def test_new_tournaments_are_not_locked(client, tournament, db_session):
    assert db_session.get(Tournament, tournament["id"]).bracket_generated is False


# --- Minimum teams for a bracket -----------------------------------------


@pytest.mark.parametrize(
    ("count", "ready"), [(0, False), (1, False), (2, True), (8, True)]
)
def test_bracket_needs_at_least_two_teams(count, ready):
    assert MIN_BRACKET_TEAMS == 2
    error = bracket_readiness_error(count)
    if ready:
        assert error is None
    else:
        assert error == (
            "A tournament needs at least 2 teams before a bracket can be generated."
        )


def test_can_remove_teams_below_the_minimum(client, tournament, admin):
    """The minimum only applies when generating; the list itself can shrink."""
    a, b = add_all(client, tournament, admin, "A", "B")

    assert (
        client.delete(teams_url(tournament, f"/{a}"), headers=admin).status_code == 204
    )
    assert (
        client.delete(teams_url(tournament, f"/{b}"), headers=admin).status_code == 204
    )
    assert listing(client, tournament)["teams"] == []
