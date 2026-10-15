import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { addDays, format } from 'date-fns'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import Dashboard from './Dashboard'

const at = (h: number) => { const d = new Date(); d.setHours(h, 0, 0, 0); return d.toISOString() }
const dateOnly = (d: Date) => `${format(d, 'yyyy-MM-dd')}T00:00:00+00:00`
const ev = (id: string, title: string, start: string, end: string, all_day = false) =>
  ({ id, source_id: 's', title, start_dt: start, end_dt: end, all_day, location: null, description: null,
     created_by: null, external_uid: null, source_color_hex: '#4F46E5' })
const today = new Date()
const TODAY = format(today, 'yyyy-MM-dd')

const summary = (over: object = {}) => ({
  today: TODAY,
  events_today: [],
  chores: { mine_open: 2, mine_done: 1, family_open: 3, family_done: 4 },
  points_balance: 42,
  allowance_cents: 1250,
  meals_today: [{ day: TODAY, slot: 'dinner', title: 'Tacos', recipe_id: 'r1' }],
  meals_week: [],
  birthdays: [{ user_id: 'kid', display_name: 'Kid', color_hex: '#059669', avatar_value: null, date: TODAY, turns: 9, days_away: 0 }],
  announcements: [{ id: 'a1', body: 'Pizza Friday', pinned: true, author_id: 'mom', created_at: '2026-10-13T12:00:00+00:00' }],
  ...over,
})

const chore = (id: string, title: string) => ({ id, template_id: 't', title, points: 5, due_date: TODAY, status: 'pending',
  assigned_to: null, claimed_by: null, completed_by: null, completed_at: null, routine_id: null })

function signIn(id: string, role: string) {
  useAuthStore.getState().setUser({ id, display_name: id === 'mom' ? 'Mom' : 'Kid', role } as User)
}

function homeApi(extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /dashboard/summary': summary(),
    'GET /weather': { configured: false },
    'GET /rewards/progress': [{ user_id: 'kid', display_name: 'Kid', color_hex: '#059669', avatar_value: null,
      points_balance: 42, points_this_week: 7, streak_days: 2, badges: [] }],
    'GET /calendar/sources': [{ id: 's', sync_error: null }],
    'GET /ha/states': { configured: false, available: false, error: null, entities: [] },
    'GET /chores/instances': (params: { scope?: string } | undefined) => (params?.scope === 'available' ? [chore('c1', 'Take out recycling')] : []),
    ...extra,
  })
}

