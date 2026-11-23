from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://localhost/tournament_engine"
    # Directory holding the built frontend (frontend/dist). When set, the app
    # serves it alongside the API; the Docker image sets it. See app/spa.py.
    frontend_dist: str | None = None


def normalize_database_url(url: str) -> str:
    """Neon and most providers hand out ``postgresql://`` URLs; SQLAlchemy needs
    the driver named explicitly to use psycopg 3."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
