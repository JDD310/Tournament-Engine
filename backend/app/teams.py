"""Team rules shared by the API and, later, bracket generation (TE-6)."""

from collections.abc import Sequence

from app.models import Team

# A bracket needs at least this many teams.
MIN_BRACKET_TEAMS = 2


def team_name_key(name: str) -> str:
    """The form of a team name used for the uniqueness check.

    Names are compared ignoring case, surrounding whitespace and repeated inner
    whitespace, so "Team  Liquid " and "team liquid" count as the same name.
    """
    return " ".join(name.split()).casefold()


def seed_order(teams: Sequence[Team]) -> list[Team]:
    """Seeded teams by seed (1 first), then unseeded teams in the order added."""
    return sorted(teams, key=lambda t: (t.seed is None, t.seed or 0, t.id))


def renumber_seeds(ordered: Sequence[Team]) -> None:
    """Number the seeded teams in ``ordered`` 1..n, closing any gaps."""
    seed = 1
    for team in ordered:
        if team.seed is not None:
            team.seed = seed
            seed += 1


def bracket_readiness_error(team_count: int) -> str | None:
    """Why a bracket can't be generated yet, or None if it can.

    Bracket generation (TE-6) should call this and refuse if it returns a
    message, then set ``Tournament.bracket_generated`` to lock the teams.
    """
    if team_count < MIN_BRACKET_TEAMS:
        return (
            f"A tournament needs at least {MIN_BRACKET_TEAMS} teams "
            "before a bracket can be generated."
        )
    return None
