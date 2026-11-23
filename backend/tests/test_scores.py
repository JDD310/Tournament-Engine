"""Reporting and correcting match scores (TE-9: TE-37, TE-38, TE-39)."""

import pytest
from sqlalchemy.orm import Session

from app.models import Match
from app.routers import tournaments as tournaments_router
from app.routers.matches import (
    BYE_MATCH,
    MATCH_NOT_FOUND,
    NEXT_MATCH_PLAYED,
    TEAMS_NOT_KNOWN,
    TIE_NOT_ALLOWED,
)
from app.schemas import MAX_SCORE
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


def make_bracket(client, tournament, admin, names):
    """Add ``names`` seeded in order and generate the bracket."""
    ids = [
        client.post(url(tournament, "/teams"), json={"name": n}, headers=admin).json()[
            "id"
        ]
        for n in names
    ]
    client.put(url(tournament, "/teams/seeding"), json={"team_ids": ids}, headers=admin)
    response = client.post(url(tournament, "/bracket"), headers=admin)
    assert response.status_code == 201
    return response.json()


def report(client, tournament, admin, match_id, team1_score, team2_score):
    return client.put(
        url(tournament, f"/matches/{match_id}/score"),
        json={"team1_score": team1_score, "team2_score": team2_score},
        headers=admin,
    )


def match_at(bracket, round_number, position):
    return bracket["rounds"][round_number - 1]["matches"][position]


def names(match):
    return tuple(t and t["name"] for t in (match["team1"], match["team2"]))


def winner_name(match):
    for team in (match["team1"], match["team2"]):
        if team and team["id"] == match["winner_id"]:
            return team["name"]
    return None


def bracket(client, tournament):
    return client.get(url(tournament, "/bracket")).json()


@pytest.fixture
def four(client, tournament, admin):
    """A-D seeded 1-4: semifinals A v D (feeds final slot 1), B v C (slot 2)."""
    return make_bracket(client, tournament, admin, ["A", "B", "C", "D"])


# --- Reporting and advancement (TE-37, TE-38) ----------------------------


def test_report_records_the_score_and_returns_the_bracket(
    client, tournament, admin, four
):
    semi = match_at(four, 1, 0)

    response = report(client, tournament, admin, semi["id"], 3, 1)

    assert response.status_code == 200
    reported = match_at(response.json(), 1, 0)
    assert (reported["team1_score"], reported["team2_score"]) == (3, 1)
    assert winner_name(reported) == "A"
    assert response.json() == bracket(client, tournament)


def test_winner_of_the_top_match_goes_into_slot_1(client, tournament, admin, four):
    report(client, tournament, admin, match_at(four, 1, 0)["id"], 2, 0)

    assert names(match_at(bracket(client, tournament), 2, 0)) == ("A", None)


def test_winner_of_the_bottom_match_goes_into_slot_2(client, tournament, admin, four):
    report(client, tournament, admin, match_at(four, 1, 1)["id"], 2, 0)

    assert names(match_at(bracket(client, tournament), 2, 0)) == (None, "B")


def test_team2_can_win(client, tournament, admin, four):
    report(client, tournament, admin, match_at(four, 1, 0)["id"], 1, 4)
    report(client, tournament, admin, match_at(four, 1, 1)["id"], 0, 2)

    result = bracket(client, tournament)
    assert winner_name(match_at(result, 1, 0)) == "D"
    assert names(match_at(result, 2, 0)) == ("D", "C")


def test_bye_winner_meets_an_opponent_reported_later(client, tournament, admin):
    # Three teams: A has a bye into the final; B plays C for the other slot.
    generated = make_bracket(client, tournament, admin, ["A", "B", "C"])
    bye, played = match_at(generated, 1, 0), match_at(generated, 1, 1)
    assert bye["is_bye"] and names(match_at(generated, 2, 0)) == ("A", None)

    report(client, tournament, admin, played["id"], 1, 2)

    final = match_at(bracket(client, tournament), 2, 0)
    assert names(final) == ("A", "C")
    assert report(client, tournament, admin, final["id"], 0, 1).status_code == 200
    assert bracket(client, tournament)["champion"]["name"] == "C"


