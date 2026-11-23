import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import { AppRoutes } from '../App.jsx'

export function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <AppRoutes />
    </MemoryRouter>,
  )
}

export function jsonResponse(status, body) {
  return { ok: status >= 200 && status < 300, status, json: async () => body }
}

export const EMPTY_TEAMS = { locked: false, teams: [] }

function isTeamListRequest(url, init) {
  return (init?.method ?? 'GET') === 'GET' && /^\/api\/tournaments\/[^/]+\/teams$/.test(url)
}

// Queue fetch responses in call order. The management page also loads its
// team list; those GETs get an empty list and are left out of the returned
// mock, so page tests don't depend on the team panel's requests. Use
// mockEveryFetch to queue (and record) the team requests too.
export function mockFetch(...responses) {
  const fetchMock = vi.fn()
  for (const r of responses) fetchMock.mockResolvedValueOnce(r)
  vi.stubGlobal('fetch', (url, init) =>
    isTeamListRequest(url, init)
      ? Promise.resolve(jsonResponse(200, EMPTY_TEAMS))
      : fetchMock(url, init),
  )
  return fetchMock
}

// Queue fetch responses in call order, team list requests included.
export function mockEveryFetch(...responses) {
  const fetchMock = vi.fn()
  for (const r of responses) fetchMock.mockResolvedValueOnce(r)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export const TOURNAMENT = {
  id: 'abc123',
  name: 'Friday Night Smash',
  game: 'Super Smash Bros.',
  format: 'single_elimination',
  created_at: '2026-11-22T12:00:00Z',
  public_path: '/t/abc123',
}
