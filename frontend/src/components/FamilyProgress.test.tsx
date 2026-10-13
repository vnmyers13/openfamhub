import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FamilyProgress from './FamilyProgress'

const row = (over: object = {}) => ({
  user_id: 'kid', display_name: 'Kid', color_hex: '#059669', avatar_value: '🦊', points_balance: 42,
  points_this_week: 12, streak_days: 3, badges: [{ id: 'b1', name: 'Helper', icon: '🏅' }], ...over,
})

describe('FamilyProgress', () => {
  it('shows points, this week, streak and badges for each person', () => {
    render(<FamilyProgress rows={[row(), row({ user_id: 'sib', display_name: 'Sib', points_balance: 0, points_this_week: 0,
      streak_days: 0, badges: [] })]} />)
    expect(screen.getByText('Kid')).toBeTruthy()
    expect(screen.getByLabelText('42 points')).toBeTruthy()
    expect(screen.getByText(/\+12 this week/)).toBeTruthy()
    expect(screen.getByText(/3-day streak/)).toBeTruthy()
    expect(screen.getByLabelText('Badges: Helper')).toBeTruthy()
    expect(screen.getByLabelText('0 points')).toBeTruthy()
    expect(screen.getAllByText(/streak/)).toHaveLength(1)
  })

  it('says so when nobody is earning yet', () => {
    render(<FamilyProgress rows={[]} size="wall" />)
    expect(screen.getByText('No one is earning points yet.')).toBeTruthy()
  })
})
