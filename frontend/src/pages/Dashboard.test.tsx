import { screen } from '@testing-library/react'
import { addDays, format } from 'date-fns'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { mockApi } from '../test/api'
import { renderApp } from '../test/render'
import Dashboard from './Dashboard'

const at = (h: number) => { const d = new Date(); d.setHours(h, 0, 0, 0); return d.toISOString() }
const dateOnly = (d: Date) => `${format(d, 'yyyy-MM-dd')}T00:00:00+00:00`
const ev = (id: string, title: string, start: string, end: string, all_day = false) =>
  ({ id, source_id: 's', title, start_dt: start, end_dt: end, all_day, location: null, description: null,
     created_by: null, external_uid: null, source_color_hex: '#4F46E5' })

describe('Dashboard', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it("greets the member and lists only today's events", async () => {
    useAuthStore.getState().setUser({ id: 'u', display_name: 'Mom', role: 'admin' } as User)
    const today = new Date()
    mockApi({
      'GET /calendar/events': [
        ev('a', 'School run', at(8), at(9)),
        ev('b', 'Spirit day', dateOnly(today), dateOnly(addDays(today, 1)), true),
        // The UTC overlap query can return tomorrow's all-day event west of UTC.
        ev('c', 'Tomorrow trip', dateOnly(addDays(today, 1)), dateOnly(addDays(today, 2)), true),
      ],
      'GET /calendar/sources': [],
    })
    renderApp(<Dashboard />)
    expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/^Good (morning|afternoon|evening), Mom!$/)
    expect(await screen.findByText('School run')).toBeTruthy()
    expect(screen.getByText('Spirit day')).toBeTruthy()
    expect(screen.queryByText('Tomorrow trip')).toBeNull()
  })

  it('says when today is empty', async () => {
    mockApi({ 'GET /calendar/events': [], 'GET /calendar/sources': [] })
    renderApp(<Dashboard />)
    expect(await screen.findByText('No events scheduled for today.')).toBeTruthy()
  })

  it("shows the family's stars", async () => {
    mockApi({
      'GET /calendar/events': [], 'GET /calendar/sources': [],
      'GET /rewards/progress': [{ user_id: 'kid', display_name: 'Kid', color_hex: '#059669', avatar_value: null,
        points_balance: 42, points_this_week: 7, streak_days: 2, badges: [] }],
    })
    renderApp(<Dashboard />)
    expect(await screen.findByLabelText('42 points')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Rewards' })).toBeTruthy()
  })
})
