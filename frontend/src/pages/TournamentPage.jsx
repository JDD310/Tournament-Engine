import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FORMAT_LABELS, getBracket, getTournament } from '../api.js'
import BracketView from '../components/BracketView.jsx'

// Public tournament page: the details and, once generated, the bracket.
export default function TournamentPage() {
  const { id } = useParams()
  const [tournament, setTournament] = useState(null)
  const [error, setError] = useState(null)
  const [bracket, setBracket] = useState(null)
  const [bracketError, setBracketError] = useState(null)

  useEffect(() => {
    let cancelled = false
    getTournament(id)
      .then((data) => !cancelled && setTournament(data))
      .catch((err) => !cancelled && setError(err.message))
    getBracket(id)
      .then((data) => !cancelled && setBracket(data))
      .catch((err) => !cancelled && setBracketError(err.message))
    return () => {
      cancelled = true
    }
  }, [id])

  if (error) {
    return (
      <main>
        <p role="alert" className="form-error">
          {error}
        </p>
      </main>
    )
  }
  if (!tournament) {
    return (
      <main>
        <p>Loading...</p>
      </main>
    )
  }

  let bracketBody
  if (bracketError) {
    bracketBody = (
      <p role="alert" className="form-error">
        {bracketError}
      </p>
    )
  } else if (!bracket) {
    bracketBody = <p>Loading bracket...</p>
  } else if (!bracket.generated) {
    bracketBody = <p className="muted">The bracket hasn't been generated yet.</p>
  } else {
    bracketBody = <BracketView bracket={bracket} />
  }

  return (
    <main>
      <h1>{tournament.name}</h1>
      <p>
        {tournament.game} &middot; {FORMAT_LABELS[tournament.format] ?? tournament.format}
      </p>
      <section aria-labelledby="bracket-heading">
        <h2 id="bracket-heading">Bracket</h2>
        {bracketBody}
      </section>
    </main>
  )
}
