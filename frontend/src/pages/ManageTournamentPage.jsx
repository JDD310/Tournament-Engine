import { useEffect, useState } from 'react'
import { useLocation, useParams } from 'react-router-dom'
import { FORMAT_LABELS, getTournamentAsAdmin, updateTournament } from '../api.js'
import TeamManager from '../components/TeamManager.jsx'
import TextField from '../components/TextField.jsx'
import { validateTournament } from '../validation.js'

export default function ManageTournamentPage() {
  const { id } = useParams()
  const location = useLocation()
  // The organizer link is /t/{id}/manage#token=... The fragment is never sent
  // to the server; the token only leaves the browser in the X-Admin-Token header.
  const token = new URLSearchParams(location.hash.slice(1)).get('token')

  const [tournament, setTournament] = useState(null)
  const [fetchError, setFetchError] = useState(null)
  const [fields, setFields] = useState({ name: '', game: '' })
  const [errors, setErrors] = useState({})
  const [saveMessage, setSaveMessage] = useState(null)
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    getTournamentAsAdmin(id, token)
      .then((data) => {
        if (cancelled) return
        setTournament(data)
        setFields({ name: data.name, game: data.game })
      })
      .catch((err) => !cancelled && setFetchError(err.message))
    return () => {
      cancelled = true
    }
  }, [id, token])

  async function handleSave(event) {
    event.preventDefault()
    setSaveMessage(null)
    const clientErrors = validateTournament(fields)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length > 0) return

    setSaving(true)
    try {
      const updated = await updateTournament(id, token, fields)
      setTournament(updated)
      setSaveMessage('Changes saved.')
    } catch (err) {
      setErrors(err.fieldErrors ?? {})
      setSaveMessage(err.message)
    } finally {
      setSaving(false)
    }
  }

  const loadError = token ? fetchError : 'This organizer link is missing its access token.'
  if (loadError) {
    return (
      <main>
        <h1>Can't open this tournament</h1>
        <p role="alert" className="form-error">
          {loadError}
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

  const origin = window.location.origin
  const adminUrl = `${origin}${location.pathname}${location.hash}`
  const publicUrl = `${origin}${tournament.public_path}`

  return (
    <main>
      <p className="muted">Manage tournament</p>
      <h1>{tournament.name}</h1>
      <p>
        {tournament.game} &middot; {FORMAT_LABELS[tournament.format] ?? tournament.format}
      </p>

      {location.state?.justCreated && (
        <p className="notice" role="status">
          Tournament created. Save your organizer link below: it is the only way to manage this
          tournament.
        </p>
      )}

      <h2>Links</h2>
      <p>
        <strong>Organizer link (keep private)</strong>
        <br />
        <span className="link-value" data-testid="admin-url">
          {adminUrl}
        </span>
      </p>
      <p>
        <strong>Public link</strong>
        <br />
        <a className="link-value" href={publicUrl} data-testid="public-url">
          {publicUrl}
        </a>
      </p>

      <h2>Details</h2>
      <form onSubmit={handleSave} noValidate>
        <TextField
          id="name"
          label="Tournament name"
          value={fields.name}
          onChange={(value) => setFields((prev) => ({ ...prev, name: value }))}
          error={errors.name}
        />
        <TextField
          id="game"
          label="Game"
          value={fields.game}
          onChange={(value) => setFields((prev) => ({ ...prev, game: value }))}
          error={errors.game}
        />
        {saveMessage && <p role="status">{saveMessage}</p>}
        <button type="submit" disabled={saving}>
          {saving ? 'Saving...' : 'Save changes'}
        </button>
      </form>

      <TeamManager tournamentId={id} adminToken={token} />
    </main>
  )
}
