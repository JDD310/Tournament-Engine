import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createTournament, FORMAT_LABELS } from '../api.js'
import TextField from '../components/TextField.jsx'
import { validateTournament } from '../validation.js'

export default function CreateTournamentPage() {
  const navigate = useNavigate()
  const [fields, setFields] = useState({ name: '', game: '', format: 'single_elimination' })
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  const setField = (key) => (value) => setFields((prev) => ({ ...prev, [key]: value }))

  async function handleSubmit(event) {
    event.preventDefault()
    setFormError(null)
    const clientErrors = validateTournament(fields)
    setErrors(clientErrors)
    if (Object.keys(clientErrors).length > 0) return

    setSubmitting(true)
    try {
      const created = await createTournament(fields)
      navigate(created.admin_path, { state: { justCreated: true } })
    } catch (err) {
      setErrors(err.fieldErrors ?? {})
      setFormError(err.message)
      setSubmitting(false)
    }
  }

  return (
    <main>
      <h1>Create a tournament</h1>
      <form onSubmit={handleSubmit} noValidate>
        <TextField
          id="name"
          label="Tournament name"
          value={fields.name}
          onChange={setField('name')}
          error={errors.name}
        />
        <TextField
          id="game"
          label="Game"
          value={fields.game}
          onChange={setField('game')}
          error={errors.game}
        />
        <div className="field">
          <label htmlFor="format">Format</label>
          <select
            id="format"
            name="format"
            value={fields.format}
            onChange={(e) => setField('format')(e.target.value)}
            aria-invalid={errors.format ? 'true' : 'false'}
            aria-describedby={errors.format ? 'format-error' : undefined}
          >
            {Object.entries(FORMAT_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {errors.format && (
            <p id="format-error" className="field-error">
              {errors.format}
            </p>
          )}
        </div>
        {formError && (
          <p role="alert" className="form-error">
            {formError}
          </p>
        )}
        <button type="submit" disabled={submitting}>
          {submitting ? 'Creating...' : 'Create tournament'}
        </button>
      </form>
    </main>
  )
}
