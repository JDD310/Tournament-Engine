from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

import app.models  # noqa: F401  (registers tables on Base.metadata)
from app.config import get_settings, normalize_database_url
from app.db import Base

config = context.config
target_metadata = Base.metadata

# Callers such as the test suite pass an open connection in
# config.attributes["connection"]; they also manage logging themselves.
external_connection = config.attributes.get("connection")
if config.config_file_name is not None and external_connection is None:
    fileConfig(config.config_file_name)


def database_url() -> str:
    return normalize_database_url(get_settings().database_url)


def configure(**kwargs) -> None:
    context.configure(
        target_metadata=target_metadata,
        compare_type=True,
        **kwargs,
    )


def run_migrations_offline() -> None:
    """Emit SQL to stdout (``alembic upgrade head --sql``) without connecting."""
    configure(url=database_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_on(connection) -> None:
    # SQLite can't ALTER most things in place; batch mode rebuilds the table.
    configure(
        connection=connection,
        render_as_batch=connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    if external_connection is not None:
        run_migrations_on(external_connection)
        return
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        run_migrations_on(connection)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
