import { screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SIX_TEAM_BRACKET } from '../test/brackets.js'
import { jsonResponse, mockEveryFetch, NO_BRACKET, renderAt, TOURNAMENT } from '../test/helpers.jsx'

afterEach(() => vi.unstubAllGlobals())

function respondTo(routes) {
  const fetchMock = vi.fn((url) => Promise.resolve(routes[url]))
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('TournamentPage', () => {
  it('shows the bracket once generated', async () => {
    const fetchMock = respondTo({
      '/api/tournaments/abc123': jsonResponse(200, TOURNAMENT),
      '/api/tournaments/abc123/bracket': jsonResponse(200, SIX_TEAM_BRACKET),
    })
    renderAt('/t/abc123')

    expect(await screen.findByRole('heading', { name: 'Final' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Friday Night Smash' })).toBeInTheDocument()
    expect(screen.getByText('Echo')).toBeInTheDocument()
    // Public: no organizer token is sent.
    for (const [, init] of fetchMock.mock.calls) {
      expect(init?.headers?.['X-Admin-Token']).toBeUndefined()
    }
  })

  it('says when the bracket has not been generated', async () => {
    respondTo({
      '/api/tournaments/abc123': jsonResponse(200, TOURNAMENT),
      '/api/tournaments/abc123/bracket': jsonResponse(200, NO_BRACKET),
    })
    renderAt('/t/abc123')

    expect(
      await screen.findByText("The bracket hasn't been generated yet."),
    ).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Generate Bracket' })).not.toBeInTheDocument()
  })

  it('shows an unknown tournament error', async () => {
    mockEveryFetch(
      jsonResponse(404, { detail: 'Tournament not found.' }),
      jsonResponse(404, { detail: 'Tournament not found.' }),
    )
    renderAt('/t/nope')

    expect(await screen.findByRole('alert')).toHaveTextContent('Tournament not found.')
  })
})
