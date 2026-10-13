import { describe, expect, it } from 'vitest'
import { describeBadge } from './badges'

describe('describeBadge', () => {
  it('says what earns each kind', () => {
    expect(describeBadge('streak_days', 7)).toBe('A 7-day streak')
    expect(describeBadge('chores_completed', 1)).toBe('Complete 1 chore')
    expect(describeBadge('chores_completed', 10)).toBe('Complete 10 chores')
    expect(describeBadge('points_earned', 100)).toBe('Earn 100 chore points')
    expect(describeBadge('points_earned', 1)).toBe('Earn 1 chore point')
  })
})
