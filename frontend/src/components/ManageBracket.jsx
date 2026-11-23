import { useEffect, useState } from 'react'
import { generateBracket, getBracket, reportScore } from '../api.js'
import { canReport } from '../bracket.js'
import BracketView from './BracketView.jsx'
import ScoreEntry from './ScoreEntry.jsx'

// The organizer's bracket panel: a Generate Bracket button until the bracket
// exists, then the bracket with score entry on each match that can be
// reported. onGenerated runs after a successful generation (the team list is
// locked from then on).
export default function ManageBracket({ tournamentId, adminToken, onGenerated }) {
  const [bracket, setBracket] = useState(null)
  const [loadError, setLoadError] = useState(null)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let cancelled = false
    getBracket(tournamentId)
      .then((data) => !cancelled && setBracket(data))
      .catch((err) => !cancelled && setLoadError(err.message))
    return () => {
      cancelled = true
    }
  }, [tournamentId])

  async function handleGenerate() {
    const question =
      'Generate the bracket from the current seeding? The team list will be locked ' +
      'and the bracket cannot be regenerated.'
    if (!window.confirm(question)) return
    setBusy(true)
    setMessage(null)
    try {
      setBracket(await generateBracket(tournamentId, adminToken))
      onGenerated?.()
    } catch (err) {
      setMessage(err.message)
      // Another tab may have generated it already; show what the server has.
      if (err.status === 409) {
        try {
          const latest = await getBracket(tournamentId)
          setBracket(latest)
          if (latest.generated) onGenerated?.()
        } catch {
          // Keep the original message.
        }
      }
    } finally {
      setBusy(false)
    }
  }

  // Resolves to whether the score was saved. After a refusal the bracket is
  // reloaded, in case another tab changed it (e.g. played the next match).
  async function handleReport(match, team1Score, team2Score) {
    setMessage(null)
    try {
      setBracket(await reportScore(tournamentId, adminToken, match.id, team1Score, team2Score))
      return true
    } catch (err) {
      setMessage(err.message)
      if (err.status === 404 || err.status === 409) {
        try {
          setBracket(await getBracket(tournamentId))
        } catch {
          // Keep the original message.
        }
      }
      return false
    }
  }

  let body
  if (loadError) {
    body = (
      <p role="alert" className="form-error">
        {loadError}
      </p>
    )
  } else if (!bracket) {
    body = <p>Loading bracket...</p>
  } else if (!bracket.generated) {
    body = (
      <>
        <p className="muted">
          Seeded teams are placed by seed; unseeded teams follow them in the order they were added.
          Top seeds get any byes.
        </p>
        <button type="button" onClick={handleGenerate} disabled={busy}>
          {busy ? 'Generating...' : 'Generate Bracket'}
        </button>
      </>
    )
  } else {
    const matchesById = new Map(bracket.rounds.flatMap((r) => r.matches).map((m) => [m.id, m]))
    body = (
      <BracketView
        bracket={bracket}
        renderMatchActions={(match) =>
          canReport(match, matchesById) && (
            <ScoreEntry
              key={`${match.id}-${match.team1.id}-${match.team2.id}`}
              match={match}
              onSubmit={(team1, team2) => handleReport(match, team1, team2)}
            />
          )
        }
      />
    )
  }

  return (
    <section aria-labelledby="bracket-heading">
      <h2 id="bracket-heading">Bracket</h2>
      {message && (
        <p role="alert" className="form-error">
          {message}
        </p>
      )}
      {body}
    </section>
  )
}
