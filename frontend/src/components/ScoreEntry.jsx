import { useState } from 'react'
import { validateScores } from '../validation.js'

function ScoreField({ id, label, value, onChange, error }) {
  const errorId = `${id}-error`
  return (
    <div className="field score-field">
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        name={id}
        type="number"
        inputMode="numeric"
        min="0"
        step="1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-invalid={error ? 'true' : 'false'}
        aria-describedby={error ? errorId : undefined}
      />
      {error && (
        <p id={errorId} className="field-error">
          {error}
        </p>
      )}
    </div>
  )
}

const initial = (score) => (score === null || score === undefined ? '' : String(score))

// Report or edit one match's score (management page only). onSubmit(team1,
// team2) saves it and resolves to whether it worked; the form closes if so.
export default function ScoreEntry({ match, onSubmit }) {
  const [open, setOpen] = useState(false)
  const [values, setValues] = useState({ team1: '', team2: '' })
  const [errors, setErrors] = useState({})
  const [saving, setSaving] = useState(false)

  const team1 = match.team1.name
  const team2 = match.team2.name
  const reported = match.winner_id !== null
  const action = reported ? 'Edit score' : 'Report score'

  function start() {
    setValues({ team1: initial(match.team1_score), team2: initial(match.team2_score) })
    setErrors({})
    setOpen(true)
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const result = validateScores(values.team1, values.team2, team1, team2)
    setErrors(result.errors)
    if (Object.keys(result.errors).length > 0) return
    setSaving(true)
    let ok = false
    try {
      ok = await onSubmit(result.team1, result.team2)
    } finally {
      setSaving(false)
    }
    if (ok) setOpen(false)
  }

  if (!open) {
    return (
      <button
        type="button"
        className="secondary score-button"
        onClick={start}
        aria-label={`${action}: ${team1} vs ${team2}`}
      >
        {action}
      </button>
    )
  }

  const idBase = `score-${match.id}`
  return (
    <form
      className="score-form"
      onSubmit={handleSubmit}
      noValidate
      aria-label={`Score: ${team1} vs ${team2}`}
    >
      <ScoreField
        id={`${idBase}-team1`}
        label={team1}
        value={values.team1}
        onChange={(value) => setValues((prev) => ({ ...prev, team1: value }))}
        error={errors.team1}
      />
      <ScoreField
        id={`${idBase}-team2`}
        label={team2}
        value={values.team2}
        onChange={(value) => setValues((prev) => ({ ...prev, team2: value }))}
        error={errors.team2}
      />
      {errors.form && (
        <p role="alert" className="form-error">
          {errors.form}
        </p>
      )}
      <div className="score-actions">
        <button type="submit" disabled={saving}>
          {saving ? 'Saving...' : 'Save score'}
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() => setOpen(false)}
          disabled={saving}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}
