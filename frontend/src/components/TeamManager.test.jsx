import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  jsonResponse,
  mockEveryFetch,
  mockFetch,
  renderAt,
  TOURNAMENT,
} from '../test/helpers.jsx'
import TeamManager from './TeamManager.jsx'

afterEach(() => vi.unstubAllGlobals())

const ALPHA = { id: 1, name: 'Alpha', seed: 1 }
const BRAVO = { id: 2, name: 'Bravo', seed: 2 }
const CHARLIE = { id: 3, name: 'Charlie', seed: null }

function teamList(teams, locked = false) {
  return jsonResponse(200, { locked, teams })
}

function renderManager() {
  return render(<TeamManager tournamentId="abc123" adminToken="secret-token" />)
}

function seededNames() {
  const list = screen.queryByRole('list', { name: /Seeded/ })
  if (!list) return []
  return within(list)
    .getAllByRole('listitem')
    .map((li) => li.querySelector('.team-name').textContent.trim())
}

function unseededNames() {
  const list = screen.queryByRole('list', { name: 'Unseeded' })
  if (!list) return []
  return within(list)
    .getAllByRole('listitem')
    .map((li) => li.querySelector('.team-name').textContent.trim())
}

function lastCall(fetchMock, offset = 1) {
  const calls = fetchMock.mock.calls
  const [url, init] = calls[calls.length - offset]
  return { url, method: init?.method ?? 'GET', init, body: init?.body && JSON.parse(init.body) }
}

