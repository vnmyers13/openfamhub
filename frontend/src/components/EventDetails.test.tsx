import { fireEvent, screen, within } from '@testing-library/react'
import { addHours, format } from 'date-fns'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { CalendarEvent } from '../api/calendar'
import Dashboard from '../pages/Dashboard'
import { useAuthStore, type User } from '../stores/auth'
import { mockApi } from '../test/api'
import { renderApp } from '../test/render'
import { WallDashboardPageView } from '../wall/WallDashboard'
import EventDetails from './EventDetails'

const start = new Date(new Date().setHours(15, 0, 0, 0))
const GAME: CalendarEvent = {
  id: 'g', source_id: 'club', title: 'Soccer game', start_dt: start.toISOString(), end_dt: addHours(start, 1).toISOString(),
  all_day: false, location: 'Riverside Park, Field 3',
  description: 'Bring water.\nSchedule: https://club.example/schedule. <b>not bold</b>',
  url: 'https://club.example/games/42', organizer: 'Coach Lee', attendees: Array.from({ length: 12 }, (_, i) => `Kid ${i + 1}`),
  created_by: 'mom', external_uid: 'game-1', source_color_hex: '#059669', created_at: null, updated_at: null,
}
const LOOKUPS = {
  'GET /calendar/sources': [{ id: 'club', display_name: 'Soccer club', color_hex: '#059669' }],
  'GET /users/': [{ id: 'mom', display_name: 'Mom', role: 'admin', color_hex: '#000', avatar_value: null }],
}

describe('EventDetails', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('shows everything we know about an event, with safe links', async () => {
    mockApi(LOOKUPS)
    renderApp(<EventDetails event={GAME} onClose={() => {}} />)
    const dialog = screen.getByRole('dialog', { name: 'Soccer game' })
    expect(within(dialog).getByText(`${format(start, 'EEE d MMM')}, 3:00 PM – 4:00 PM`)).toBeTruthy()
    expect(await within(dialog).findByText('Soccer club')).toBeTruthy()
    expect(await within(dialog).findByText('Added by Mom')).toBeTruthy()
    const map = within(dialog).getByRole('link', { name: 'Map: Riverside Park, Field 3' })
    expect(map.getAttribute('href')).toContain('query=Riverside%20Park%2C%20Field%203')
    expect(map.getAttribute('rel')).toBe('noopener noreferrer')
    const notes = within(dialog).getByTestId('event-notes')
    expect(within(notes).getByRole('link', { name: 'https://club.example/schedule' }).getAttribute('href')).toBe('https://club.example/schedule')
    expect(notes.textContent).toContain('<b>not bold</b>')  // shown as text, never as HTML
    expect(notes.querySelector('b')).toBeNull()
    expect(within(dialog).getByRole('link', { name: 'club.example' }).getAttribute('href')).toBe('https://club.example/games/42')
    expect(within(dialog).getByText('Organized by Coach Lee')).toBeTruthy()
    expect(within(dialog).getByText(/^With Kid 1, Kid 2, .*Kid 10 and 2 more$/)).toBeTruthy()
  })

  it('leaves out what an event does not have, and closes with Escape or Close', () => {
    mockApi({ ...LOOKUPS })
    const onClose = vi.fn()
    renderApp(<EventDetails onClose={onClose} event={{ ...GAME, location: null, description: null, url: null, organizer: null,
      attendees: null, created_by: null, all_day: true, start_dt: '2026-10-15T00:00:00+00:00', end_dt: '2026-10-16T00:00:00+00:00' }} />)
    const dialog = screen.getByRole('dialog')
    expect(within(dialog).getByText('Thu 15 Oct, all day')).toBeTruthy()
    expect(within(dialog).queryAllByRole('link')).toEqual([])
    expect(within(dialog).queryByText(/Organized by|With |Added by/)).toBeNull()
    fireEvent.keyDown(window, { key: 'Escape' })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(onClose).toHaveBeenCalledTimes(2)
  })
})

describe('events on Home', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('show where they are and open their details', async () => {
    useAuthStore.getState().setUser({ id: 'kid', display_name: 'Kid', role: 'member' } as User)
    mockApi({
      ...LOOKUPS,
      'GET /users/me/preferences': { nav: 'side', calendar_scope: 'family', wallpaper: 'none', wallpaper_media_id: null,
        pages: [{ name: 'Home', widgets: [{ key: 'events', size: 'wide' }, { key: 'week', size: 'wide' }] }] },
      'GET /dashboard/summary': { today: format(new Date(), 'yyyy-MM-dd'), events_today: [GAME, { ...GAME, id: 'h', title: 'Homework club', location: null }],
        chores: { mine_open: 0, mine_done: 0, family_open: 0, family_done: 0 }, points_balance: 0, allowance_cents: 0,
        meals_today: [], meals_week: [], birthdays: [], announcements: [] },
      'GET /calendar/events': [GAME],
    })
    renderApp(<Dashboard />)
    const today = await screen.findByRole('region', { name: "Today's Events" })
    expect(await within(today).findByText('Riverside Park, Field 3')).toBeTruthy()
    expect(within(within(today).getByRole('button', { name: 'Details: Homework club' })).queryByText(/📍/)).toBeNull()
    const week = await screen.findByRole('region', { name: 'This Week' })
    expect(await within(week).findByText('Riverside Park, Field 3')).toBeTruthy()
    fireEvent.click(within(today).getByRole('button', { name: 'Details: Soccer game' }))
    const dialog = await screen.findByRole('dialog', { name: 'Soccer game' })
    expect(within(dialog).getByText('Organized by Coach Lee')).toBeTruthy()
    expect(within(dialog).getByRole('link', { name: 'Open the calendar' }).getAttribute('href')).toBe('/calendar')
    fireEvent.click(within(dialog).getByRole('button', { name: 'Close' }))
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})

describe("the wall's Today's events", () => {
  it('shows where each event is', async () => {
    mockApi({ 'GET /wall/events': [GAME] })
    renderApp(<WallDashboardPageView timeZone={Intl.DateTimeFormat().resolvedOptions().timeZone}
      page={{ name: 'Today', duration_seconds: 30, widgets: [{ key: 'events', size: 'wide' }] }} />)
    expect(await screen.findByText('Riverside Park, Field 3')).toBeTruthy()
    expect(screen.queryAllByRole('button')).toEqual([])
  })
})
