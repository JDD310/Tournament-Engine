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

// Mirror MAX_SCORE in backend/app/schemas.py.
export const MAX_SCORE = 999999

function scoreError(value, label) {
  const trimmed = String(value).trim()
  if (!trimmed) return `${label} is required.`
  if (/^-\d+$/.test(trimmed)) return `${label} can't be negative.`
  if (!/^\d+$/.test(trimmed)) return `${label} must be a whole number.`
  if (Number(trimmed) > MAX_SCORE) {
    return `${label} must be ${MAX_SCORE.toLocaleString('en-US')} or less.`
  }
  return null
}

// Scores for an elimination match: whole numbers, 0 or more, and not a tie.
// Returns { errors, team1, team2 }: errors has team1/team2/form messages; the
// scores are numbers when there are no errors.
export function validateScores(team1Value, team2Value, team1Label, team2Label) {
  const errors = {}
  const team1Error = scoreError(team1Value, `${team1Label}'s score`)
  if (team1Error) errors.team1 = team1Error
  const team2Error = scoreError(team2Value, `${team2Label}'s score`)
  if (team2Error) errors.team2 = team2Error
  const team1 = Number(String(team1Value).trim())
  const team2 = Number(String(team2Value).trim())
  if (!team1Error && !team2Error && team1 === team2) {
    errors.form = "Elimination matches can't end in a tie. Enter the score that decided the winner."
  }
  return { errors, team1, team2 }
}
