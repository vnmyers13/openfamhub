import { act, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import Avatar from '../components/Avatar'
import { mockApi } from '../test/api'
import WallClock from './WallClock'
import WallProgress from './WallProgress'
import WallBirthdays from './WallBirthdays'

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

  it('the birthday card lists the next two weeks, or nothing', async () => {
    const day = (n: number) => { const d = new Date(); d.setDate(d.getDate() + n); return d.toISOString().slice(0, 10) }
    mockApi({ 'GET /wall/birthdays': [
      { user_id: 'a', display_name: 'Kid', color_hex: '#059669', avatar_value: null, date: day(0), turns: 9, days_away: 0 },
      { user_id: 'b', display_name: 'Sib', color_hex: '#4F46E5', avatar_value: null, date: day(1), turns: 6, days_away: 1 },
      { user_id: 'c', display_name: 'Mom', color_hex: '#DC2626', avatar_value: null, date: day(10), turns: 40, days_away: 10 },
    ] })
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const { unmount } = render(<QueryClientProvider client={client}><WallBirthdays /></QueryClientProvider>)
    expect(await screen.findByText(/Happy Birthday, Kid!/)).toBeTruthy()
    expect(screen.getByText('(turns 9)')).toBeTruthy()
    expect(screen.getByText('Tomorrow')).toBeTruthy()
    expect(screen.getByText('Mom turns 40')).toBeTruthy()
    unmount()
    mockApi({ 'GET /wall/birthdays': [] })
    const { container } = render(<QueryClientProvider client={new QueryClient()}><WallBirthdays /></QueryClientProvider>)
    await waitFor(() => expect(container.textContent).toBe(''))
  })

  it('an avatar shows the emoji, or the initial when there is none', () => {
    const { container, rerender } = render(<Avatar name="mom" color="#4F46E5" emoji="🦊" />)
    expect(container.textContent).toBe('🦊')
    rerender(<Avatar name="mom" color="" />)
    expect(container.textContent).toBe('M')
  })
})
