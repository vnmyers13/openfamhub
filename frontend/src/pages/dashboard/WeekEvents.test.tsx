import { screen, waitFor, within } from '@testing-library/react'
import { addDays, format } from 'date-fns'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../../stores/auth'
import { mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import Dashboard from '../Dashboard'

const SUMMARY = {
  today: format(new Date(), 'yyyy-MM-dd'), events_today: [], chores: { mine_open: 0, mine_done: 0, family_open: 0, family_done: 0 },
  points_balance: 0, allowance_cents: 0, meals_today: [], meals_week: [], birthdays: [], announcements: [],
}
const prefs = (scope = 'family') => ({ nav: 'side', calendar_scope: scope, wallpaper: 'none', wallpaper_media_id: null,
  pages: [{ name: 'Home', widgets: [{ key: 'week', size: 'wide' }] }] })
const day = (n: number) => addDays(new Date(new Date().setHours(0, 0, 0, 0)), n)
const at = (n: number, h: number) => { const d = day(n); d.setHours(h, 0, 0, 0); return d.toISOString() }
const date = (n: number) => `${format(day(n), 'yyyy-MM-dd')}T00:00:00+00:00`
const ev = (id: string, title: string, start: string, end: string, all_day = false) =>
  ({ id, source_id: 's', title, start_dt: start, end_dt: end, all_day, location: null, description: null,
     created_by: null, external_uid: null, source_color_hex: '#4F46E5' })

function setup(events: unknown[], scope = 'family') {
  useAuthStore.getState().setUser({ id: 'kid', display_name: 'Kid', role: 'member' } as User)
  return mockApi({
    'GET /users/me/preferences': prefs(scope),
    'GET /dashboard/summary': SUMMARY,
    'GET /calendar/events': events,
  })
}

describe('This week card', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it("shows today and the next six days, each with its events", async () => {
    const calls = setup([
      ev('a', 'Dentist', at(0, 15), at(0, 16)),
      ev('b', 'Camping trip', date(2), date(4), true),  // two days
      ev('c', 'School holiday', date(1), date(2), true),
      ...['A', 'B', 'C', 'D', 'E'].map((x, i) => ev(`m${x}`, `Meeting ${x}`, at(5, 9 + i), at(5, 10 + i))),
    ])
    renderApp(<Dashboard />)
    const card = await screen.findByRole('region', { name: 'This Week' })
    await within(card).findByText('Dentist')
    const days = within(card).getAllByRole('listitem').filter((li) => li.getAttribute('aria-label'))
    expect(days.map((d) => d.getAttribute('aria-label'))).toEqual(
      ['Today', 'Tomorrow', ...[2, 3, 4, 5, 6].map((n) => format(day(n), 'EEE d MMM'))])
    expect(within(days[0]).getByText('Dentist')).toBeTruthy()
    expect(within(days[1]).getByText('School holiday')).toBeTruthy()
    expect(within(days[1]).getByText('All day')).toBeTruthy()
    expect(within(days[2]).getByText('Camping trip')).toBeTruthy()
    expect(within(days[3]).getByText('Camping trip')).toBeTruthy()
    expect(within(days[4]).getByText('Nothing planned')).toBeTruthy()
    expect(within(days[5]).getByText('Meeting D')).toBeTruthy()
    expect(within(days[5]).queryByText('Meeting E')).toBeNull()
    expect(within(days[5]).getByText('and 1 more')).toBeTruthy()
    const query = calls.find((c) => c.url === '/calendar/events')?.body as { start: string; end: string }
    expect(new Date(query.start).getTime()).toBe(day(0).getTime())
    expect(new Date(query.end).getTime()).toBe(day(7).getTime())
  })

  it('says when the week is empty, and follows "just mine"', async () => {
    const calls = setup([], 'mine')
    renderApp(<Dashboard />)
    expect(await screen.findByText('Nothing on the calendar this week.')).toBeTruthy()
    await waitFor(() => expect(calls.filter((c) => c.url === '/calendar/events').at(-1)?.body).toMatchObject({ scope: 'mine' }))
  })
})
