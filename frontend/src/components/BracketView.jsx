// Read-only single-elimination bracket: one column per round, left to right
// (first round to final). Used by the public page and the management page.
//
// bracket: { generated, rounds: [{ round, name, matches: [match] }] } as
// returned by GET /api/tournaments/{id}/bracket.

function TeamLine({ team, isWinner, placeholder }) {
  if (!team) {
    return <li className="bracket-team bracket-team-empty">{placeholder}</li>
  }
  return (
    <li className={isWinner ? 'bracket-team bracket-team-winner' : 'bracket-team'}>
      {team.seed !== null && <span className="bracket-seed">{team.seed}</span>}
      <span className="bracket-team-name">{team.name}</span>
      {isWinner && <span className="visually-hidden"> (advances)</span>}
    </li>
  )
}

function MatchCard({ match, label }) {
  const winner = (team) => team !== null && match.winner_id === team.id
  return (
    <li className={match.is_bye ? 'bracket-match bracket-match-bye' : 'bracket-match'}>
      <ul className="bracket-teams" aria-label={label}>
        <TeamLine team={match.team1} isWinner={winner(match.team1)} placeholder="TBD" />
        <TeamLine
          team={match.team2}
          isWinner={winner(match.team2)}
          placeholder={match.is_bye ? 'Bye' : 'TBD'}
        />
      </ul>
    </li>
  )
}

export default function BracketView({ bracket }) {
  if (!bracket?.generated) return null
  return (
    <div className="bracket" data-testid="bracket">
      {bracket.rounds.map((round) => {
        const headingId = `bracket-round-${round.round}`
        return (
          <section key={round.round} className="bracket-round" aria-labelledby={headingId}>
            <h3 id={headingId}>{round.name}</h3>
            <ol className="bracket-matches">
              {round.matches.map((match, index) => (
                <MatchCard
                  key={match.id}
                  match={match}
                  label={`${round.name}, match ${index + 1}`}
                />
              ))}
            </ol>
          </section>
        )
      })}
    </div>
  )
}
