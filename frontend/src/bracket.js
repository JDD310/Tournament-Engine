// Whether the organizer can report (or correct) this match: both teams are
// known, it isn't a bye, and the next match hasn't been played. The server
// checks the same rules; this only decides where to show the button.
export function canReport(match, matchesById) {
  if (match.is_bye || !match.team1 || !match.team2) return false
  const next = match.next_match_id === null ? null : matchesById.get(match.next_match_id)
  return !next || next.winner_id === null
}
