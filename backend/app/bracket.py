"""Single-elimination bracket planning (TE-6).

Pure functions with no database access, so the seeding and bye rules can be
unit tested directly. ``routers/bracket.py`` saves the plan as ``Match`` rows.

Rules:

* Entrants are given in seed order: index 0 is seed 1. The caller decides that
  order; the API uses ``teams.seed_order`` (seeded teams by seed, then unseeded
  teams in the order they were added), so unseeded teams take the seeds after
  the last seeded team.
* The bracket has room for the next power of two at or above the team count.
  The missing seeds at the bottom are byes.
* Standard seeding placement: in round 1, seed ``s`` meets seed
  ``size + 1 - s``, and the pairs are ordered so the top two seeds can only
  meet in the final, the top four only in the semifinals, and so on
  (1v8, 4v5, 2v7, 3v6 for 8 teams).
* Because the missing seeds are the bottom ones, the byes go to the top seeds,
  and two byes never meet each other.
* A bye is a first-round match with no second team, already won by the first
  team, who is placed in their round-2 match straight away.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Generic, TypeVar

from app.teams import MIN_BRACKET_TEAMS

T = TypeVar("T")


@dataclass
class PlannedMatch(Generic[T]):
    round: int  # 1 is the first round; the last round is the final.
    position: int  # 0-based, top to bottom within the round.
    team1: T | None = None
    team2: T | None = None
    winner: T | None = None
    is_bye: bool = False
    # Where the winner goes: (round, position) and slot 1 (team1) or 2 (team2).
    # None for the final.
    next: tuple[int, int] | None = None
    next_slot: int | None = None


def bracket_size(team_count: int) -> int:
    """The number of first-round slots: the smallest power of two that fits."""
    size = 2
    while size < team_count:
        size *= 2
    return size


def round_count(team_count: int) -> int:
    return bracket_size(team_count).bit_length() - 1


def seed_positions(size: int) -> list[int]:
    """Seeds in bracket order, top to bottom, for a bracket of ``size`` slots.

    Slots 2k and 2k+1 meet in round 1. Built by doubling: every seed ``s`` in
    the bracket of half the size is replaced by the pair ``s, size + 1 - s``.
    Each pair adds up to ``size + 1`` and the lower seed always comes first.
    """
    if size < 2 or size & (size - 1):
        raise ValueError("Bracket size must be a power of two, at least 2.")
    order = [1]
    while len(order) < size:
        total = len(order) * 2 + 1
        order = [s for seed in order for s in (seed, total - seed)]
    return order


def round_name(round_number: int, rounds: int) -> str:
    from_end = rounds - round_number
    if from_end == 0:
        return "Final"
    if from_end == 1:
        return "Semifinals"
    if from_end == 2:
        return "Quarterfinals"
    return f"Round {round_number}"


def plan_bracket(entrants: Sequence[T]) -> list[list[PlannedMatch[T]]]:
    """Every match of the bracket, round by round (round 1 first).

    ``entrants`` must be in seed order and unique.
    """
    if len(entrants) < MIN_BRACKET_TEAMS:
        raise ValueError(f"A bracket needs at least {MIN_BRACKET_TEAMS} teams.")
    size = bracket_size(len(entrants))
    rounds = round_count(len(entrants))

    plan: list[list[PlannedMatch[T]]] = []
    for round_number in range(1, rounds + 1):
        matches = []
        for position in range(size >> round_number):
            match = PlannedMatch[T](round=round_number, position=position)
            if round_number < rounds:
                match.next = (round_number + 1, position // 2)
                match.next_slot = 1 if position % 2 == 0 else 2
            matches.append(match)
        plan.append(matches)

    by_seed = dict(enumerate(entrants, start=1))
    order = seed_positions(size)
    for match in plan[0]:
        top, bottom = order[2 * match.position], order[2 * match.position + 1]
        match.team1 = by_seed[top]  # The top seed of a pair always exists.
        match.team2 = by_seed.get(bottom)
        if match.team2 is None:
            match.is_bye = True
            match.winner = match.team1
            _advance(plan, match)
    return plan


def _advance(plan: list[list[PlannedMatch[T]]], match: PlannedMatch[T]) -> None:
    """Put ``match``'s winner into the slot it feeds."""
    round_number, position = match.next
    target = plan[round_number - 1][position]
    if match.next_slot == 1:
        target.team1 = match.winner
    else:
        target.team2 = match.winner
