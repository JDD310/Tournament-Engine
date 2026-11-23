export const MAX_LENGTH = 100

function requiredText(value, label) {
  const trimmed = value.trim()
  if (!trimmed) return `${label} is required.`
  if (trimmed.length > MAX_LENGTH) return `${label} must be ${MAX_LENGTH} characters or fewer.`
  return null
}

// Mirrors the backend rules so most mistakes are caught before submitting.
export function validateTournament({ name, game, format }) {
  const errors = {}
  const nameError = requiredText(name, 'Tournament name')
  if (nameError) errors.name = nameError
  const gameError = requiredText(game, 'Game')
  if (gameError) errors.game = gameError
  if (format !== undefined && !format) errors.format = 'Format is required.'
  return errors
}

// Same comparison as the backend: ignores case, surrounding whitespace and
// repeated inner whitespace. The server has the final say (it also folds
// characters like "ß"), so this only catches the common cases early.
export function teamNameKey(name) {
  return name.trim().split(/\s+/).join(' ').toLowerCase()
}

export function validateTeamName(name, teams, ownId = null) {
  const error = requiredText(name, 'Team name')
  if (error) return error
  const key = teamNameKey(name)
  if (teams.some((team) => team.id !== ownId && teamNameKey(team.name) === key)) {
    return `A team named "${name.trim()}" is already in this tournament.`
  }
  return null
}
