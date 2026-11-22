from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAME_MAX_LENGTH = 100
GAME_MAX_LENGTH = 100


class TournamentFormat(str, Enum):
    # Swiss is added in Sprint 2 (TE-7).
    single_elimination = "single_elimination"


def _required_text(value: object, label: str, max_length: int) -> str:
    if value is None:
        raise ValueError(f"{label} is required.")
    if not isinstance(value, str):
        raise ValueError(f"{label} must be text.")
    value = value.strip()
    if not value:
        raise ValueError(f"{label} is required.")
    if len(value) > max_length:
        raise ValueError(f"{label} must be {max_length} characters or fewer.")
    return value


class TournamentCreate(BaseModel):
    name: str = Field(description="Tournament name")
    game: str = Field(description="Game being played")
    format: TournamentFormat

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _required_text(value, "Tournament name", NAME_MAX_LENGTH)

    @field_validator("game", mode="before")
    @classmethod
    def validate_game(cls, value: object) -> str:
        return _required_text(value, "Game", GAME_MAX_LENGTH)


class TournamentUpdate(BaseModel):
    name: str | None = None
    game: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _required_text(value, "Tournament name", NAME_MAX_LENGTH)

    @field_validator("game", mode="before")
    @classmethod
    def validate_game(cls, value: object) -> str:
        return _required_text(value, "Game", GAME_MAX_LENGTH)


class TournamentPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    game: str
    format: TournamentFormat
    created_at: datetime
    public_path: str


class TournamentCreated(TournamentPublic):
    admin_token: str
    admin_path: str