describe('TeamManager', () => {
  it('lists seeded teams by seed, then unseeded teams', async () => {
    mockEveryFetch(teamList([ALPHA, BRAVO, CHARLIE]))
    renderManager()

    await screen.findByRole('heading', { name: 'Seeded (1 = top seed)' })
    expect(seededNames()).toEqual(['1. Alpha', '2. Bravo'])
    expect(unseededNames()).toEqual(['Charlie'])
    expect(screen.getByText('Unseeded teams are placed after the seeded ones.')).toBeInTheDocument()
    expect(screen.queryByText(/at least 2 teams/)).not.toBeInTheDocument()
  })

  it('says a bracket needs at least 2 teams', async () => {
    mockEveryFetch(teamList([CHARLIE]))
    renderManager()

    expect(
      await screen.findByText('Add at least 2 teams before the bracket can be generated.'),
    ).toBeInTheDocument()
  })

  it('shows an empty state', async () => {
    mockEveryFetch(teamList([]))
    renderManager()

    expect(await screen.findByText('No teams yet.')).toBeInTheDocument()
    expect(screen.getByText(/at least 2 teams/)).toBeInTheDocument()
  })

  it('adds a team with the organizer token', async () => {
    const fetchMock = mockEveryFetch(
      teamList([]),
      jsonResponse(201, { id: 3, name: 'Charlie', seed: null }),
      teamList([CHARLIE]),
    )
    renderManager()

    await userEvent.type(await screen.findByLabelText('Team name'), '  Charlie ')
    await userEvent.click(screen.getByRole('button', { name: 'Add team' }))

    expect(await screen.findByText('Charlie')).toBeInTheDocument()
    const post = lastCall(fetchMock, 2)
    expect(post.url).toBe('/api/tournaments/abc123/teams')
    expect(post.method).toBe('POST')
    expect(post.body).toEqual({ name: 'Charlie' })
    expect(post.init.headers['X-Admin-Token']).toBe('secret-token')
    expect(screen.getByLabelText('Team name')).toHaveValue('')
  })

  it.each(['alpha', '  ALPHA  ', 'Alpha'])(
    'rejects the duplicate name %j before sending it',
    async (name) => {
      const fetchMock = mockEveryFetch(teamList([ALPHA]))
      renderManager()

      await userEvent.type(await screen.findByLabelText('Team name'), name)
      await userEvent.click(screen.getByRole('button', { name: 'Add team' }))

      expect(
        screen.getByText(`A team named "${name.trim()}" is already in this tournament.`),
      ).toBeInTheDocument()
      expect(fetchMock).toHaveBeenCalledTimes(1)
    },
  )

  it('requires a team name', async () => {
    const fetchMock = mockEveryFetch(teamList([]))
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Add team' }))

    expect(screen.getByText('Team name is required.')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('shows a name conflict from the server on the field', async () => {
    mockEveryFetch(
      teamList([]),
      jsonResponse(409, { detail: 'A team named "Straße" is already in this tournament.' }),
      teamList([{ id: 9, name: 'Strasse', seed: null }]),
    )
    renderManager()

    await userEvent.type(await screen.findByLabelText('Team name'), 'Straße')
    await userEvent.click(screen.getByRole('button', { name: 'Add team' }))

    expect(
      await screen.findByText('A team named "Straße" is already in this tournament.'),
    ).toBeInTheDocument()
    expect(screen.getByLabelText('Team name')).toHaveValue('Straße')
  })

  it('moves a seed down', async () => {
    const fetchMock = mockEveryFetch(
      teamList([ALPHA, BRAVO, CHARLIE]),
      teamList([
        { ...BRAVO, seed: 1 },
        { ...ALPHA, seed: 2 },
        CHARLIE,
      ]),
    )
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Move Alpha down' }))

    await waitFor(() => expect(seededNames()).toEqual(['1. Bravo', '2. Alpha']))
    const put = lastCall(fetchMock)
    expect(put.url).toBe('/api/tournaments/abc123/teams/seeding')
    expect(put.method).toBe('PUT')
    expect(put.body).toEqual({ team_ids: [2, 1] })
    expect(put.init.headers['X-Admin-Token']).toBe('secret-token')
  })

  it('moves a seed up', async () => {
    const fetchMock = mockEveryFetch(teamList([ALPHA, BRAVO]), teamList([ALPHA, BRAVO]))
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Move Bravo up' }))

    expect(lastCall(fetchMock).body).toEqual({ team_ids: [2, 1] })
  })

  it('cannot move the top seed up or the last seed down', async () => {
    mockEveryFetch(teamList([ALPHA, BRAVO]))
    renderManager()

    expect(await screen.findByRole('button', { name: 'Move Alpha up' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Move Bravo down' })).toBeDisabled()
  })

  it('seeds an unseeded team after the current seeds', async () => {
    const fetchMock = mockEveryFetch(
      teamList([ALPHA, BRAVO, CHARLIE]),
      teamList([ALPHA, BRAVO, { ...CHARLIE, seed: 3 }]),
    )
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Seed Charlie next' }))

    expect(lastCall(fetchMock).body).toEqual({ team_ids: [1, 2, 3] })
    expect(await screen.findByText('3.')).toBeInTheDocument()
    expect(unseededNames()).toEqual([])
  })

  it('unseeds a team', async () => {
    const fetchMock = mockEveryFetch(
      teamList([ALPHA, BRAVO]),
      teamList([{ ...BRAVO, seed: 1 }, { ...ALPHA, seed: null }]),
    )
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Unseed Alpha' }))

    expect(lastCall(fetchMock).body).toEqual({ team_ids: [2] })
    expect(await screen.findByRole('list', { name: 'Unseeded' })).toBeInTheDocument()
    expect(seededNames()).toEqual(['1. Bravo'])
    expect(unseededNames()).toEqual(['Alpha'])
  })

  it('renames a team', async () => {
    const fetchMock = mockEveryFetch(
      teamList([ALPHA]),
      jsonResponse(200, { ...ALPHA, name: 'Alpha Squad' }),
      teamList([{ ...ALPHA, name: 'Alpha Squad' }]),
    )
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Rename Alpha' }))
    const input = screen.getByLabelText('New name for Alpha')
    await userEvent.clear(input)
    await userEvent.type(input, 'Alpha Squad')
    await userEvent.click(screen.getByRole('button', { name: 'Save name' }))

    expect(await screen.findByText('Alpha Squad')).toBeInTheDocument()
    const patch = lastCall(fetchMock, 2)
    expect(patch.url).toBe('/api/tournaments/abc123/teams/1')
    expect(patch.method).toBe('PATCH')
    expect(patch.body).toEqual({ name: 'Alpha Squad' })
  })

  it('lets a team change only the case of its own name', async () => {
    const fetchMock = mockEveryFetch(
      teamList([ALPHA]),
      jsonResponse(200, { ...ALPHA, name: 'ALPHA' }),
      teamList([{ ...ALPHA, name: 'ALPHA' }]),
    )
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Rename Alpha' }))
    const input = screen.getByLabelText('New name for Alpha')
    await userEvent.clear(input)
    await userEvent.type(input, 'ALPHA')
    await userEvent.click(screen.getByRole('button', { name: 'Save name' }))

    expect(await screen.findByText('ALPHA')).toBeInTheDocument()
    expect(lastCall(fetchMock, 2).method).toBe('PATCH')
  })

  it("won't rename a team to another team's name", async () => {
    const fetchMock = mockEveryFetch(teamList([ALPHA, BRAVO]))
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Rename Bravo' }))
    const input = screen.getByLabelText('New name for Bravo')
    await userEvent.clear(input)
    await userEvent.type(input, 'alpha')
    await userEvent.click(screen.getByRole('button', { name: 'Save name' }))

    expect(
      screen.getByText('A team named "alpha" is already in this tournament.'),
    ).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('cancels a rename', async () => {
    const fetchMock = mockEveryFetch(teamList([ALPHA]))
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Rename Alpha' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('New name for Alpha')).not.toBeInTheDocument()
    expect(seededNames()).toEqual(['1. Alpha'])
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('removes a team from the middle of the seeds and shows the renumbered list', async () => {
    const fetchMock = mockEveryFetch(
      teamList([ALPHA, BRAVO, { ...CHARLIE, seed: 3 }]),
      jsonResponse(204, null),
      teamList([ALPHA, { ...CHARLIE, seed: 2 }]),
    )
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Remove Bravo' }))

    await waitFor(() => expect(seededNames()).toEqual(['1. Alpha', '2. Charlie']))
    const del = lastCall(fetchMock, 2)
    expect(del.url).toBe('/api/tournaments/abc123/teams/2')
    expect(del.method).toBe('DELETE')
    expect(del.init.headers['X-Admin-Token']).toBe('secret-token')
  })

  it('hides every control once the list is locked', async () => {
    mockEveryFetch(teamList([ALPHA, BRAVO, CHARLIE], true))
    renderManager()

    expect(
      await screen.findByText('The bracket has been generated, so the team list is locked.'),
    ).toBeInTheDocument()
    expect(seededNames()).toEqual(['1. Alpha', '2. Bravo'])
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByLabelText('Team name')).not.toBeInTheDocument()
  })

  it('locks the list when the server says the bracket was generated', async () => {
    mockEveryFetch(
      teamList([ALPHA, BRAVO]),
      jsonResponse(409, {
        detail: 'The bracket has been generated, so the teams can no longer be changed.',
      }),
      teamList([ALPHA, BRAVO], true),
    )
    renderManager()

    await userEvent.click(await screen.findByRole('button', { name: 'Remove Alpha' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('can no longer be changed')
    expect(await screen.findByText(/team list is locked/)).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows an error if the teams fail to load', async () => {
    mockEveryFetch(jsonResponse(404, { detail: 'Tournament not found.' }))
    renderManager()

    expect(await screen.findByRole('alert')).toHaveTextContent('Tournament not found.')
  })
})

describe('ManageTournamentPage team panel', () => {
  it('loads the teams once the organizer link is verified', async () => {
    // The token is in both the query string and the fragment so this test
    // passes whichever way the page reads it (PR #3 moves it to the fragment).
    const fetchMock = mockFetch(jsonResponse(200, TOURNAMENT))
    const teamFetch = vi.fn(async () => teamList([ALPHA, CHARLIE]))
    const pageFetch = globalThis.fetch
    vi.stubGlobal('fetch', (url, init) =>
      url.endsWith('/teams') ? teamFetch(url, init) : pageFetch(url, init),
    )
    renderAt('/t/abc123/manage?token=secret-token#token=secret-token')

    expect(await screen.findByRole('heading', { name: 'Teams' })).toBeInTheDocument()
    expect(await screen.findByText('Charlie')).toBeInTheDocument()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(teamFetch).toHaveBeenCalledWith('/api/tournaments/abc123/teams', expect.anything())
  })
})
