import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import normalize_database_url
from app.db import Base, get_db
from app.main import app

# Tests run against in-memory SQLite by default so they need no setup.
# Set TEST_DATABASE_URL to run them against a real Postgres database instead.
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
def engine():
    if TEST_DATABASE_URL:
        engine = create_engine(normalize_database_url(TEST_DATABASE_URL))
    else:
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(engine):
    TestSession = sessionmaker(bind=engine, expire_on_commit=False)
    with TestSession() as session:
        yield session


@pytest.fixture
def client(engine):
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    # Not used as a context manager, so the startup create_all against the
    # real DATABASE_URL never runs during tests.
    yield TestClient(app)
    app.dependency_overrides.clear()
