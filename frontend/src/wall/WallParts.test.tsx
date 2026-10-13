import { act, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import Avatar from '../components/Avatar'
import { mockApi } from '../test/api'
import WallClock from './WallClock'
import WallProgress from './WallProgress'

describe('wall parts', () => {
  it('the clock shows the time and date, and ticks', () => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 9, 12, 9, 5, 0))
    try {
      const { container } = render(<WallClock />)
      expect(container.textContent).toContain('09:05')
      expect(container.textContent).toMatch(/Monday/)
      vi.setSystemTime(new Date(2026, 9, 12, 9, 6, 0))
      act(() => {
        vi.advanceTimersByTime(1000)
      })
      expect(container.textContent).toContain('09:06')
    } finally {
      vi.useRealTimers()
    }
  })

  it('the progress panel shows each member with their points', async () => {
    mockApi({ 'GET /wall/progress': [
      { user_id: 'a', display_name: 'Mom', color_hex: '#4F46E5', avatar_value: null, points_balance: 3,
        points_this_week: 3, streak_days: 0, badges: [] },
      { user_id: 'b', display_name: 'Kid', color_hex: '', avatar_value: '🦊', points_balance: 40,
        points_this_week: 12, streak_days: 5, badges: [{ id: 'x', name: 'Helper', icon: '🏅' }] },
    ] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><WallProgress /></QueryClientProvider>)
    expect(await screen.findByText('Mom')).toBeTruthy()
    expect(screen.getByText('Kid')).toBeTruthy()
    expect(screen.getByLabelText('40 points')).toBeTruthy()
    expect(screen.getByText(/5-day streak/)).toBeTruthy()
  })

  it('an avatar shows the emoji, or the initial when there is none', () => {
    const { container, rerender } = render(<Avatar name="mom" color="#4F46E5" emoji="🦊" />)
    expect(container.textContent).toBe('🦊')
    rerender(<Avatar name="mom" color="" />)
    expect(container.textContent).toBe('M')
  })
})
