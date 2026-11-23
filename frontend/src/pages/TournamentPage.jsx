import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { FORMAT_LABELS, getTournament } from '../api.js'

// Minimal public page so the tournament's public URL resolves. The live
// bracket view is built in later stories.
export default function TournamentPage() {
  const { id } = useParams()
  const [tournament, setTournament] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false
    getTournament(id)
      .then((data) => !cancelled && setTournament(data))
      .catch((err) => !cancelled && setError(err.message))
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
  return (
    <main>
      <h1>{tournament.name}</h1>
      <p>
        {tournament.game} &middot; {FORMAT_LABELS[tournament.format] ?? tournament.format}
      </p>
    </main>
  )
}
