"""Unit tests for single-elimination bracket planning (TE-25, TE-27).

Entrants are plain seed numbers here (entrant ``s`` is seed ``s``), so each
pairing reads as "seed vs seed".
"""

import pytest

from app.bracket import (
    bracket_size,
    plan_bracket,
    round_count,
    round_name,
    seed_positions,
)
from app.teams import MAX_TEAMS


def plan_for(team_count):
    return plan_bracket(list(range(1, team_count + 1)))


def pairings(round_):
    return [(m.team1, m.team2) for m in round_]


def check_structure(plan, team_count):
    """Shape and wiring that must hold for every bracket size."""
    size = bracket_size(team_count)
    rounds = len(plan)
    assert rounds == round_count(team_count) == size.bit_length() - 1
    assert [len(r) for r in plan] == [size >> r for r in range(1, rounds + 1)]
    for number, round_ in enumerate(plan, start=1):
        assert [(m.round, m.position) for m in round_] == [
            (number, p) for p in range(len(round_))
        ]

    # Every winner feeds exactly one later match; the final feeds none.
    final = plan[-1]
    assert len(final) == 1
    assert final[0].next is None and final[0].next_slot is None
    fed = {}
    for round_ in plan[:-1]:
        for match in round_:
            assert match.next == (match.round + 1, match.position // 2)
            assert match.next_slot in (1, 2)
            key = (*match.next, match.next_slot)
            assert key not in fed, f"two matches feed {key}"
            fed[key] = match
    # ...and every slot after round 1 is fed by exactly one match.
    assert set(fed) == {
        (m.round, m.position, slot) for r in plan[1:] for m in r for slot in (1, 2)
    }

    # Every team plays round 1 exactly once (as a team or as a bye).
    first = plan[0]
    entered = [t for m in first for t in (m.team1, m.team2) if t is not None]
    assert sorted(entered) == list(range(1, team_count + 1))

    # Byes: the top seeds, one per bye, already won and already advanced.
    byes = [m for m in first if m.is_bye]
    assert sorted(m.team1 for m in byes) == list(range(1, size - team_count + 1))
    for match in first:
        if match.is_bye:
            assert match.team2 is None and match.winner == match.team1
            target = plan[1][match.next[1]] if rounds > 1 else None
            slot = target.team1 if match.next_slot == 1 else target.team2
            assert slot == match.team1
        else:
            assert match.team1 is not None and match.team2 is not None
            assert match.winner is None
            assert match.team1 < match.team2

    # Later rounds only hold teams that got there by a bye.
    for round_ in plan[1:]:
        for match in round_:
            for slot, team in ((1, match.team1), (2, match.team2)):
                if team is not None:
                    feeder = fed[(match.round, match.position, slot)]
                    assert feeder.is_bye and feeder.winner == team
            assert match.winner is None and not match.is_bye


def check_top_seeds_meet_late(plan, team_count):
    """The top 2^k seeds are spread one per block, so they meet as late as
    possible: seeds 1 and 2 only in the final, the top 4 only in the semis..."""
    size = bracket_size(team_count)
    slot_of = {}
    for match in plan[0]:
        slot_of[match.team1] = 2 * match.position
        if match.team2 is not None:
            slot_of[match.team2] = 2 * match.position + 1
    k = 2
    while k <= team_count:
        block = size // k
        blocks = [slot_of[seed] // block for seed in range(1, k + 1)]
        assert sorted(blocks) == list(range(k)), f"top {k} seeds share a block"
        k *= 2


# --- Seed placement -------------------------------------------------------


@pytest.mark.parametrize(
    "size, expected",
    [
        (2, [1, 2]),
        (4, [1, 4, 2, 3]),
        (8, [1, 8, 4, 5, 2, 7, 3, 6]),
        (16, [1, 16, 8, 9, 4, 13, 5, 12, 2, 15, 7, 10, 3, 14, 6, 11]),
    ],
)
def test_seed_positions(size, expected):
    assert seed_positions(size) == expected


@pytest.mark.parametrize("size", [0, 1, 3, 6, 12])
def test_seed_positions_rejects_non_powers_of_two(size):
    with pytest.raises(ValueError):
        seed_positions(size)


@pytest.mark.parametrize(
    "teams, size", [(2, 2), (3, 4), (4, 4), (5, 8), (8, 8), (9, 16), (256, 256)]
)
def test_bracket_size(teams, size):
    assert bracket_size(teams) == size


def test_round_names():
    assert [round_name(r, 4) for r in range(1, 5)] == [
        "Round 1",
        "Quarterfinals",
        "Semifinals",
        "Final",
    ]
    assert round_name(1, 1) == "Final"


@pytest.mark.parametrize("count", [0, 1])
def test_fewer_than_two_teams_is_rejected(count):
    with pytest.raises(ValueError):
        plan_for(count)


# --- The sizes TE-27 asks for: 4, 6, 8, 16 --------------------------------


def test_4_teams():
    plan = plan_for(4)
    check_structure(plan, 4)
    assert pairings(plan[0]) == [(1, 4), (2, 3)]
    assert pairings(plan[1]) == [(None, None)]
    assert not any(m.is_bye for m in plan[0])


def test_6_teams_gives_byes_to_seeds_1_and_2():
    plan = plan_for(6)
    check_structure(plan, 6)
    assert pairings(plan[0]) == [(1, None), (4, 5), (2, None), (3, 6)]
    assert [m.is_bye for m in plan[0]] == [True, False, True, False]
    # The bye winners are already in the semifinals, waiting for an opponent.
    assert pairings(plan[1]) == [(1, None), (2, None)]
    assert pairings(plan[2]) == [(None, None)]


def test_8_teams():
    plan = plan_for(8)
    check_structure(plan, 8)
    assert pairings(plan[0]) == [(1, 8), (4, 5), (2, 7), (3, 6)]
    assert len(plan) == 3


def test_16_teams():
    plan = plan_for(16)
    check_structure(plan, 16)
    assert pairings(plan[0]) == [
        (1, 16),
        (8, 9),
        (4, 13),
        (5, 12),
        (2, 15),
        (7, 10),
        (3, 14),
        (6, 11),
    ]
    assert len(plan) == 4


# --- Other sizes ----------------------------------------------------------


def test_2_teams_is_just_a_final():
    plan = plan_for(2)
    check_structure(plan, 2)
    assert len(plan) == 1
    assert pairings(plan[0]) == [(1, 2)]


def test_3_teams_gives_seed_1_a_bye_to_the_final():
    plan = plan_for(3)
    check_structure(plan, 3)
    assert pairings(plan[0]) == [(1, None), (2, 3)]
    assert pairings(plan[1]) == [(1, None)]


def test_5_teams():
    plan = plan_for(5)
    check_structure(plan, 5)
    assert pairings(plan[0]) == [(1, None), (4, 5), (2, None), (3, None)]
    # Seeds 2 and 3 both had byes, so their semifinal is already set.
    assert pairings(plan[1]) == [(1, None), (2, 3)]


def test_7_teams():
    plan = plan_for(7)
    check_structure(plan, 7)
    assert pairings(plan[0]) == [(1, None), (4, 5), (2, 7), (3, 6)]
    assert pairings(plan[1]) == [(1, None), (None, None)]


def test_256_teams():
    plan = plan_for(MAX_TEAMS)
    check_structure(plan, MAX_TEAMS)
    check_top_seeds_meet_late(plan, MAX_TEAMS)
    assert len(plan) == 8
    assert sum(len(r) for r in plan) == 255
    assert pairings(plan[0])[:2] == [(1, 256), (128, 129)]
    assert not any(m.is_bye for m in plan[0])


@pytest.mark.parametrize("count", range(2, MAX_TEAMS + 1))
def test_every_size_up_to_the_team_cap(count):
    plan = plan_for(count)
    check_structure(plan, count)
    check_top_seeds_meet_late(plan, count)


def test_entrants_can_be_any_value():
    plan = plan_bracket(["Alpha", "Bravo", "Charlie"])
    assert pairings(plan[0]) == [("Alpha", None), ("Bravo", "Charlie")]
    assert plan[1][0].team1 == "Alpha"
