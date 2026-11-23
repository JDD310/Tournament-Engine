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
