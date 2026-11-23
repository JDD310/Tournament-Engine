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
export const NO_BRACKET = { generated: false, rounds: [] }

function panelResponse(url, init) {
  if ((init?.method ?? 'GET') !== 'GET') return null
  if (/^\/api\/tournaments\/[^/]+\/teams$/.test(url)) return EMPTY_TEAMS
  if (/^\/api\/tournaments\/[^/]+\/bracket$/.test(url)) return NO_BRACKET
  return null
}

// Queue fetch responses in call order. The pages also load their team list
// and bracket; those GETs get an empty list / no bracket and are left out of
// the returned mock, so page tests don't depend on the panels' requests. Use
// mockEveryFetch to queue (and record) those requests too.
export function mockFetch(...responses) {
  const fetchMock = vi.fn()
  for (const r of responses) fetchMock.mockResolvedValueOnce(r)
  vi.stubGlobal('fetch', (url, init) => {
    const panel = panelResponse(url, init)
    return panel ? Promise.resolve(jsonResponse(200, panel)) : fetchMock(url, init)
  })
  return fetchMock
}

// Queue fetch responses in call order, panel requests included.
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
