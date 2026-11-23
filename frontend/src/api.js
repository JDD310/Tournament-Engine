export const FORMAT_LABELS = {
  single_elimination: 'Single elimination',
}

export class ApiError extends Error {
  constructor(status, message, fieldErrors = {}) {
    super(message)
    this.status = status
    this.fieldErrors = fieldErrors
  }
}

async function request(path, { method = 'GET', body, adminToken } = {}) {
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (adminToken) headers['X-Admin-Token'] = adminToken

  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const data = await response.json().catch(() => null)

  if (!response.ok) {
    const fieldErrors = {}
    for (const err of data?.errors ?? []) fieldErrors[err.field] = err.message
    const message =
      typeof data?.detail === 'string' ? data.detail : 'Something went wrong. Please try again.'
    throw new ApiError(response.status, message, fieldErrors)
  }
  return data
}

export function createTournament(fields) {
  return request('/api/tournaments', { method: 'POST', body: fields })
}

export function getTournament(id) {
  return request(`/api/tournaments/${encodeURIComponent(id)}`)
}

export function getTournamentAsAdmin(id, adminToken) {
  return request(`/api/tournaments/${encodeURIComponent(id)}/admin`, { adminToken })
}

export function updateTournament(id, adminToken, fields) {
  return request(`/api/tournaments/${encodeURIComponent(id)}`, {
    method: 'PATCH',
    body: fields,
    adminToken,
  })
}

function teamsPath(id, suffix = '') {
  return `/api/tournaments/${encodeURIComponent(id)}/teams${suffix}`
}

// Resolves to { locked, teams }, with teams in seed order (unseeded last).
export function listTeams(id) {
  return request(teamsPath(id))
}

export function addTeam(id, adminToken, name) {
  return request(teamsPath(id), { method: 'POST', body: { name }, adminToken })
}

export function renameTeam(id, adminToken, teamId, name) {
  return request(teamsPath(id, `/${teamId}`), { method: 'PATCH', body: { name }, adminToken })
}

export function removeTeam(id, adminToken, teamId) {
  return request(teamsPath(id, `/${teamId}`), { method: 'DELETE', adminToken })
}

// teamIds: the seeded teams, top seed first. Teams left out become unseeded.
export function setSeeding(id, adminToken, teamIds) {
  return request(teamsPath(id, '/seeding'), {
    method: 'PUT',
    body: { team_ids: teamIds },
    adminToken,
  })
}

// Resolves to { generated, rounds }. rounds is empty until it is generated.
export function getBracket(id) {
  return request(`/api/tournaments/${encodeURIComponent(id)}/bracket`)
}

// Generates the single-elimination bracket and locks the team list.
export function generateBracket(id, adminToken) {
  return request(`/api/tournaments/${encodeURIComponent(id)}/bracket`, {
    method: 'POST',
    adminToken,
  })
}
