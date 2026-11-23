// Single-elimination bracket: one column per round, left to right (first
// round to final), with reported scores and, once the final is reported, the
// champion. Used by the public page and the management page.
//
// bracket: { generated, rounds: [{ round, name, matches: [match] }], champion }
// as returned by GET /api/tournaments/{id}/bracket.
// renderMatchActions(match): optional; its result is shown under each match.
// Only the management page passes it, so the public bracket stays read-only.

function TeamLine({ team, isWinner, placeholder, score }) {
  if (!team) {
    return <li className="bracket-team bracket-team-empty">{placeholder}</li>
  }
  return (
    <li className={isWinner ? 'bracket-team bracket-team-winner' : 'bracket-team'}>
      {team.seed !== null && <span className="bracket-seed">{team.seed}</span>}
      <span className="bracket-team-name">{team.name}</span>
      {score !== null && score !== undefined && <span className="bracket-score">{score}</span>}
      {isWinner && <span className="visually-hidden"> (advances)</span>}
    </li>
  )
}

function MatchCard({ match, label, actions }) {
  const winner = (team) => team !== null && match.winner_id === team.id
  return (
    <li className={match.is_bye ? 'bracket-match bracket-match-bye' : 'bracket-match'}>
      <ul className="bracket-teams" aria-label={label}>
        <TeamLine
          team={match.team1}
          isWinner={winner(match.team1)}
          placeholder="TBD"
          score={match.team1_score}
        />
        <TeamLine
          team={match.team2}
          isWinner={winner(match.team2)}
          placeholder={match.is_bye ? 'Bye' : 'TBD'}
          score={match.team2_score}
        />
      </ul>
      {actions}
    </li>
  )
}

export default function BracketView({ bracket, renderMatchActions }) {
  if (!bracket?.generated) return null
  return (
    <>
      {bracket.champion && (
        <p className="champion" data-testid="champion">
          Tournament complete. Champion: <strong>{bracket.champion.name}</strong>
        </p>
      )}
      {bracket.rounds.length > 1 && (
        <p className="bracket-hint muted">Scroll sideways to see every round.</p>
      )}
      {/* The rounds scroll sideways inside this box, not the whole page. It is
          focusable so keyboard users can scroll it too. */}
      <div
        className="bracket"
        data-testid="bracket"
        role="region"
        aria-label="Bracket rounds"
        tabIndex={0}
      >
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
                    actions={renderMatchActions?.(match)}
                  />
                ))}
              </ol>
            </section>
          )
        })}
      </div>
    </>
  )
}
