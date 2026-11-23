import { useEffect, useState } from 'react'
import { generateBracket, getBracket } from '../api.js'
import BracketView from './BracketView.jsx'

// The organizer's bracket panel: a Generate Bracket button until the bracket
// exists, then the bracket itself. onGenerated runs after a successful
// generation (the team list is locked from then on).
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
          Seeded teams are placed by seed; unseeded teams follow them in the order they were
          added. Top seeds get any byes.
        </p>
        <button type="button" onClick={handleGenerate} disabled={busy}>
          {busy ? 'Generating...' : 'Generate Bracket'}
        </button>
      </>
    )
  } else {
    body = <BracketView bracket={bracket} />
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
