import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { SIX_TEAM_BRACKET, withResults } from '../test/brackets.js'
import ScoreEntry from './ScoreEntry.jsx'

const unplayed = SIX_TEAM_BRACKET.rounds[0].matches[1] // Delta v Echo
const played = withResults({ 12: [1, 3] }).rounds[0].matches[1]

function renderEntry(match = unplayed, onSubmit = vi.fn().mockResolvedValue(true)) {
  render(<ScoreEntry match={match} onSubmit={onSubmit} />)
  return onSubmit
}

async function enter(team1, team2) {
  await userEvent.click(screen.getByRole('button', { name: /score: Delta vs Echo/ }))
  if (team1 !== '') await userEvent.type(screen.getByLabelText('Delta'), team1)
  if (team2 !== '') await userEvent.type(screen.getByLabelText('Echo'), team2)
  await userEvent.click(screen.getByRole('button', { name: 'Save score' }))
}

describe('ScoreEntry', () => {
  it('submits whole-number scores and closes', async () => {
    const onSubmit = renderEntry()

    await enter('2', '1')

    expect(onSubmit).toHaveBeenCalledWith(2, 1)
    expect(screen.queryByRole('form')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Report score: Delta vs Echo' })).toBeInTheDocument()
  })

  it('rejects a tie without submitting', async () => {
    const onSubmit = renderEntry()

    await enter('2', '2')

    expect(screen.getByRole('alert')).toHaveTextContent("can't end in a tie")
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it.each([
    ['-1', '0', "Delta's score can't be negative."],
    ['1.5', '0', "Delta's score must be a whole number."],
    ['', '3', "Delta's score is required."],
    ['1000000', '0', "Delta's score must be 999,999 or less."],
  ])('rejects %s - %s', async (team1, team2, message) => {
    const onSubmit = renderEntry()

    await enter(team1, team2)

    expect(screen.getByText(message)).toBeInTheDocument()
    expect(screen.getByLabelText('Delta')).toHaveAttribute('aria-invalid', 'true')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('stays open when saving fails', async () => {
    renderEntry(unplayed, vi.fn().mockResolvedValue(false))

    await enter('2', '1')

    expect(screen.getByRole('button', { name: 'Save score' })).toBeEnabled()
    expect(screen.getByLabelText('Delta')).toHaveValue(2)
  })

  it('edits a reported score, starting from the current one', async () => {
    const onSubmit = renderEntry(played)

    await userEvent.click(screen.getByRole('button', { name: 'Edit score: Delta vs Echo' }))
    expect(screen.getByLabelText('Delta')).toHaveValue(1)
    expect(screen.getByLabelText('Echo')).toHaveValue(3)
    await userEvent.clear(screen.getByLabelText('Delta'))
    await userEvent.type(screen.getByLabelText('Delta'), '4')
    await userEvent.click(screen.getByRole('button', { name: 'Save score' }))

    expect(onSubmit).toHaveBeenCalledWith(4, 3)
  })

  it('can be cancelled', async () => {
    const onSubmit = renderEntry()

    await userEvent.click(screen.getByRole('button', { name: 'Report score: Delta vs Echo' }))
    await userEvent.click(screen.getByRole('button', { name: 'Cancel' }))

    expect(screen.queryByLabelText('Delta')).not.toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })
})
