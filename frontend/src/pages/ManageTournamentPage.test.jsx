import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse, mockFetch, renderAt, TOURNAMENT } from '../test/helpers.jsx'

afterEach(() => vi.unstubAllGlobals())

describe('ManageTournamentPage', () => {
  it('shows the tournament with its organizer and public links', async () => {
    mockFetch(jsonResponse(200, TOURNAMENT))
    renderAt('/t/abc123/manage?token=secret-token')

    expect(await screen.findByRole('heading', { name: 'Friday Night Smash' })).toBeInTheDocument()
    expect(screen.getByText(/Single elimination/)).toBeInTheDocument()
    expect(screen.getByTestId('admin-url')).toHaveTextContent(
      '/t/abc123/manage?token=secret-token',
    )
    expect(screen.getByTestId('public-url')).toHaveTextContent('/t/abc123')
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
    renderAt('/t/abc123/manage?token=wrong')

    expect(await screen.findByRole('alert')).toHaveTextContent('valid organizer link is required')
  })

  it('saves edits with the organizer token', async () => {
    const fetchMock = mockFetch(
      jsonResponse(200, TOURNAMENT),
      jsonResponse(200, { ...TOURNAMENT, name: 'Renamed Cup' }),
    )
    renderAt('/t/abc123/manage?token=secret-token')

    const nameInput = await screen.findByLabelText('Tournament name')
    await userEvent.clear(nameInput)
    await userEvent.type(nameInput, 'Renamed Cup')
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(await screen.findByRole('heading', { name: 'Renamed Cup' })).toBeInTheDocument()
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/tournaments/abc123')
    expect(init.method).toBe('PATCH')
    expect(init.headers['X-Admin-Token']).toBe('secret-token')
  })

  it('validates edits before saving', async () => {
    const fetchMock = mockFetch(jsonResponse(200, TOURNAMENT))
    renderAt('/t/abc123/manage?token=secret-token')

    await userEvent.clear(await screen.findByLabelText('Game'))
    await userEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    expect(screen.getByText('Game is required.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
