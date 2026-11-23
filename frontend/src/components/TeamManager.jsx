import { useEffect, useState } from 'react'
import { addTeam, listTeams, removeTeam, renameTeam, setSeeding } from '../api.js'
import { validateTeamName } from '../validation.js'
import TextField from './TextField.jsx'

// Mirrors MIN_BRACKET_TEAMS in backend/app/teams.py.
export const MIN_BRACKET_TEAMS = 2

// The organizer's team list: add, rename, remove and seed teams. Seeded teams
// (1 = top seed) are listed first; unseeded teams follow in the order added.
export default function TeamManager({ tournamentId, adminToken }) {
  const [teams, setTeams] = useState(null)
  const [locked, setLocked] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [newName, setNewName] = useState('')
  const [addError, setAddError] = useState(null)
  const [editing, setEditing] = useState(null) // { id, name, error }
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  function applyList(data) {
    setTeams(data.teams)
    setLocked(data.locked)
  }

  useEffect(() => {
    let cancelled = false
    listTeams(tournamentId)
      .then((data) => {
        if (cancelled) return
        setTeams(data.teams)
        setLocked(data.locked)
      })
      .catch((err) => !cancelled && setLoadError(err.message))
    return () => {
      cancelled = true
    }
  }, [tournamentId])

  // Runs one change, then shows the server's current list (even after an
  // error, so a lock or a change from another tab shows up). Returns whether
  // the change succeeded.
  async function run(action, onError = (err) => setMessage(err.message)) {
    setBusy(true)
    setMessage(null)
    let ok = false
    let list = null
    try {
      list = await action()
      ok = true
    } catch (err) {
      onError(err)
    }
    try {
      applyList(list?.teams ? list : await listTeams(tournamentId))
    } catch (err) {
      setMessage(err.message)
    }
    setBusy(false)
    return ok
  }

  async function handleAdd(event) {
    event.preventDefault()
    const error = validateTeamName(newName, teams)
    setAddError(error)
    if (error) return
    const ok = await run(
      () => addTeam(tournamentId, adminToken, newName.trim()),
      (err) => setAddError(err.fieldErrors?.name ?? err.message),
    )
    if (ok) setNewName('')
  }

  async function handleRename(event) {
    event.preventDefault()
    const error = validateTeamName(editing.name, teams, editing.id)
    if (error) {
      setEditing({ ...editing, error })
      return
    }
    const ok = await run(
      () => renameTeam(tournamentId, adminToken, editing.id, editing.name.trim()),
      (err) => setEditing((prev) => ({ ...prev, error: err.fieldErrors?.name ?? err.message })),
    )
    if (ok) setEditing(null)
  }

  function handleRemove(team) {
    if (editing?.id === team.id) setEditing(null)
    run(() => removeTeam(tournamentId, adminToken, team.id))
  }

  function reseed(teamIds) {
    run(() => setSeeding(tournamentId, adminToken, teamIds))
  }

  if (loadError) {
    return (
      <section aria-labelledby="teams-heading">
        <h2 id="teams-heading">Teams</h2>
        <p role="alert" className="form-error">
          {loadError}
        </p>
      </section>
    )
  }

  if (!teams) {
    return (
      <section aria-labelledby="teams-heading">
        <h2 id="teams-heading">Teams</h2>
        <p>Loading teams...</p>
      </section>
    )
  }

  const seeded = teams.filter((team) => team.seed !== null)
  const unseeded = teams.filter((team) => team.seed === null)
  const seedIds = seeded.map((team) => team.id)

  function moveSeed(index, delta) {
    const ids = [...seedIds]
    ;[ids[index], ids[index + delta]] = [ids[index + delta], ids[index]]
    reseed(ids)
  }

  function renderTeam(team, actions) {
    if (editing?.id === team.id) {
      return (
        <li key={team.id}>
          <form className="team-rename" onSubmit={handleRename} noValidate>
            <TextField
              id={`rename-${team.id}`}
              label={`New name for ${team.name}`}
              value={editing.name}
              onChange={(value) => setEditing((prev) => ({ ...prev, name: value }))}
              error={editing.error}
            />
            <div className="team-actions">
              <button type="submit" disabled={busy}>
                Save name
              </button>
              <button type="button" className="secondary" onClick={() => setEditing(null)}>
                Cancel
              </button>
            </div>
          </form>
        </li>
      )
    }
    return (
      <li key={team.id} className="team-row">
        <span className="team-name">
          {team.seed !== null && <span className="team-seed">{team.seed}.</span>} {team.name}
        </span>
        {!locked && (
          <span className="team-actions">
            {actions}
            <button
              type="button"
              className="secondary"
              disabled={busy}
              aria-label={`Rename ${team.name}`}
              onClick={() => setEditing({ id: team.id, name: team.name, error: null })}
            >
              Rename
            </button>
            <button
              type="button"
              className="secondary"
              disabled={busy}
              aria-label={`Remove ${team.name}`}
              onClick={() => handleRemove(team)}
            >
              Remove
            </button>
          </span>
        )}
      </li>
    )
  }

  function actionButton(label, ariaLabel, onClick, disabled = false) {
    return (
      <button
        type="button"
        className="secondary"
        disabled={busy || disabled}
        aria-label={ariaLabel}
        onClick={onClick}
      >
        {label}
      </button>
    )
  }

  return (
    <section aria-labelledby="teams-heading">
      <h2 id="teams-heading">Teams</h2>

      {locked ? (
        <p className="notice" role="status">
          The bracket has been generated, so the team list is locked.
        </p>
      ) : (
        teams.length < MIN_BRACKET_TEAMS && (
          <p className="muted">
            Add at least {MIN_BRACKET_TEAMS} teams before the bracket can be generated.
          </p>
        )
      )}

      {message && (
        <p role="alert" className="form-error">
          {message}
        </p>
      )}

      {teams.length === 0 && <p>No teams yet.</p>}

      {seeded.length > 0 && (
        <>
          <h3 id="seeded-heading">Seeded (1 = top seed)</h3>
          <ol aria-labelledby="seeded-heading" className="team-list">
            {seeded.map((team, index) =>
              renderTeam(
                team,
                <>
                  {actionButton('Up', `Move ${team.name} up`, () => moveSeed(index, -1), index === 0)}
                  {actionButton(
                    'Down',
                    `Move ${team.name} down`,
                    () => moveSeed(index, 1),
                    index === seeded.length - 1,
                  )}
                  {actionButton('Unseed', `Unseed ${team.name}`, () =>
                    reseed(seedIds.filter((id) => id !== team.id)),
                  )}
                </>,
              ),
            )}
          </ol>
        </>
      )}

      {unseeded.length > 0 && (
        <>
          <h3 id="unseeded-heading">Unseeded</h3>
          <p className="muted">Unseeded teams are placed after the seeded ones.</p>
          <ul aria-labelledby="unseeded-heading" className="team-list">
            {unseeded.map((team) =>
              renderTeam(
                team,
                actionButton('Seed', `Seed ${team.name} next`, () =>
                  reseed([...seedIds, team.id]),
                ),
              ),
            )}
          </ul>
        </>
      )}

      {!locked && (
        <form onSubmit={handleAdd} noValidate>
          <TextField
            id="team-name"
            label="Team name"
            value={newName}
            onChange={setNewName}
            error={addError}
          />
          <button type="submit" disabled={busy}>
            Add team
          </button>
        </form>
      )}
    </section>
  )
}
