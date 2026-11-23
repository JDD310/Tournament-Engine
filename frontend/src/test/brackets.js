// A 6-team bracket as the API returns it: seeds 1 and 2 have byes and are
// already in the semifinals.
const team = (id, name, seed) => ({ id, name, seed })
const S1 = team(1, 'Alpha', 1)
const S2 = team(2, 'Bravo', 2)
const S3 = team(3, 'Charlie', 3)
const S4 = team(4, 'Delta', 4)
const S5 = team(5, 'Echo', null)
const S6 = team(6, 'Foxtrot', null)

const match = (id, round, position, team1, team2, extra = {}) => ({
  id,
  round,
  position,
  team1,
  team2,
  winner_id: null,
  is_bye: false,
  next_match_id: null,
  next_slot: null,
  ...extra,
})

export const SIX_TEAM_BRACKET = {
  generated: true,
  rounds: [
    {
      round: 1,
      name: 'Quarterfinals',
      matches: [
        match(11, 1, 0, S1, null, { is_bye: true, winner_id: 1, next_match_id: 21, next_slot: 1 }),
        match(12, 1, 1, S4, S5, { next_match_id: 21, next_slot: 2 }),
        match(13, 1, 2, S2, null, { is_bye: true, winner_id: 2, next_match_id: 22, next_slot: 1 }),
        match(14, 1, 3, S3, S6, { next_match_id: 22, next_slot: 2 }),
      ],
    },
    {
      round: 2,
      name: 'Semifinals',
      matches: [
        match(21, 2, 0, S1, null, { next_match_id: 31, next_slot: 1 }),
        match(22, 2, 1, S2, null, { next_match_id: 31, next_slot: 2 }),
      ],
    },
    { round: 3, name: 'Final', matches: [match(31, 3, 0, null, null)] },
  ],
}
