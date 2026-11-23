from datetime import datetime
from enum import Enum

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictInt,
    field_validator,
    model_validator,
)

from app.models import TEAM_NAME_MAX_LENGTH

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


class TeamName(BaseModel):
    """Body for adding or renaming a team."""

    name: str = Field(description="Team name")

    @model_validator(mode="before")
    @classmethod
    def missing_name_is_none(cls, data: object) -> object:
        # Lets the field validator report a missing name as "Team name is
        # required." (the generic handler would call it "Tournament name").
        if isinstance(data, dict) and "name" not in data:
            return {**data, "name": None}
        return data

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _required_text(value, "Team name", TEAM_NAME_MAX_LENGTH)


class TeamSeeding(BaseModel):
    team_ids: list[StrictInt] = Field(
        description="IDs of the seeded teams, top seed first. Teams that are "
        "left out become unseeded."
    )

    @field_validator("team_ids")
    @classmethod
    def no_duplicates(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Each team can only be seeded once.")
        return value


class TeamPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    seed: int | None


class TeamList(BaseModel):
    # True once the bracket is generated; the teams can't be changed after that.
    locked: bool
    # Seeded teams by seed, then unseeded teams in the order they were added.
    teams: list[TeamPublic]
