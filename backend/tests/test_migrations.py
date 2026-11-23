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
        assert "tournaments" not in inspect(connection).get_table_names()
        migrate.upgrade(connection)
        assert "tournaments" in inspect(connection).get_table_names()


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


def test_app_startup_does_not_create_tables(monkeypatch):
    def fail(*args, **kwargs):
        raise AssertionError("create_all must not run at startup")

    monkeypatch.setattr(Base.metadata, "create_all", fail)

    with TestClient(app) as client:
        assert client.get("/api/health").json() == {"status": "ok"}
