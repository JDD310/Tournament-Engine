"""Serving the built frontend next to the API (app/spa.py) and response headers."""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import ReferrerPolicyMiddleware, app
from app.routers import tournaments
from app.spa import ASSET_CACHE_CONTROL, install_spa

INDEX_HTML = "<!doctype html><title>Tournament Engine</title>"
BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture
def dist(tmp_path):
    (tmp_path / "index.html").write_text(INDEX_HTML)
    (tmp_path / "favicon.svg").write_text("<svg/>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    return tmp_path


@pytest.fixture
def spa_client(dist, client):
    # The `client` fixture wires the test database into the shared routers.
    spa_app = FastAPI()
    spa_app.include_router(tournaments.router)
    spa_app.add_middleware(ReferrerPolicyMiddleware)
    install_spa(spa_app, dist)
    spa_app.dependency_overrides = app.dependency_overrides
    return TestClient(spa_app)


@pytest.mark.parametrize(
    "path", ["/", "/t/abc123", "/t/abc123/manage", "/no/such/page"]
)
def test_app_routes_get_index_html(spa_client, path):
    response = spa_client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX_HTML
    assert response.headers["content-type"].startswith("text/html")
    assert response.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_cached(spa_client):
    response = spa_client.get("/assets/index-abc123.js")

    assert response.status_code == 200
    assert response.headers["cache-control"] == ASSET_CACHE_CONTROL


def test_missing_asset_is_a_404_not_the_app(spa_client):
    response = spa_client.get("/assets/index-gone.js")

    assert response.status_code == 404
    assert response.text != INDEX_HTML


def test_root_files_are_served(spa_client):
    response = spa_client.get("/favicon.svg")

    assert response.status_code == 200
    assert response.text == "<svg/>"


def test_path_traversal_falls_back_to_the_app(spa_client):
    response = spa_client.get("/..%2Fsecret.txt")

    assert response.text == INDEX_HTML


def test_unknown_api_path_is_still_json(spa_client):
    response = spa_client.get("/api/nope")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"detail": "Not Found"}


def test_api_404_from_a_route_is_still_json(spa_client):
    response = spa_client.get("/api/tournaments/missing/public")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"


def test_wrong_method_on_api_path_keeps_405(spa_client):
    response = spa_client.get("/api/tournaments")

    assert response.status_code == 405


def test_api_still_works_with_the_app_mounted(spa_client):
    response = spa_client.post(
        "/api/tournaments",
        json={"name": "Cup", "game": "Chess", "format": "single_elimination"},
    )

    assert response.status_code == 201
    assert spa_client.get(f"/t/{response.json()['id']}").text == INDEX_HTML


def test_post_to_an_app_route_is_not_the_app(spa_client):
    assert spa_client.post("/t/abc123").status_code == 404


def test_install_spa_requires_a_build(tmp_path):
    with pytest.raises(RuntimeError, match="index.html"):
        install_spa(FastAPI(), tmp_path)


@pytest.mark.parametrize("path", ["/api/health", "/api/nope"])
def test_referrer_policy_header(client, path):
    response = client.get(path)

    assert response.headers["referrer-policy"] == "same-origin"


def test_referrer_policy_header_on_the_app(spa_client):
    assert spa_client.get("/t/abc123").headers["referrer-policy"] == "same-origin"


def test_frontend_dist_setting_turns_on_serving(dist):
    """FRONTEND_DIST (set in the Docker image) wires app/spa.py into app.main."""
    script = (
        "from fastapi.testclient import TestClient\n"
        "from app.main import app\n"
        "c = TestClient(app)\n"
        "r = c.get('/t/x')\n"
        "assert r.status_code == 200 and 'Tournament Engine' in r.text, r.text\n"
        "assert c.get('/api/health').json() == {'status': 'ok'}\n"
    )
    env = {**os.environ, "FRONTEND_DIST": str(dist), "DATABASE_URL": "sqlite://"}
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
