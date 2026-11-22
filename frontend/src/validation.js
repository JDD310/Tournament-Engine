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
