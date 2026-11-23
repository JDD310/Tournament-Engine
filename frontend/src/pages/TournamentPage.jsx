import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { ApiError, FORMAT_LABELS, getPublicView, STATUS_LABELS } from '../api.js'
import BracketView from '../components/BracketView.jsx'
import NotFoundPage from './NotFoundPage.jsx'

const UNKNOWN_STATUS_LABEL = 'Unavailable'

// Public, read-only tournament page for spectators: the details, the status,
// and the bracket with scores (or, before it is generated, the teams so far).
// It never shows edit controls; organizers manage from /t/:id/manage.
export default function TournamentPage() {
  const { id } = useParams()
  const [view, setView] = useState(null)
  // 'not-found' for a 404; 'failed' for a network or server error.
  const [error, setError] = useState(null)
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    let cancelled = false
    getPublicView(id)
      .then((data) => !cancelled && setView(data))
      .catch((err) => {
        if (cancelled) return
        setError(err instanceof ApiError && err.status === 404 ? 'not-found' : 'failed')
      })
    return () => {
      cancelled = true
    }
  }, [id, attempt])

  if (error === 'not-found') return <NotFoundPage />
  if (error === 'failed') {
    return (
      <main>
        <h1>Couldn't load this tournament</h1>
        <p role="alert" className="form-error">
          Something went wrong on our side or with the connection. Please try again in a moment.
        </p>
        <button
          type="button"
          onClick={() => {
            setError(null)
            setAttempt((n) => n + 1)
          }}
        >
          Try again
        </button>
      </main>
    )
  }
  if (!view) {
    return (
      <main>
        <p>Loading...</p>
      </main>
    )
  }

  const { tournament, teams, bracket } = view
  // A status this page doesn't know yet (added to the API later) gets a
  // neutral label and badge rather than its raw value.
  const knownStatus = Object.hasOwn(STATUS_LABELS, tournament.status)
  return (
    <main>
      <h1>{tournament.name}</h1>
      <p className="tournament-meta">
        {tournament.game} &middot; {FORMAT_LABELS[tournament.format] ?? tournament.format}
      </p>
      <p className="tournament-status">
        Status:{' '}
        <span
          className={`status-badge status-${knownStatus ? tournament.status : 'unknown'}`}
          data-testid="status"
        >
          {knownStatus ? STATUS_LABELS[tournament.status] : UNKNOWN_STATUS_LABEL}
        </span>
      </p>
      <section aria-labelledby="bracket-heading">
        <h2 id="bracket-heading">Bracket</h2>
        {bracket.generated ? (
          <BracketView bracket={bracket} />
        ) : (
          <>
            <p className="muted">The bracket hasn't been generated yet.</p>
            <TeamsSoFar teams={teams.teams} />
          </>
        )}
      </section>
    </main>
  )
}

function TeamsSoFar({ teams }) {
  if (teams.length === 0) return <p className="muted">No teams have joined yet.</p>
  return (
    <>
      <h3>Teams ({teams.length})</h3>
      <ol className="team-list public-team-list" aria-label="Teams">
        {teams.map((team) => (
          <li key={team.id} className="team-row">
            <span>
              {team.seed !== null && <span className="team-seed">{team.seed}</span>} {team.name}
            </span>
          </li>
        ))}
      </ol>
    </>
  )
}
