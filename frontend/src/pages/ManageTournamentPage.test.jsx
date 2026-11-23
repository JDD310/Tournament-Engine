import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SIX_TEAM_BRACKET } from '../test/brackets.js'
import { jsonResponse, mockFetch, NO_BRACKET, renderAt, TOURNAMENT } from '../test/helpers.jsx'

afterEach(() => vi.unstubAllGlobals())

describe('ManageTournamentPage', () => {
  it('shows the tournament with its organizer and public links', async () => {
    mockFetch(jsonResponse(200, TOURNAMENT))
    renderAt('/t/abc123/manage#token=secret-token')

    expect(await screen.findByRole('heading', { name: 'Friday Night Smash' })).toBeInTheDocument()
    expect(screen.getByText(/Single elimination/)).toBeInTheDocument()
    expect(screen.getByTestId('admin-url')).toHaveTextContent(
      '/t/abc123/manage#token=secret-token',
    )
    expect(screen.getByTestId('public-url')).toHaveTextContent('/t/abc123')
  })

  it('sends the token only in the X-Admin-Token header', async () => {
    const fetchMock = mockFetch(jsonResponse(200, TOURNAMENT))
    renderAt('/t/abc123/manage#token=secret-token')

    await screen.findByRole('heading', { name: 'Friday Night Smash' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/tournaments/abc123/admin')
    expect(url).not.toContain('secret-token')
    expect(init.headers['X-Admin-Token']).toBe('secret-token')
  })

  it('does not accept the old query-string link', async () => {
    const fetchMock = mockFetch()
    renderAt('/t/abc123/manage?token=secret-token')

    expect(await screen.findByRole('alert')).toHaveTextContent('missing its access token')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('refuses to load without a token', async () => {
    const fetchMock = mockFetch()
    renderAt('/t/abc123/manage')

    expect(await screen.findByRole('alert')).toHaveTextContent('missing its access token')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('shows the server error for an invalid token', async () => {
    mockFetch(
      jsonResponse(403, {
        detail: 'A valid organizer link is required to manage this tournament.',
      }),
    )
    renderAt('/t/abc123/manage#token=wrong')

    expect(await screen.findByRole('alert')).toHaveTextContent('valid organizer link is required')
  })

  it('saves edits with the organizer token', async () => {
    const fetchMock = mockFetch(
      jsonResponse(200, TOURNAMENT),
      jsonResponse(200, { ...TOURNAMENT, name: 'Renamed Cup' }),
    )
    renderAt('/t/abc123/manage#token=secret-token')

    const nameInput = await screen.findByLabelText('Tournament name')
    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'Renamed Cup')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('heading', { name: 'Renamed Cup' })).toBeInTheDocument()
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/tournaments/abc123')
    expect(url).not.toContain('secret-token')
    expect(init.method).toBe('PATCH')
    expect(init.headers['X-Admin-Token']).toBe('secret-token')
  })

  it('validates edits before saving', async () => {
    const fetchMock = mockFetch(jsonResponse(200, TOURNAMENT))
    renderAt('/t/abc123/manage#token=secret-token')

    await userEvent.clear(await screen.findByLabelText('Game'))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(screen.getByText('Game is required.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('ManageTournamentPage bracket', () => {
  it('reloads the team list as locked after generating the bracket', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const teams = [
      { id: 1, name: 'Alpha', seed: 1 },
      { id: 2, name: 'Bravo', seed: 2 },
    ]
    let generated = false
    const fetchMock = vi.fn(async (url, init) => {
      const method = init?.method ?? 'GET'
      if (url === '/api/tournaments/abc123/admin') return jsonResponse(200, TOURNAMENT)
      if (url === '/api/tournaments/abc123/teams') {
        return jsonResponse(200, { locked: generated, teams })
      }
      if (url === '/api/tournaments/abc123/bracket' && method === 'POST') {
        generated = true
        return jsonResponse(201, SIX_TEAM_BRACKET)
      }
      if (url === '/api/tournaments/abc123/bracket') return jsonResponse(200, NO_BRACKET)
      throw new Error(`unexpected ${method} ${url}`)
    })
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/t/abc123/manage#token=secret-token')

    await userEvent.click(await screen.findByRole('button', { name: 'Generate Bracket' }))

    expect(
      await screen.findByText('The bracket has been generated, so the team list is locked.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add team' })).not.toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Final' })).toBeInTheDocument()
  })
})
