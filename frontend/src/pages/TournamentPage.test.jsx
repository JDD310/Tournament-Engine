import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SIX_TEAM_BRACKET, withResults } from '../test/brackets.js'
import { jsonResponse, mockEveryFetch, NO_BRACKET, renderAt, TOURNAMENT } from '../test/helpers.jsx'

afterEach(() => vi.unstubAllGlobals())

const TEAMS = {
  locked: false,
  teams: [
    { id: 1, name: 'Alpha', seed: 1 },
    { id: 2, name: 'Bravo', seed: null },
  ],
}
const LOCKED_TEAMS = { ...TEAMS, locked: true }
const COMPLETE = withResults({ 12: [1, 3], 14: [2, 0], 21: [2, 1], 22: [0, 2], 31: [4, 2] })

function publicView({ status = 'setting_up', teams = TEAMS, bracket = NO_BRACKET } = {}) {
  return {
    tournament: {
      ...TOURNAMENT,
      status,
      completed_at: status === 'complete' ? '2026-11-22T18:00:00Z' : null,
    },
    teams,
    bracket,
  }
}

function respondWith(...responses) {
  return mockEveryFetch(...responses.map((body) => jsonResponse(200, body)))
}

function scoreOf(match, teamName) {
  return (
    match.getByText(teamName).closest('li').querySelector('.bracket-score')?.textContent ?? null
  )
}

function expectNoEditControls() {
  // The public page's only button is "Try again", and only on a load error.
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument()
  expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
  expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
  for (const name of [/report/i, /edit score/i, /score/i, /generate/i, /remove/i, /rename/i]) {
    expect(screen.queryByRole('button', { name })).not.toBeInTheDocument()
  }
  expect(screen.queryByRole('link', { name: /manage/i })).not.toBeInTheDocument()
}

describe('TournamentPage', () => {
  it('loads everything from the public view, without an organizer token', async () => {
    const fetchMock = respondWith(publicView())
    renderAt('/t/abc123')

    await screen.findByRole('heading', { name: 'Friday Night Smash' })
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/tournaments/abc123/public')
    expect(init?.headers?.['X-Admin-Token']).toBeUndefined()
  })

  it('shows the name, game, format and status', async () => {
    respondWith(
      publicView({ status: 'in_progress', teams: LOCKED_TEAMS, bracket: SIX_TEAM_BRACKET }),
    )
    renderAt('/t/abc123')

    expect(await screen.findByRole('heading', { name: 'Friday Night Smash' })).toBeInTheDocument()
    expect(screen.getByText('Super Smash Bros. · Single elimination')).toBeInTheDocument()
    expect(screen.getByTestId('status')).toHaveTextContent('In progress')
  })

  it('shows Setting up and the teams so far before the bracket exists', async () => {
    respondWith(publicView())
    renderAt('/t/abc123')

    expect(await screen.findByTestId('status')).toHaveTextContent('Setting up')
    expect(screen.getByText("The bracket hasn't been generated yet.")).toBeInTheDocument()
    const teams = within(screen.getByRole('list', { name: 'Teams' }))
    expect(teams.getAllByRole('listitem').map((li) => li.textContent.trim())).toEqual([
      '1 Alpha',
      'Bravo',
    ])
    expect(screen.queryByTestId('bracket')).not.toBeInTheDocument()
    expectNoEditControls()
  })

  it('says when no teams have joined yet', async () => {
    respondWith(publicView({ teams: { locked: false, teams: [] } }))
    renderAt('/t/abc123')

    expect(await screen.findByText('No teams have joined yet.')).toBeInTheDocument()
  })

  it('shows the full bracket with scores while in progress', async () => {
    const partly = withResults({ 12: [1, 3], 14: [2, 0] })
    respondWith(publicView({ status: 'in_progress', teams: LOCKED_TEAMS, bracket: partly }))
    renderAt('/t/abc123')

    expect(await screen.findByTestId('status')).toHaveTextContent('In progress')
    for (const round of ['Quarterfinals', 'Semifinals', 'Final']) {
      expect(screen.getByRole('heading', { name: round })).toBeInTheDocument()
    }
    const qf2 = within(screen.getByRole('list', { name: 'Quarterfinals, match 2' }))
    expect(scoreOf(qf2, 'Delta')).toBe('1')
    expect(scoreOf(qf2, 'Echo')).toBe('3')
    // Unreported matches show no score.
    expect(
      scoreOf(within(screen.getByRole('list', { name: 'Semifinals, match 1' })), 'Alpha'),
    ).toBe(null)
    expect(screen.queryByTestId('champion')).not.toBeInTheDocument()
    expectNoEditControls()
  })

  it('shows Complete, every score and the champion', async () => {
    respondWith(publicView({ status: 'complete', teams: LOCKED_TEAMS, bracket: COMPLETE }))
    renderAt('/t/abc123')

    expect(await screen.findByTestId('status')).toHaveTextContent('Complete')
    expect(screen.getByTestId('champion')).toHaveTextContent('Champion: Alpha')
    const final = within(screen.getByRole('list', { name: 'Final, match 1' }))
    expect(scoreOf(final, 'Alpha')).toBe('4')
    expect(scoreOf(final, 'Charlie')).toBe('2')
    expectNoEditControls()
  })

  it.each(['on_hold', 'constructor'])(
    'shows a neutral label for a status it does not know (%s)',
    async (status) => {
      respondWith(publicView({ status }))
      renderAt('/t/abc123')

      const badge = await screen.findByTestId('status')
      expect(badge).toHaveTextContent(/^Unavailable$/)
      expect(badge).toHaveClass('status-badge', 'status-unknown')
      expect(screen.queryByText(status, { exact: false })).not.toBeInTheDocument()
    },
  )

  it('puts the bracket in its own sideways-scrolling region', async () => {
    respondWith(
      publicView({ status: 'in_progress', teams: LOCKED_TEAMS, bracket: SIX_TEAM_BRACKET }),
    )
    renderAt('/t/abc123')

    const region = await screen.findByRole('region', { name: 'Bracket rounds' })
    expect(region).toHaveClass('bracket')
    expect(region).toHaveAttribute('tabindex', '0')
    expect(screen.getByText('Scroll sideways to see every round.')).toBeInTheDocument()
  })

  it('shows the not-found page for an unknown tournament', async () => {
    mockEveryFetch(jsonResponse(404, { detail: 'Tournament not found.' }))
    renderAt('/t/nope')

    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Go to the home page' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
  })

  it.each([
    ['a server error', () => jsonResponse(500, { detail: 'Internal Server Error' })],
    ['a server error with no JSON body', () => jsonResponse(502, null)],
  ])('shows a retryable error, not "not found", for %s', async (_, response) => {
    mockEveryFetch(response(), jsonResponse(200, publicView()))
    renderAt('/t/abc123')

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
    expect(screen.queryByRole('heading', { name: 'Page not found' })).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Try again' }))
    expect(await screen.findByRole('heading', { name: 'Friday Night Smash' })).toBeInTheDocument()
  })

  it('shows a retryable error when the network fails', async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', fetchMock)
    renderAt('/t/abc123')

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong')
    expect(screen.queryByRole('heading', { name: 'Page not found' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
  })
})
