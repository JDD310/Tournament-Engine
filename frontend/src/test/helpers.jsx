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

// Queue fetch responses in call order.
export function mockFetch(...responses) {
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
