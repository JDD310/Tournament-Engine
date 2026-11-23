import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { jsonResponse, mockFetch, renderAt, TOURNAMENT } from '../test/helpers.jsx'

afterEach(() => vi.unstubAllGlobals())

describe('CreateTournamentPage', () => {
  it('shows required-field errors without calling the API', async () => {
    const fetchMock = mockFetch()
    renderAt('/')

    await userEvent.click(screen.getByRole('button', { name: 'Create tournament' }))

    expect(screen.getByText('Tournament name is required.')).toBeInTheDocument()
    expect(screen.getByText('Game is required.')).toBeInTheDocument()
    expect(screen.getByLabelText('Tournament name')).toHaveAttribute('aria-invalid', 'true')
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('creates the tournament and lands on the management page', async () => {
    const fetchMock = mockFetch(
      jsonResponse(201, {
        ...TOURNAMENT,
        admin_token: 'secret-token',
        admin_path: '/t/abc123/manage#token=secret-token',
      }),
      jsonResponse(200, TOURNAMENT),
    )
    renderAt('/')

    await userEvent.type(screen.getByLabelText('Tournament name'), 'Friday Night Smash')
    await userEvent.type(screen.getByLabelText('Game'), 'Super Smash Bros.')
    expect(screen.getByLabelText('Format')).toHaveValue('single_elimination')
    await userEvent.click(screen.getByRole('button', { name: 'Create tournament' }))

    expect(await screen.findByText('Manage tournament')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('Tournament created')

    const [createUrl, createInit] = fetchMock.mock.calls[0]
    expect(createUrl).toBe('/api/tournaments')
    expect(createInit.method).toBe('POST')
    expect(JSON.parse(createInit.body)).toEqual({
      name: 'Friday Night Smash',
      game: 'Super Smash Bros.',
      format: 'single_elimination',
    })
    const [adminUrl, adminInit] = fetchMock.mock.calls[1]
    expect(adminUrl).toBe('/api/tournaments/abc123/admin')
    expect(fetchMock.mock.calls.every(([url]) => !url.includes('secret-token'))).toBe(true)
    expect(adminInit.headers['X-Admin-Token']).toBe('secret-token')
  })

  it('shows field errors returned by the server', async () => {
    mockFetch(
      jsonResponse(422, {
        detail: 'Please fix the highlighted fields.',
        errors: [{ field: 'game', message: 'Game must be 100 characters or fewer.' }],
      }),
    )
    renderAt('/')

    await userEvent.type(screen.getByLabelText('Tournament name'), 'Cup')
    await userEvent.type(screen.getByLabelText('Game'), 'Chess')
    await userEvent.click(screen.getByRole('button', { name: 'Create tournament' }))

    expect(await screen.findByText('Game must be 100 characters or fewer.')).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Please fix the highlighted fields.')
  })
})
