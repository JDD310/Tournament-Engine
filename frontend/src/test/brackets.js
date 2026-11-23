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
  team1_score: null,
  team2_score: null,
  ...extra,
})

export const SIX_TEAM_BRACKET = {
  generated: true,
  champion: null,
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

// SIX_TEAM_BRACKET with the matches in `results` reported. results maps a
// match ID to [team1Score, team2Score]; each winner is copied into the slot
// it feeds, the way the API does it. The final's winner becomes champion.
export function withResults(results) {
  const bracket = structuredClone(SIX_TEAM_BRACKET)
  const byId = new Map(bracket.rounds.flatMap((r) => r.matches).map((m) => [m.id, m]))
  for (const [id, [team1Score, team2Score]] of Object.entries(results)) {
    const m = byId.get(Number(id))
    const winner = team1Score > team2Score ? m.team1 : m.team2
    Object.assign(m, { team1_score: team1Score, team2_score: team2Score, winner_id: winner.id })
    if (m.next_match_id === null) bracket.champion = winner
    else byId.get(m.next_match_id)[`team${m.next_slot}`] = winner
  }
  return bracket
}
