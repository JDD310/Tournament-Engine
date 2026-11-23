import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SIX_TEAM_BRACKET, withResults } from '../test/brackets.js'
import BracketView from './BracketView.jsx'

function teamLines(matchLabel) {
  return within(screen.getByRole('list', { name: matchLabel }))
    .getAllByRole('listitem')
    .map((li) => li.textContent)
}

describe('BracketView', () => {
  it('shows the rounds left to right, first round to final', () => {
    render(<BracketView bracket={SIX_TEAM_BRACKET} />)

    const columns = [...screen.getByTestId('bracket').children]
    expect(columns.map((c) => within(c).getByRole('heading').textContent)).toEqual([
      'Quarterfinals',
      'Semifinals',
      'Final',
    ])
  })

  it('shows the team names and seeds in each match', () => {
    render(<BracketView bracket={SIX_TEAM_BRACKET} />)

    expect(teamLines('Quarterfinals, match 2')).toEqual(['4Delta', 'Echo'])
    expect(teamLines('Quarterfinals, match 4')).toEqual(['3Charlie', 'Foxtrot'])
  })

  it('shows byes as already won and the bye winner in the next round', () => {
    render(<BracketView bracket={SIX_TEAM_BRACKET} />)

    expect(teamLines('Quarterfinals, match 1')).toEqual(['1Alpha (advances)', 'Bye'])
    expect(teamLines('Semifinals, match 1')).toEqual(['1Alpha', 'TBD'])
    expect(teamLines('Semifinals, match 2')).toEqual(['2Bravo', 'TBD'])
    expect(teamLines('Final, match 1')).toEqual(['TBD', 'TBD'])
  })

  it('renders nothing before the bracket is generated', () => {
    const { container } = render(<BracketView bracket={{ generated: false, rounds: [] }} />)

    expect(container).toBeEmptyDOMElement()
  })

  it('shows reported scores next to the teams and marks the winner', () => {
    render(<BracketView bracket={withResults({ 12: [1, 3] })} />)

    expect(teamLines('Quarterfinals, match 2')).toEqual(['4Delta1', 'Echo3 (advances)'])
    expect(teamLines('Semifinals, match 1')).toEqual(['1Alpha', 'Echo'])
  })

  it('shows the champion once the final is reported', () => {
    const done = withResults({ 12: [1, 3], 14: [2, 0], 21: [2, 1], 22: [0, 2], 31: [4, 2] })
    render(<BracketView bracket={done} />)

    expect(screen.getByTestId('champion')).toHaveTextContent('Tournament complete. Champion: Alpha')
  })

  it('has no champion or match actions by default', () => {
    render(<BracketView bracket={SIX_TEAM_BRACKET} />)

    expect(screen.queryByTestId('champion')).not.toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('renders match actions under each match when given', () => {
    render(
      <BracketView
        bracket={SIX_TEAM_BRACKET}
        renderMatchActions={(match) => <button type="button">Act on {match.id}</button>}
      />,
    )

    expect(screen.getAllByRole('button')).toHaveLength(7)
    expect(screen.getByRole('button', { name: 'Act on 12' })).toBeInTheDocument()
  })
})