def test_reporting_the_final_completes_the_tournament(client, tournament, admin, four):
    report(client, tournament, admin, match_at(four, 1, 0)["id"], 2, 1)
    report(client, tournament, admin, match_at(four, 1, 1)["id"], 2, 1)
    assert bracket(client, tournament)["champion"] is None
    assert client.get(url(tournament)).json()["completed_at"] is None

    final = match_at(bracket(client, tournament), 2, 0)
    response = report(client, tournament, admin, final["id"], 1, 3)

    assert response.status_code == 200
    assert response.json()["champion"]["name"] == "B"
    assert response.json()["champion"]["seed"] == 2
    assert client.get(url(tournament)).json()["completed_at"] is not None
    assert (
        client.get(url(tournament, "/admin"), headers=admin).json()["completed_at"]
        == client.get(url(tournament)).json()["completed_at"]
    )


def test_two_team_bracket_is_just_a_final(client, tournament, admin):
    generated = make_bracket(client, tournament, admin, ["A", "B"])

    report(client, tournament, admin, match_at(generated, 1, 0)["id"], 5, 4)

    assert bracket(client, tournament)["champion"]["name"] == "A"
    assert client.get(url(tournament)).json()["completed_at"] is not None


def test_full_eight_team_tournament(client, tournament, admin, db_session):
    generated = make_bracket(client, tournament, admin, list("ABCDEFGH"))
    assert [names(m) for m in generated["rounds"][0]["matches"]] == [
        ("A", "H"),
        ("D", "E"),
        ("B", "G"),
        ("C", "F"),
    ]

    # Round 1: the lower seed (team2) wins every match. Then team1 wins.
    for match in generated["rounds"][0]["matches"]:
        assert report(client, tournament, admin, match["id"], 0, 1).status_code == 200
    semis_in = [names(m) for m in bracket(client, tournament)["rounds"][1]["matches"]]
    assert semis_in == [("H", "E"), ("G", "F")]
    for match in bracket(client, tournament)["rounds"][1]["matches"]:
        assert report(client, tournament, admin, match["id"], 2, 1).status_code == 200
    final = match_at(bracket(client, tournament), 3, 0)
    assert names(final) == ("H", "G")
    assert report(client, tournament, admin, final["id"], 3, 2).status_code == 200

    result = bracket(client, tournament)
    assert result["champion"]["name"] == "H"
    assert client.get(url(tournament)).json()["completed_at"] is not None
    # Every winner is one of its match's teams and is in the slot it feeds.
    matches = {m["id"]: m for r in result["rounds"] for m in r["matches"]}
    for m in matches.values():
        assert m["winner_id"] in {m["team1"]["id"], m["team2"]["id"]}
        if m["next_match_id"] is not None:
            fed = matches[m["next_match_id"]][f"team{m['next_slot']}"]
            assert fed["id"] == m["winner_id"]
    # Every match is decided; none is still waiting.
    assert all(
        m.winner_id is not None
        for m in db_session.query(Match).filter_by(tournament_id=tournament["id"])
    )


# --- Rejections (TE-37) --------------------------------------------------


def test_bye_cannot_be_reported(client, tournament, admin):
    generated = make_bracket(client, tournament, admin, ["A", "B", "C"])
    bye = match_at(generated, 1, 0)

    response = report(client, tournament, admin, bye["id"], 1, 0)

    assert response.status_code == 409
    assert response.json()["detail"] == BYE_MATCH
    assert bracket(client, tournament) == generated


def test_match_with_a_team_still_to_be_decided_cannot_be_reported(
    client, tournament, admin, four
):
    report(client, tournament, admin, match_at(four, 1, 0)["id"], 2, 0)
    before = bracket(client, tournament)

    response = report(client, tournament, admin, match_at(four, 2, 0)["id"], 1, 0)

    assert response.status_code == 409
    assert response.json()["detail"] == TEAMS_NOT_KNOWN
    assert bracket(client, tournament) == before


