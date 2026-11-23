import io

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app import migrate
from app.config import get_settings
from app.db import Base
from app.main import app


def test_migrations_match_models(engine):
    """Fails if a model changes without a matching migration."""
    with engine.connect() as connection:
        diff = compare_metadata(
            MigrationContext.configure(connection, opts={"compare_type": True}),
            Base.metadata,
        )

    assert diff == []


def test_migrations_are_at_head(engine):
    with engine.connect() as connection:
        current = MigrationContext.configure(connection).get_current_revision()

    head = ScriptDirectory.from_config(migrate.alembic_config()).get_current_head()
    assert current == head


def test_downgrade_to_base_removes_tables(engine):
    with engine.begin() as connection:
        migrate.downgrade(connection, "base")
        assert inspect(connection).get_table_names() == ["alembic_version"]
        migrate.upgrade(connection)
        assert {"tournaments", "teams", "matches"} <= set(
            inspect(connection).get_table_names()
        )


def test_downgrade_from_teams_keeps_tournaments(engine):
    with engine.begin() as connection:
        migrate.downgrade(connection, "0001")
        inspector = inspect(connection)
        assert "teams" not in inspector.get_table_names()
        columns = {c["name"] for c in inspector.get_columns("tournaments")}
        assert "bracket_generated" not in columns
        migrate.upgrade(connection)
        columns = {c["name"] for c in inspect(connection).get_columns("tournaments")}
        assert "bracket_generated" in columns


def test_downgrade_from_matches_keeps_teams(engine):
    with engine.begin() as connection:
        migrate.downgrade(connection, "0002")
        tables = set(inspect(connection).get_table_names())
        assert "matches" not in tables
        assert {"tournaments", "teams"} <= tables
        migrate.upgrade(connection)
        assert "matches" in inspect(connection).get_table_names()


def test_downgrade_from_scores_keeps_matches(engine):
    with engine.begin() as connection:
        migrate.downgrade(connection, "0003")
        inspector = inspect(connection)
        match_columns = {c["name"] for c in inspector.get_columns("matches")}
        assert {"team1_score", "team2_score"}.isdisjoint(match_columns)
        assert "winner_id" in match_columns
        tournament_columns = {c["name"] for c in inspector.get_columns("tournaments")}
        assert "completed_at" not in tournament_columns
        assert "bracket_generated" in tournament_columns
        migrate.upgrade(connection)
        inspector = inspect(connection)
        assert {"team1_score", "team2_score"} <= {
            c["name"] for c in inspector.get_columns("matches")
        }
        assert "completed_at" in {
            c["name"] for c in inspector.get_columns("tournaments")
        }


def test_offline_sql_for_postgres(monkeypatch):
    """Render the Postgres DDL without needing a database."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@localhost/te")
    get_settings.cache_clear()
    buffer = io.StringIO()
    config = migrate.alembic_config()
    config.output_buffer = buffer
    try:
        command.upgrade(config, "head", sql=True)
    finally:
        get_settings.cache_clear()

    sql = buffer.getvalue()
    assert "CREATE TABLE tournaments" in sql
    assert "created_at TIMESTAMP WITH TIME ZONE NOT NULL" in sql
    assert "CREATE TABLE alembic_version" in sql
    assert "CREATE TABLE teams" in sql
    assert "id SERIAL NOT NULL" in sql
    assert (
        "FOREIGN KEY(tournament_id) REFERENCES tournaments (id) ON DELETE CASCADE"
        in sql
    )
    assert "ADD COLUMN bracket_generated BOOLEAN DEFAULT false NOT NULL" in sql
    assert "CREATE TABLE matches" in sql
    assert "FOREIGN KEY(next_match_id) REFERENCES matches (id)" in sql
    assert "FOREIGN KEY(winner_id) REFERENCES teams (id)" in sql
    assert "ALTER TABLE matches ADD COLUMN team1_score INTEGER" in sql
    assert "ALTER TABLE matches ADD COLUMN team2_score INTEGER" in sql
    assert (
        "ALTER TABLE tournaments ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE"
        in sql
    )


def test_app_startup_does_not_create_tables(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("create_all must not run at startup")

    monkeypatch.setattr(Base.metadata, "create_all", fail)

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
