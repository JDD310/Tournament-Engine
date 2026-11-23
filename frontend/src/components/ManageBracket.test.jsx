import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SIX_TEAM_BRACKET, withResults } from '../test/brackets.js'
import { jsonResponse, mockEveryFetch, NO_BRACKET } from '../test/helpers.jsx'
import ManageBracket from './ManageBracket.jsx'

afterEach(() => vi.unstubAllGlobals())

function renderPanel(onGenerated = vi.fn()) {
  render(
    <ManageBracket tournamentId="abc123" adminToken="secret-token" onGenerated={onGenerated} />,
  )
  return onGenerated
}

describe('ManageBracket', () => {
  it('generates the bracket with the organizer token after confirming', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const fetchMock = mockEveryFetch(
      jsonResponse(200, NO_BRACKET),
      jsonResponse(201, SIX_TEAM_BRACKET),
    )
    const onGenerated = renderPanel()

    await userEvent.click(await screen.findByRole('button', { name: 'Generate Bracket' }))

    expect(await screen.findByRole('heading', { name: 'Final' })).toBeInTheDocument()
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/tournaments/abc123/bracket')
    expect(init.method).toBe('POST')
    expect(init.headers['X-Admin-Token']).toBe('secret-token')
    expect(onGenerated).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('button', { name: 'Generate Bracket' })).not.toBeInTheDocument()
  })

  it('does nothing if the organizer cancels', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const fetchMock = mockEveryFetch(jsonResponse(200, NO_BRACKET))
    const onGenerated = renderPanel()

    await userEvent.click(await screen.findByRole('button', { name: 'Generate Bracket' }))

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(onGenerated).not.toHaveBeenCalled()
  })

  it('shows the reason generation was refused', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockEveryFetch(
      jsonResponse(200, NO_BRACKET),
      jsonResponse(409, {
        detail: 'A tournament needs at least 2 teams before a bracket can be generated.',
      }),
      jsonResponse(200, NO_BRACKET),
    )
    const onGenerated = renderPanel()

    await userEvent.click(await screen.findByRole('button', { name: 'Generate Bracket' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('at least 2 teams')
    expect(screen.getByRole('button', { name: 'Generate Bracket' })).toBeEnabled()
    expect(onGenerated).not.toHaveBeenCalled()
  })

  it('shows the bracket if it was generated elsewhere in the meantime', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    mockEveryFetch(
      jsonResponse(200, NO_BRACKET),
      jsonResponse(409, { detail: 'The bracket has already been generated.' }),
      jsonResponse(200, SIX_TEAM_BRACKET),
    )
    const onGenerated = renderPanel()

    await userEvent.click(await screen.findByRole('button', { name: 'Generate Bracket' }))

    expect(await screen.findByRole('heading', { name: 'Final' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('already been generated')
    expect(onGenerated).toHaveBeenCalledTimes(1)
  })

  it('shows an existing bracket without a generate button', async () => {
    mockEveryFetch(jsonResponse(200, SIX_TEAM_BRACKET))
    renderPanel()

    expect(await screen.findByRole('heading', { name: 'Semifinals' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Generate Bracket' })).not.toBeInTheDocument()
  })

  it('offers score entry only on matches with both teams known', async () => {
    mockEveryFetch(jsonResponse(200, SIX_TEAM_BRACKET))
    renderPanel()

    await screen.findByRole('heading', { name: 'Final' })
    const buttons = screen.getAllByRole('button', { name: /^Report score/ })
    expect(buttons.map((b) => b.getAttribute('aria-label'))).toEqual([
      'Report score: Delta vs Echo',
      'Report score: Charlie vs Foxtrot',
    ])
  })

  it('reports a score with the organizer token and shows the winner advancing', async () => {
    const fetchMock = mockEveryFetch(
      jsonResponse(200, SIX_TEAM_BRACKET),
      jsonResponse(200, withResults({ 12: [1, 3] })),
    )
    renderPanel()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Report score: Delta vs Echo' }),
    )
    await userEvent.type(screen.getByLabelText('Delta'), '1')
    await userEvent.type(screen.getByLabelText('Echo'), '3')
    await userEvent.click(screen.getByRole('button', { name: 'Save score' }))

    expect(
      await screen.findByRole('button', { name: 'Report score: Alpha vs Echo' }),
    ).toBeInTheDocument()
    const [url, init] = fetchMock.mock.calls[1]
    expect(url).toBe('/api/tournaments/abc123/matches/12/score')
    expect(init.method).toBe('PUT')
    expect(init.headers['X-Admin-Token']).toBe('secret-token')
    expect(JSON.parse(init.body)).toEqual({ team1_score: 1, team2_score: 3 })
    expect(screen.getByRole('button', { name: 'Edit score: Delta vs Echo' })).toBeInTheDocument()
  })

  it('does not send a tie to the server', async () => {
    const fetchMock = mockEveryFetch(jsonResponse(200, SIX_TEAM_BRACKET))
    renderPanel()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Report score: Delta vs Echo' }),
    )
    await userEvent.type(screen.getByLabelText('Delta'), '2')
    await userEvent.type(screen.getByLabelText('Echo'), '2')
    await userEvent.click(screen.getByRole('button', { name: 'Save score' }))

    expect(screen.getByRole('alert')).toHaveTextContent("can't end in a tie")
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('shows a refused correction and reloads the bracket', async () => {
    const reported = withResults({ 12: [1, 3] })
    const nextPlayed = withResults({ 12: [1, 3], 21: [2, 0] })
    mockEveryFetch(
      jsonResponse(200, reported),
      jsonResponse(409, {
        detail: "This result can't be changed: the next match has already been reported.",
      }),
      jsonResponse(200, nextPlayed),
    )
    renderPanel()

    await userEvent.click(await screen.findByRole('button', { name: 'Edit score: Delta vs Echo' }))
    await userEvent.clear(screen.getByLabelText('Delta'))
    await userEvent.type(screen.getByLabelText('Delta'), '5')
    await userEvent.click(screen.getByRole('button', { name: 'Save score' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('already been reported')
    // The reloaded bracket has the semifinal played, so the quarterfinal is final.
    expect(screen.queryByRole('button', { name: /Delta vs Echo/ })).not.toBeInTheDocument()
  })

  it('shows the champion after the final is reported', async () => {
    const semisDone = withResults({ 12: [1, 3], 14: [2, 0], 21: [2, 1], 22: [0, 2] })
    const done = withResults({ 12: [1, 3], 14: [2, 0], 21: [2, 1], 22: [0, 2], 31: [4, 2] })
    mockEveryFetch(jsonResponse(200, semisDone), jsonResponse(200, done))
    renderPanel()

    await userEvent.click(
      await screen.findByRole('button', { name: 'Report score: Alpha vs Charlie' }),
    )
    await userEvent.type(screen.getByLabelText('Alpha'), '4')
    await userEvent.type(screen.getByLabelText('Charlie'), '2')
    await userEvent.click(screen.getByRole('button', { name: 'Save score' }))

    expect(await screen.findByTestId('champion')).toHaveTextContent('Champion: Alpha')
    // The final can still be corrected: nothing comes after it.
    expect(screen.getByRole('button', { name: 'Edit score: Alpha vs Charlie' })).toBeInTheDocument()
  })
})
