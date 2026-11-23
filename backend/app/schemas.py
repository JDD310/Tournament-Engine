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
from app.teams import MAX_TEAMS, too_many_teams_message

NAME_MAX_LENGTH = 100
GAME_MAX_LENGTH = 100
# Well inside a Postgres INTEGER, and far beyond any real game's score.
MAX_SCORE = 999_999


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
    # Set when the final is reported: the tournament is Complete.
    completed_at: datetime | None = None


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
        "left out become unseeded.",
        json_schema_extra={"maxItems": MAX_TEAMS},
    )

    @field_validator("team_ids", mode="before")
    @classmethod
    def not_too_long(cls, value: object) -> object:
        # Checked before the items are validated, with the same message as the
        # team cap, rather than Field(max_length=...)'s generic one.
        if isinstance(value, list) and len(value) > MAX_TEAMS:
            raise ValueError(too_many_teams_message())
        return value

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


class BracketTeam(BaseModel):
    """A team as shown in the bracket. ``seed`` is None for unseeded teams."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    seed: int | None


class MatchPublic(BaseModel):
    id: int
    round: int
    position: int
    # None while the team is still to be decided, and for team2 of a bye.
    team1: BracketTeam | None
    team2: BracketTeam | None
    winner_id: int | None
    is_bye: bool
    # The match the winner moves on to, and as team1 (1) or team2 (2). None for
    # the final.
    next_match_id: int | None
    next_slot: int | None
    # The reported score; both None until the match is reported (and for byes).
    team1_score: int | None = None
    team2_score: int | None = None


class RoundPublic(BaseModel):
    round: int
    name: str
    matches: list[MatchPublic]


class BracketPublic(BaseModel):
    generated: bool
    # Round 1 first; matches top to bottom. Empty until generated.
    rounds: list[RoundPublic]
    # The final's winner, once the final is reported (the tournament is then
    # Complete). None until then.
    champion: BracketTeam | None = None


def _score(value: object, label: str) -> int:
    # bool is an int subclass in Python, and JSON true/false aren't scores.
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{label} must be a whole number.")
    if value < 0:
        raise ValueError(f"{label} can't be negative.")
    if value > MAX_SCORE:
        raise ValueError(f"{label} must be {MAX_SCORE:,} or less.")
    return value


class ScoreReport(BaseModel):
    """Body for reporting (or correcting) a match's score.

    The team with the higher score wins. Whether a tie is allowed depends on
    the format, so it is checked by the endpoint, not here.
    """

    team1_score: int = Field(description="Score of team1", ge=0, le=MAX_SCORE)
    team2_score: int = Field(description="Score of team2", ge=0, le=MAX_SCORE)

    @field_validator("team1_score", mode="before")
    @classmethod
    def validate_team1_score(cls, value: object) -> int:
        return _score(value, "Team 1 score")

    @field_validator("team2_score", mode="before")
    @classmethod
    def validate_team2_score(cls, value: object) -> int:
        return _score(value, "Team 2 score")
