import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { SIX_TEAM_BRACKET } from '../test/brackets.js'
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
})