describe('Dashboard', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it("greets the member and lists only today's events", async () => {
    signIn('mom', 'admin')
    homeApi({ 'GET /dashboard/summary': summary({ events_today: [
      ev('a', 'School run', at(8), at(9)),
      ev('b', 'Spirit day', dateOnly(today), dateOnly(addDays(today, 1)), true),
      // The UTC day window can include tomorrow's all-day event west of UTC.
      ev('c', 'Tomorrow trip', dateOnly(addDays(today, 1)), dateOnly(addDays(today, 2)), true),
    ] }) })
    renderApp(<Dashboard />)
    expect(screen.getByRole('heading', { level: 1 }).textContent).toMatch(/^Good (morning|afternoon|evening), Mom!$/)
    expect(await screen.findByText('School run')).toBeTruthy()
    expect(screen.getByText('Spirit day')).toBeTruthy()
    expect(screen.queryByText('Tomorrow trip')).toBeNull()
  })

  it('shows my day, meals, birthdays, stars and sync status', async () => {
    signIn('mom', 'admin')
    homeApi()
    renderApp(<Dashboard />)
    expect(await screen.findByText('No events scheduled for today.')).toBeTruthy()
    const myDay = screen.getByRole('region', { name: 'My Day' })
    expect(within(myDay).getByText('2')).toBeTruthy()
    expect(within(myDay).getByText('4/7')).toBeTruthy()
    expect(within(myDay).getByText('⭐ 42')).toBeTruthy()
    expect(within(myDay).getByText('$12.50')).toBeTruthy()
    expect(screen.getByText('Tacos')).toBeTruthy()
    expect(screen.getByText('Kid turns 9')).toBeTruthy()
    expect(screen.getByText('🎂 Today!')).toBeTruthy()
    expect(await screen.findByLabelText('42 points')).toBeTruthy()
    expect(await screen.findByText('All sources healthy')).toBeTruthy()
  })

  it('lists chores up for grabs and claims one', async () => {
    signIn('kid', 'member')
    const calls = homeApi({ 'POST /chores/instances/c1/claim': { ...chore('c1', 'Take out recycling'), status: 'claimed', claimed_by: 'kid' } })
    renderApp(<Dashboard />)
    const card = await screen.findByRole('region', { name: 'Chores Up for Grabs' })
    expect(await within(card).findByText('Take out recycling')).toBeTruthy()
    expect(within(card).getByText('⭐ 5')).toBeTruthy()
    fireEvent.click(within(card).getByRole('button', { name: 'Claim: Take out recycling' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST' && c.url === '/chores/instances/c1/claim')).toBe(true))
  })

  it('says when no chores are up for grabs, and shows how many more there are', async () => {
    signIn('kid', 'member')
    homeApi({ 'GET /chores/instances': [] })
    renderApp(<Dashboard />)
    const card = await screen.findByRole('region', { name: 'Chores Up for Grabs' })
    expect(await within(card).findByText('No open chores right now.')).toBeTruthy()
  })

  it('shows six chores up for grabs and counts the rest', async () => {
    signIn('kid', 'member')
    homeApi({ 'GET /chores/instances': Array.from({ length: 8 }, (_, i) => chore(`c${i}`, `Chore ${i}`)) })
    renderApp(<Dashboard />)
    const card = await screen.findByRole('region', { name: 'Chores Up for Grabs' })
    expect(await within(card).findByText('Chore 5')).toBeTruthy()
    expect(within(card).queryByText('Chore 6')).toBeNull()
    expect(within(card).getByText('and 2 more on the Chores page')).toBeTruthy()
  })

  it("explains a claim that didn't work", async () => {
    signIn('kid', 'member')
    homeApi({ 'POST /chores/instances/c1/claim': () => { throw apiError(409, "Someone else has this chore, or it's already done") } })
    renderApp(<Dashboard />)
    const card = await screen.findByRole('region', { name: 'Chores Up for Grabs' })
    fireEvent.click(await within(card).findByRole('button', { name: 'Claim: Take out recycling' }))
    expect((await within(card).findByRole('alert')).textContent).toMatch(/Someone else has this chore/)
  })

  it('hides personal numbers and admin cards from viewers', async () => {
    signIn('gm', 'viewer')
    homeApi({ 'GET /dashboard/summary': summary({ meals_today: [], birthdays: [], announcements: [] }) })
    renderApp(<Dashboard />)
    expect(await screen.findByText('Nothing planned today.')).toBeTruthy()
    expect(screen.queryByText('My points')).toBeNull()
    expect(screen.getByText('None in the next month.')).toBeTruthy()
    expect(screen.getByText('Nothing posted.')).toBeTruthy()
    expect(screen.queryByLabelText('New announcement')).toBeNull()
    expect(screen.queryByRole('region', { name: 'Sync Status' })).toBeNull()
    expect(screen.getByText('Not set up yet.')).toBeTruthy()
    expect(await screen.findByText('Take out recycling')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Claim: Take out recycling' })).toBeNull()
  })

  it('shows the weather, or how to set it up', async () => {
    signIn('mom', 'admin')
    homeApi({ 'GET /weather': { configured: true, place: 'Ann Arbor, Michigan', units: 'fahrenheit', temperature: 61,
      emoji: '⛅', label: 'Partly cloudy', wind: 8, days: [{ date: TODAY, emoji: '🌦️', label: 'Light rain', high: 64, low: 46, precip_chance: 40 }] } })
    const { unmount } = renderApp(<Dashboard />)
    expect(await screen.findByText('61°F')).toBeTruthy()
    expect(screen.getByText('Partly cloudy · Ann Arbor, Michigan')).toBeTruthy()
    expect(screen.getByText('64° / 46°')).toBeTruthy()
    unmount()
    homeApi({ 'GET /weather': { configured: true, place: 'X', error: 'Weather is unavailable right now' } })
    const second = renderApp(<Dashboard />)
    expect(await screen.findByText('Weather is unavailable right now')).toBeTruthy()
    second.unmount()
    homeApi()
    renderApp(<Dashboard />)
    expect(await screen.findByRole('link', { name: 'Settings' })).toBeTruthy()
  })

  it('posts, pins and removes announcements', async () => {
    signIn('mom', 'admin')
    const calls = homeApi({
      'POST /announcements': { id: 'a2' }, 'PATCH /announcements/a1': {}, 'DELETE /announcements/a1': null,
    })
    renderApp(<Dashboard />)
    expect(await screen.findByLabelText('Pinned')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('New announcement'), { target: { value: ' Dentist Tuesday ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Post' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: 'Unpin' }))
    fireEvent.click(screen.getByRole('button', { name: 'Remove: Pizza Friday' }))
    await waitFor(() => expect(calls.filter((c) => c.method !== 'GET').map((c) => [c.method, c.url, c.body])).toEqual([
      ['POST', '/announcements', { body: 'Dentist Tuesday' }],
      ['PATCH', '/announcements/a1', { pinned: false }],
      ['DELETE', '/announcements/a1', undefined],
    ]))
  })

  it("shows the server's reason when posting fails", async () => {
    signIn('kid', 'member')
    homeApi({ 'POST /announcements': () => { throw apiError(422, 'announcement must be 1-1000 characters') } })
    renderApp(<Dashboard />)
    fireEvent.change(await screen.findByLabelText('New announcement'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Post' }))
    expect(await screen.findByText('announcement must be 1-1000 characters')).toBeTruthy()
    // Members can't pin or remove someone else's post.
    expect(screen.queryByRole('button', { name: 'Unpin' })).toBeNull()
  })

  it('lets a member customize the shared family wall dashboard', async () => {
    signIn('kid', 'member')
    const calls = homeApi({
      'GET /family/wall-dashboard': { pages: [{ name: 'Kitchen', duration_seconds: 30, widgets: [{ key: 'events', size: 'wide' }] }] },
      'PUT /family/wall-dashboard': (body: unknown) => body,
    })
    renderApp(<Dashboard />)

    fireEvent.click(await screen.findByRole('button', { name: 'Customize' }))
    expect(screen.queryByRole('heading', { name: 'Family wall dashboard' })).toBeNull()
    expect(calls.some((c) => c.url === '/family/wall-dashboard')).toBe(false)
    fireEvent.click(screen.getByRole('button', { name: 'Edit family wall' }))
    expect(await screen.findByRole('heading', { name: 'Family wall dashboard' })).toBeTruthy()
    expect(await screen.findByDisplayValue('Kitchen')).toBeTruthy()
    fireEvent.change(screen.getByLabelText('Wall page duration'), { target: { value: '60' } })

    await waitFor(() => expect(calls.some((c) => c.method === 'PUT' && c.url === '/family/wall-dashboard')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT' && c.url === '/family/wall-dashboard')?.body).toEqual({
      pages: [{ name: 'Kitchen', duration_seconds: 60, widgets: [{ key: 'events', size: 'wide' }] }],
    })
  })
})
