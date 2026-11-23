import pytest

from app.models import Tournament
from app.security import hash_admin_token

VALID = {
    "name": "Friday Night Smash",
    "game": "Super Smash Bros.",
    "format": "single_elimination",
}


def create(client, **overrides):
    return client.post("/api/tournaments", json={**VALID, **overrides})


def errors_by_field(response):
    return {e["field"]: e["message"] for e in response.json()["errors"]}


def test_create_tournament_returns_ids_and_links(client):
    response = create(client)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == VALID["name"]
    assert body["game"] == VALID["game"]
    assert body["format"] == "single_elimination"
    assert body["public_path"] == f"/t/{body['id']}"
    assert body["admin_path"] == f"/t/{body['id']}/manage?token={body['admin_token']}"
    assert len(body["admin_token"]) >= 32


def test_create_tournament_is_persisted_with_hashed_token(client, db_session):
    body = create(client).json()

    stored = db_session.get(Tournament, body["id"])
    assert stored is not None
    assert stored.name == VALID["name"]
    assert stored.admin_token_hash == hash_admin_token(body["admin_token"])
    assert stored.admin_token_hash != body["admin_token"]


def test_each_tournament_gets_unique_id_and_token(client):
    first, second = create(client).json(), create(client).json()

    assert first["id"] != second["id"]
    assert first["admin_token"] != second["admin_token"]


def test_create_trims_whitespace(client):
    body = create(client, name="  Weekly Cup  ", game=" Valorant ").json()

    assert body["name"] == "Weekly Cup"
    assert body["game"] == "Valorant"


def test_public_get_does_not_expose_admin_token(client):
    created = create(client).json()

    response = client.get(f"/api/tournaments/{created['id']}")

    assert response.status_code == 200
    assert response.json()["name"] == VALID["name"]
    assert "admin_token" not in response.json()
    assert "admin_path" not in response.json()


def test_get_unknown_tournament_is_404(client):
    response = client.get("/api/tournaments/nope")

    assert response.status_code == 404
    assert response.json()["detail"] == "Tournament not found."


def test_admin_view_requires_valid_token(client):
    created = create(client).json()
    url = f"/api/tournaments/{created['id']}/admin"

    assert (
        client.get(url, headers={"X-Admin-Token": created["admin_token"]}).status_code
        == 200
    )
    assert client.get(url).status_code == 403
    assert client.get(url, headers={"X-Admin-Token": "wrong"}).status_code == 403


def test_organizer_can_edit_with_token(client):
    created = create(client).json()

    response = client.patch(
        f"/api/tournaments/{created['id']}",
        json={"name": "Renamed Cup"},
        headers={"X-Admin-Token": created["admin_token"]},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Renamed Cup"
    assert response.json()["game"] == VALID["game"]


@pytest.mark.parametrize("headers", [{}, {"X-Admin-Token": "wrong"}])
def test_edit_without_valid_token_is_forbidden(client, headers):
    created = create(client).json()

    response = client.patch(
        f"/api/tournaments/{created['id']}", json={"name": "Hijacked"}, headers=headers
    )

    assert response.status_code == 403
    assert "organizer link" in response.json()["detail"]
    assert (
        client.get(f"/api/tournaments/{created['id']}").json()["name"] == VALID["name"]
    )


def test_token_for_one_tournament_cannot_edit_another(client):
    first, second = create(client).json(), create(client).json()

    response = client.patch(
        f"/api/tournaments/{second['id']}",
        json={"name": "Hijacked"},
        headers={"X-Admin-Token": first["admin_token"]},
    )

    assert response.status_code == 403


def test_missing_fields_report_each_one(client):
    response = client.post("/api/tournaments", json={})

    assert response.status_code == 422
    assert errors_by_field(response) == {
        "name": "Tournament name is required.",
        "game": "Game is required.",
        "format": "Format is required.",
    }


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("name", "   ", "Tournament name is required."),
        ("name", "x" * 101, "Tournament name must be 100 characters or fewer."),
        ("game", "", "Game is required."),
        ("game", 42, "Game must be text."),
        ("format", "swiss", "Format must be single_elimination."),
    ],
)
def test_invalid_fields_have_clear_messages(client, field, value, message):
    response = create(client, **{field: value})

    assert response.status_code == 422
    assert errors_by_field(response) == {field: message}


def test_edit_validates_fields(client):
    created = create(client).json()

    response = client.patch(
        f"/api/tournaments/{created['id']}",
        json={"name": ""},
        headers={"X-Admin-Token": created["admin_token"]},
    )

    assert response.status_code == 422
    assert errors_by_field(response) == {"name": "Tournament name is required."}


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("{bad", "Request body must be valid JSON."),
        ("[1]", "Request body must be a JSON object."),
        ('"text"', "Request body must be a JSON object."),
        ("", "Request body is required."),
    ],
)
def test_malformed_body_has_clear_message(client, body, message):
    response = client.post(
        "/api/tournaments",
        content=body,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": message,
        "errors": [{"field": "", "message": message}],
    }
