"""The public, read-only tournament view (TE-10: TE-41)."""

import json

import pytest

from app.models import Tournament
from app.security import hash_admin_token

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


def url(tournament, path=""):
    return f"/api/tournaments/{tournament['id']}{path}"


def view(client, tournament):
    response = client.get(url(tournament, "/public"))
    assert response.status_code == 200
    return response.json()


def add_teams(client, tournament, admin, names):
    ids = [
        client.post(url(tournament, "/teams"), json={"name": n}, headers=admin).json()[
            "id"
        ]
        for n in names
    ]
    client.put(url(tournament, "/teams/seeding"), json={"team_ids": ids}, headers=admin)


def generate(client, tournament, admin):
    response = client.post(url(tournament, "/bracket"), headers=admin)
    assert response.status_code == 201
    return response.json()


def report(client, tournament, admin, match, team1_score, team2_score):
    response = client.put(
        url(tournament, f"/matches/{match['id']}/score"),
        json={"team1_score": team1_score, "team2_score": team2_score},
        headers=admin,
    )
    assert response.status_code == 200
    return response.json()


def play_out(client, tournament, admin):
    """A-D seeded 1-4; report both semifinals and the final (A wins)."""
    add_teams(client, tournament, admin, ["A", "B", "C", "D"])
    bracket = generate(client, tournament, admin)
    semis = bracket["rounds"][0]["matches"]
    report(client, tournament, admin, semis[0], 3, 1)
    bracket = report(client, tournament, admin, semis[1], 2, 0)
    report(client, tournament, admin, bracket["rounds"][1]["matches"][0], 5, 4)


def test_view_has_the_tournament_teams_and_bracket(client, tournament, admin):
    add_teams(client, tournament, admin, ["A", "B", "C"])

    body = view(client, tournament)

    assert set(body) == {"tournament", "teams", "bracket"}
    assert body["tournament"] == client.get(url(tournament)).json()
    assert body["teams"] == client.get(url(tournament, "/teams")).json()
    assert body["bracket"] == client.get(url(tournament, "/bracket")).json()
    assert body["tournament"]["name"] == TOURNAMENT["name"]
    assert body["tournament"]["game"] == TOURNAMENT["game"]
    assert body["tournament"]["format"] == "single_elimination"
    assert [t["name"] for t in body["teams"]["teams"]] == ["A", "B", "C"]


def test_view_matches_the_separate_reads_once_played(client, tournament, admin):
    play_out(client, tournament, admin)

    body = view(client, tournament)

    assert body["bracket"] == client.get(url(tournament, "/bracket")).json()
    final = body["bracket"]["rounds"][-1]["matches"][0]
    assert (final["team1_score"], final["team2_score"]) == (5, 4)
    assert body["bracket"]["champion"]["name"] == "A"


def test_status_is_setting_up_before_the_bracket(client, tournament, admin):
    assert tournament["status"] == "setting_up"
    add_teams(client, tournament, admin, ["A", "B"])

    assert view(client, tournament)["tournament"]["status"] == "setting_up"
    assert client.get(url(tournament)).json()["status"] == "setting_up"


def test_status_is_in_progress_once_the_bracket_is_generated(client, tournament, admin):
    add_teams(client, tournament, admin, ["A", "B", "C", "D"])
    bracket = generate(client, tournament, admin)
    assert view(client, tournament)["tournament"]["status"] == "in_progress"

    # Still in progress with some, but not all, matches reported.
    report(client, tournament, admin, bracket["rounds"][0]["matches"][0], 2, 1)
    body = view(client, tournament)
    assert body["tournament"]["status"] == "in_progress"
    assert body["tournament"]["completed_at"] is None
    assert body["bracket"]["champion"] is None


def test_status_is_complete_once_the_final_is_reported(client, tournament, admin):
    play_out(client, tournament, admin)

    body = view(client, tournament)
    assert body["tournament"]["status"] == "complete"
    assert body["tournament"]["completed_at"] is not None
    # Every public and admin read agrees: status is derived, not stored.
    assert client.get(url(tournament)).json()["status"] == "complete"
    assert (
        client.get(url(tournament, "/admin"), headers=admin).json()["status"]
        == "complete"
    )


def test_correcting_the_final_keeps_the_tournament_complete(client, tournament, admin):
    play_out(client, tournament, admin)
    final = view(client, tournament)["bracket"]["rounds"][-1]["matches"][0]

    report(client, tournament, admin, final, 1, 6)

    body = view(client, tournament)
    assert body["tournament"]["status"] == "complete"
    assert body["bracket"]["champion"]["name"] == "B"


def test_view_never_contains_the_token_or_its_hash(
    client, tournament, admin, db_session
):
    token = tournament["admin_token"]
    token_hash = db_session.get(Tournament, tournament["id"]).admin_token_hash
    assert token_hash == hash_admin_token(token)

    def check(response):
        text = response.text
        assert token not in text
        assert token_hash not in text
        for key in ("admin_token", "admin_path", "admin_token_hash"):
            assert key not in text

    check(client.get(url(tournament, "/public")))
    play_out(client, tournament, admin)
    # With the organizer token sent too: the public view ignores it.
    for path in ("/public", "", "/teams", "/bracket"):
        check(client.get(url(tournament, path)))
        check(client.get(url(tournament, path), headers=admin))


def test_view_is_read_only(client, tournament):
    for method in ("post", "put", "patch", "delete"):
        response = getattr(client, method)(url(tournament, "/public"))
        assert response.status_code == 405


@pytest.mark.parametrize(
    "tournament_id",
    ["nope", "x" * 200, "AbCdEfGh", "%20", "a.b"],
)
def test_unknown_tournament_is_404(client, tournament_id):
    response = client.get(f"/api/tournaments/{tournament_id}/public")

    assert response.status_code == 404
    assert response.json() == {"detail": "Tournament not found."}


def test_404_does_not_depend_on_the_id_resembling_a_real_one(client, tournament):
    # Same body for an ID that differs from a real one only by case as for
    # nonsense, so the response can't be used to probe for existing IDs.
    near = tournament["id"].swapcase()
    if near == tournament["id"]:
        pytest.skip("ID has no letters to change the case of")
    responses = [client.get(f"/api/tournaments/{tid}/public") for tid in (near, "nope")]
    assert [r.status_code for r in responses] == [404, 404]
    assert json.loads(responses[0].text) == json.loads(responses[1].text)
