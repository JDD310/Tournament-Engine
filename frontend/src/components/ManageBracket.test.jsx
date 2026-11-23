import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { SIX_TEAM_BRACKET } from '../test/brackets.js'
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
})