def test_tie_is_rejected(client, tournament, admin, four):
    response = report(client, tournament, admin, match_at(four, 1, 0)["id"], 2, 2)

    assert response.status_code == 422
    assert response.json()["detail"] == TIE_NOT_ALLOWED
    assert bracket(client, tournament) == four


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ({"team1_score": -1, "team2_score": 2}, "Team 1 score can't be negative."),
        ({"team1_score": 2, "team2_score": -3}, "Team 2 score can't be negative."),
        (
            {"team1_score": 1.5, "team2_score": 0},
            "Team 1 score must be a whole number.",
        ),
        (
            {"team1_score": "3", "team2_score": 0},
            "Team 1 score must be a whole number.",
        ),
        (
            {"team1_score": True, "team2_score": 0},
            "Team 1 score must be a whole number.",
        ),
        (
            {"team1_score": None, "team2_score": 0},
            "Team 1 score must be a whole number.",
        ),
        (
            {"team1_score": MAX_SCORE + 1, "team2_score": 0},
            f"Team 1 score must be {MAX_SCORE:,} or less.",
        ),
        ({"team2_score": 0}, "Team 1 score is required."),
    ],
)
def test_invalid_scores_are_rejected(client, tournament, admin, four, body, message):
    response = client.put(
        url(tournament, f"/matches/{match_at(four, 1, 0)['id']}/score"),
        json=body,
        headers=admin,
    )

    assert response.status_code == 422
    assert message in [e["message"] for e in response.json()["errors"]]
    assert bracket(client, tournament) == four


def test_highest_allowed_score_is_accepted(client, tournament, admin, four):
    response = report(
        client, tournament, admin, match_at(four, 1, 0)["id"], MAX_SCORE, 0
    )

    assert response.status_code == 200


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "not-the-token"}])
def test_reporting_needs_the_organizer_token(client, tournament, four, headers):
    response = report(client, tournament, headers, match_at(four, 1, 0)["id"], 2, 0)

    assert response.status_code == 403
    assert bracket(client, tournament) == four


def test_another_tournaments_token_is_refused(client, tournament, four):
    other = client.post("/api/tournaments", json=TOURNAMENT).json()
    headers = {"X-Admin-Token": other["admin_token"]}

    response = report(client, tournament, headers, match_at(four, 1, 0)["id"], 2, 0)

    assert response.status_code == 403


def test_match_from_another_tournament_is_404(client, tournament, admin, four):
    other = client.post("/api/tournaments", json=TOURNAMENT).json()
    other_admin = {"X-Admin-Token": other["admin_token"]}
    theirs = make_bracket(client, other, other_admin, ["X", "Y"])
    their_match = match_at(theirs, 1, 0)

    # Our token, our tournament in the URL, their match ID.
    response = report(client, tournament, admin, their_match["id"], 2, 0)

    assert response.status_code == 404
    assert response.json()["detail"] == MATCH_NOT_FOUND
    assert bracket(client, other) == theirs


def test_unknown_match_and_tournament_are_404(client, tournament, admin, four):
    assert report(client, tournament, admin, 999999, 2, 0).status_code == 404
    response = client.put(
        "/api/tournaments/nope/matches/1/score",
        json={"team1_score": 1, "team2_score": 0},
        headers=admin,
    )
    assert response.status_code == 404


def test_no_matches_before_the_bracket_is_generated(client, tournament, admin):
    assert report(client, tournament, admin, 1, 2, 0).status_code == 404


# --- Corrections (TE-39) -------------------------------------------------


def test_correction_with_the_same_winner_just_updates_the_score(
    client, tournament, admin, four
):
    semi = match_at(four, 1, 0)
    report(client, tournament, admin, semi["id"], 2, 0)

    response = report(client, tournament, admin, semi["id"], 3, 2)

    assert response.status_code == 200
    corrected = match_at(response.json(), 1, 0)
    assert (corrected["team1_score"], corrected["team2_score"]) == (3, 2)
    assert names(match_at(response.json(), 2, 0)) == ("A", None)


def test_correction_that_flips_the_winner_swaps_the_advanced_team(
    client, tournament, admin, four
):
    top, bottom = match_at(four, 1, 0), match_at(four, 1, 1)
    report(client, tournament, admin, top["id"], 2, 0)
    report(client, tournament, admin, bottom["id"], 2, 0)
    assert names(match_at(bracket(client, tournament), 2, 0)) == ("A", "B")

    response = report(client, tournament, admin, top["id"], 0, 2)

    assert response.status_code == 200
    result = response.json()
    assert winner_name(match_at(result, 1, 0)) == "D"
    # D replaces A; B, from the other semifinal, is untouched.
    assert names(match_at(result, 2, 0)) == ("D", "B")


def test_corrected_winner_is_the_one_who_plays_on(client, tournament, admin, four):
    top, bottom = match_at(four, 1, 0), match_at(four, 1, 1)
    report(client, tournament, admin, top["id"], 2, 0)
    report(client, tournament, admin, top["id"], 0, 2)
    report(client, tournament, admin, bottom["id"], 2, 0)
    final = match_at(bracket(client, tournament), 2, 0)

    report(client, tournament, admin, final["id"], 1, 0)

    assert bracket(client, tournament)["champion"]["name"] == "D"


