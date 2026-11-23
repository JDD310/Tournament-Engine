"""Run database migrations.

Deploys should run ``python -m app.migrate`` (from ``backend/``) before
starting the app. It is the same as ``alembic upgrade head``.
"""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy.engine import Connection

ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


def alembic_config(connection: Connection | None = None) -> Config:
    config = Config(str(ALEMBIC_INI))
    if connection is not None:
        config.attributes["connection"] = connection
    return config


def upgrade(connection: Connection | None = None, revision: str = "head") -> None:
    """Migrate to ``revision``. Uses DATABASE_URL unless a connection is given."""
    command.upgrade(alembic_config(connection), revision)


def downgrade(connection: Connection, revision: str) -> None:
    command.downgrade(alembic_config(connection), revision)


if __name__ == "__main__":
    upgrade()
