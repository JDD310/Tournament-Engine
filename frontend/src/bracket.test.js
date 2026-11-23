import { describe, expect, it } from 'vitest'
import { canReport } from './bracket.js'
import { SIX_TEAM_BRACKET, withResults } from './test/brackets.js'

describe('canReport', () => {
  const matches = (bracket) =>
    new Map(bracket.rounds.flatMap((r) => r.matches).map((m) => [m.id, m]))
  const find = (bracket, id) => matches(bracket).get(id)

  it('refuses byes and matches still waiting for a team', () => {
    const all = matches(SIX_TEAM_BRACKET)
    expect(canReport(find(SIX_TEAM_BRACKET, 11), all)).toBe(false) // bye
    expect(canReport(find(SIX_TEAM_BRACKET, 21), all)).toBe(false) // Alpha v TBD
    expect(canReport(find(SIX_TEAM_BRACKET, 12), all)).toBe(true)
  })

  it('allows a correction only until the next match is played', () => {
    const reported = withResults({ 12: [1, 3] })
    expect(canReport(find(reported, 12), matches(reported))).toBe(true)
    const nextPlayed = withResults({ 12: [1, 3], 21: [2, 0] })
    expect(canReport(find(nextPlayed, 12), matches(nextPlayed))).toBe(false)
  })
})