def test_correction_after_the_next_match_is_played_is_refused(
    client, tournament, admin, four
):
    top, bottom = match_at(four, 1, 0), match_at(four, 1, 1)
    report(client, tournament, admin, top["id"], 2, 0)
    report(client, tournament, admin, bottom["id"], 2, 0)
    report(client, tournament, admin, match_at(four, 2, 0)["id"], 2, 1)
    before = bracket(client, tournament)

    flip = report(client, tournament, admin, top["id"], 0, 2)
    same_winner = report(client, tournament, admin, top["id"], 5, 0)

    for response in (flip, same_winner):
        assert response.status_code == 409
        assert response.json()["detail"] == NEXT_MATCH_PLAYED
    assert bracket(client, tournament) == before


def test_correction_while_the_next_match_waits_for_its_other_team(
    client, tournament, admin
):
    # 8 teams: correct a quarterfinal whose semifinal has only one team so far.
    generated = make_bracket(client, tournament, admin, list("ABCDEFGH"))
    qf = match_at(generated, 1, 0)
    report(client, tournament, admin, qf["id"], 1, 0)

    report(client, tournament, admin, qf["id"], 0, 1)

    assert names(match_at(bracket(client, tournament), 2, 0)) == ("H", None)


def test_final_can_be_corrected_and_changes_the_champion(
    client, tournament, admin, four
):
    report(client, tournament, admin, match_at(four, 1, 0)["id"], 2, 0)
    report(client, tournament, admin, match_at(four, 1, 1)["id"], 2, 0)
    final = match_at(bracket(client, tournament), 2, 0)
    report(client, tournament, admin, final["id"], 2, 0)
    completed_at = client.get(url(tournament)).json()["completed_at"]

    response = report(client, tournament, admin, final["id"], 0, 2)

    assert response.status_code == 200
    assert response.json()["champion"]["name"] == "B"
    assert client.get(url(tournament)).json()["completed_at"] == completed_at


def test_correction_is_still_validated(client, tournament, admin, four):
    semi = match_at(four, 1, 0)
    report(client, tournament, admin, semi["id"], 2, 0)
    before = bracket(client, tournament)

    assert report(client, tournament, admin, semi["id"], 1, 1).status_code == 422
    assert report(client, tournament, admin, semi["id"], -1, 0).status_code == 422
    assert report(client, tournament, {}, semi["id"], 0, 2).status_code == 403
    assert bracket(client, tournament) == before


# --- Locking and privacy -------------------------------------------------


def test_report_takes_the_tournament_lock_before_reading_a_match(
    client, tournament, admin, four, monkeypatch
):
    events = []
    real_lock = tournaments_router.lock_tournament
    real_get = Session.get

    def spy_lock(db, tid):
        events.append(("lock", tid))
        return real_lock(db, tid)

    def spy_get(self, entity, *args, **kwargs):
        events.append(("get", entity.__name__))
        return real_get(self, entity, *args, **kwargs)

    monkeypatch.setattr(tournaments_router, "lock_tournament", spy_lock)
    monkeypatch.setattr(Session, "get", spy_get)

    assert (
        report(client, tournament, admin, match_at(four, 1, 0)["id"], 2, 0).status_code
        == 200
    )

    assert events[0] == ("lock", tournament["id"])
    assert ("get", "Match") in events
    assert events.count(("lock", tournament["id"])) == 1


def test_refused_report_also_takes_the_lock_first(
    client, tournament, admin, four, monkeypatch
):
    locked = []
    real_lock = tournaments_router.lock_tournament

    def spy(db, tid):
        locked.append(tid)
        return real_lock(db, tid)

    monkeypatch.setattr(tournaments_router, "lock_tournament", spy)

    report(client, tournament, admin, match_at(four, 2, 0)["id"], 1, 0)

    assert locked == [tournament["id"]]


def test_reads_after_reporting_never_expose_the_token(client, tournament, admin, four):
    token = tournament["admin_token"]
    reported = report(client, tournament, admin, match_at(four, 1, 0)["id"], 2, 0)
    bodies = [
        reported.text,
        client.get(url(tournament, "/bracket")).text,
        client.get(url(tournament)).text,
    ]

    for body in bodies:
        assert token not in body
        assert hash_admin_token(token) not in body
