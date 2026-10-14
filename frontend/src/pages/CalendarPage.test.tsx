import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import CalendarPage from './CalendarPage'

function signIn(role: string, id = 'u1') {
  useAuthStore.getState().setUser({
    id, display_name: 'Test', role, color_hex: '#000000', ui_mode: 'standard',
    avatar_type: null, avatar_value: null, family_id: 'f',
  } as User)
}

// An event at noon today (local), so it's in the month the page opens on.
const noon = new Date()
noon.setHours(12, 0, 0, 0)
const DINNER = {
  id: 'e1', source_id: 'int', title: 'Dinner', start_dt: noon.toISOString(),
  end_dt: new Date(noon.getTime() + 3600_000).toISOString(), all_day: false, location: null,
  description: null, created_by: 'u1', external_uid: null, source_color_hex: '#4F46E5',
}
const SOURCES = [{ id: 'int', provider: 'internal', display_name: 'Family Calendar', color_hex: '#4F46E5', enabled: true }]

const fill = (placeholder: string, value: string) =>
  fireEvent.change(screen.getByPlaceholderText(placeholder), { target: { value } })

describe('CalendarPage', () => {
  afterEach(() => {
    useAuthStore.getState().clearUser()
    try { localStorage.clear() } catch { /* ignore */ }
  })

  it('hides "New Event" from viewers', async () => {
    signIn('viewer')
    mockApi({ 'GET /calendar/events': [DINNER], 'GET /calendar/sources': SOURCES })
    renderApp(<CalendarPage />)
    expect(await screen.findByText('Dinner')).toBeTruthy()
    expect(screen.queryByRole('button', { name: '+ New Event' })).toBeNull()
  })

  it('checks that the end is after the start before saving', async () => {
    signIn('member')
    const calls = mockApi({ 'GET /calendar/events': [], 'GET /calendar/sources': SOURCES })
    const { container } = renderApp(<CalendarPage />)
    fireEvent.click(await screen.findByRole('button', { name: '+ New Event' }))
    fill('Event title', 'Backwards')
    container.querySelectorAll('input[type="date"]').forEach((d) => fireEvent.change(d, { target: { value: '2026-10-20' } }))
    const times = container.querySelectorAll('input[type="time"]')
    fireEvent.change(times[0], { target: { value: '15:00' } })
    fireEvent.change(times[1], { target: { value: '14:00' } })
    fireEvent.click(screen.getByRole('button', { name: /save|create|add/i }))
    expect(await screen.findByText('End must be after start')).toBeTruthy()
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it("shows the server's reason when saving fails", async () => {
    signIn('member')
    mockApi({
      'GET /calendar/events': [], 'GET /calendar/sources': SOURCES,
      'POST /calendar/events': () => { throw apiError(403, 'Viewers can only read the calendar') },
    })
    renderApp(<CalendarPage />)
    fireEvent.click(await screen.findByRole('button', { name: '+ New Event' }))
    fill('Event title', 'Soccer')
    fireEvent.click(screen.getByRole('button', { name: /save|create|add/i }))
    expect(await screen.findByText('Viewers can only read the calendar')).toBeTruthy()
  })

  it('saves a timed event as UTC instants and closes the form', async () => {
    signIn('member')
    const calls = mockApi({ 'GET /calendar/events': [], 'GET /calendar/sources': SOURCES, 'POST /calendar/events': DINNER })
    const { container } = renderApp(<CalendarPage />)
    fireEvent.click(await screen.findByRole('button', { name: '+ New Event' }))
    fill('Event title', 'Soccer')
    fill('Location (optional)', 'Field 3')
    // Set both dates: late in the evening the form defaults the end to tomorrow.
    const today = '2026-10-20'
    container.querySelectorAll('input[type="date"]').forEach((d) => fireEvent.change(d, { target: { value: today } }))
    const times = container.querySelectorAll('input[type="time"]')
    fireEvent.change(times[0], { target: { value: '17:00' } })
    fireEvent.change(times[1], { target: { value: '18:30' } })
    fireEvent.click(screen.getByRole('button', { name: /save|create|add/i }))
    await waitFor(() => expect(screen.queryByText('New Event')).toBeNull())
    const body = calls.find((c) => c.method === 'POST')?.body as Record<string, unknown>
    expect(body).toMatchObject({ title: 'Soccer', all_day: false, location: 'Field 3' })
    expect(body.start_dt).toBe(new Date(`${today}T17:00`).toISOString())
    expect(body.end_dt).toBe(new Date(`${today}T18:30`).toISOString())
  })

  it('fills the form from an event link, then saves what was reviewed', async () => {
    signIn('member')
    const start = new Date(2026, 10, 5, 18, 30)
    const calls = mockApi({
      'GET /calendar/events': [], 'GET /calendar/sources': SOURCES, 'POST /calendar/events': DINNER,
      'POST /import/event': { title: 'School Concert', start_dt: start.toISOString(),
        end_dt: new Date(start.getTime() + 90 * 60_000).toISOString(), all_day: false, location: 'Lincoln Elementary',
        description: 'Bring a chair.' },
    })
    renderApp(<CalendarPage />)
    fireEvent.click(await screen.findByRole('button', { name: '+ New Event' }))
    fireEvent.change(screen.getByLabelText('Fill from a link'), { target: { value: 'https://school.example.com/concert' } })
    fireEvent.click(screen.getByRole('button', { name: 'Fill' }))
    expect(await screen.findByDisplayValue('School Concert')).toBeTruthy()
    expect(screen.getByDisplayValue('Lincoln Elementary')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /save|create|add/i }))
    await waitFor(() => expect(calls.some((c) => c.url === '/calendar/events' && c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.url === '/calendar/events' && c.method === 'POST')?.body).toMatchObject({
      title: 'School Concert', start_dt: start.toISOString(), end_dt: new Date(start.getTime() + 90 * 60_000).toISOString(),
      all_day: false, location: 'Lincoln Elementary', description: 'Bring a chair.',
    })
  })

  it("says why a link couldn't fill the form", async () => {
    signIn('member')
    mockApi({ 'GET /calendar/events': [], 'GET /calendar/sources': SOURCES,
      'POST /import/event': () => { throw apiError(400, 'No event found on that page') } })
    renderApp(<CalendarPage />)
    fireEvent.click(await screen.findByRole('button', { name: '+ New Event' }))
    fireEvent.change(screen.getByLabelText('Fill from a link'), { target: { value: 'https://example.com' } })
    fireEvent.click(screen.getByRole('button', { name: 'Fill' }))
    expect(await screen.findByText('No event found on that page')).toBeTruthy()
  })

  it('saves an all-day event as dates with an exclusive end', async () => {
    signIn('member')
    const calls = mockApi({ 'GET /calendar/events': [], 'GET /calendar/sources': SOURCES, 'POST /calendar/events': DINNER })
    const { container } = renderApp(<CalendarPage />)
    fireEvent.click(await screen.findByRole('button', { name: '+ New Event' }))
    fill('Event title', 'Camp')
    fireEvent.click(container.querySelector('input[type="checkbox"]')!)
    const dates = container.querySelectorAll('input[type="date"]')
    fireEvent.change(dates[0], { target: { value: '2026-10-20' } })
    fireEvent.change(dates[1], { target: { value: '2026-10-22' } })
    fireEvent.click(screen.getByRole('button', { name: /save|create|add/i }))
    await waitFor(() => expect(calls.some((c) => c.method === 'POST')).toBe(true))
    expect(calls.find((c) => c.method === 'POST')?.body).toMatchObject({
      all_day: true, start_dt: '2026-10-20T00:00:00Z', end_dt: '2026-10-23T00:00:00Z',
    })
  })

  it('lets the creator delete an event and shows why a delete failed', async () => {
    signIn('member', 'u1')
    mockApi({
      'GET /calendar/events': [DINNER], 'GET /calendar/sources': SOURCES,
      'DELETE /calendar/events/e1': () => { throw apiError(403, 'You can only change your own events') },
    })
    renderApp(<CalendarPage />)
    fireEvent.click(await screen.findByText('Dinner'))
    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
    expect(await screen.findByText('You can only change your own events')).toBeTruthy()
  })

  it("doesn't offer Delete on someone else's event to a member", async () => {
    signIn('member', 'someone-else')
    mockApi({ 'GET /calendar/events': [DINNER], 'GET /calendar/sources': SOURCES })
    renderApp(<CalendarPage />)
    fireEvent.click(await screen.findByText('Dinner'))
    expect(await screen.findByRole('button', { name: 'Close' })).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull()
  })

  it('hides and shows a calendar with its filter chip', async () => {
    signIn('viewer')
    const school = { id: 'sch', provider: 'ical', display_name: 'School', color_hex: '#059669', enabled: true }
    const game = { ...DINNER, id: 'e2', source_id: 'sch', title: 'Game', created_by: null, external_uid: 'g1' }
    mockApi({ 'GET /calendar/events': [DINNER, game], 'GET /calendar/sources': [...SOURCES, school] })
    renderApp(<CalendarPage />)
    expect(await screen.findByText('Game')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'School' }))
    await waitFor(() => expect(screen.queryByText('Game')).toBeNull())
    expect(screen.getByText('Dinner')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'School' }))
    expect(await screen.findByText('Game')).toBeTruthy()
  })

  it('moves between months, days and back to today, and remembers the view', async () => {
    signIn('viewer')
    mockApi({ 'GET /calendar/events': [], 'GET /calendar/sources': SOURCES })
    renderApp(<CalendarPage />)
    const now = new Date()
    // The page's own title (react-big-calendar renders a second one in its toolbar).
    const heading = () => screen.getByRole('heading', { level: 1 }).parentElement!.parentElement!.querySelector('.text-white.font-medium')?.textContent
    const monthTitle = (d: Date) => d.toLocaleString('en-US', { month: 'long', year: 'numeric' })
    expect((await screen.findAllByText(monthTitle(now))).length).toBeGreaterThan(0)

    fireEvent.click(screen.getByRole('button', { name: '→' }))
    expect(heading()).toBe(monthTitle(new Date(now.getFullYear(), now.getMonth() + 1, 1)))
    fireEvent.click(screen.getByRole('button', { name: '←' }))
    fireEvent.click(screen.getByRole('button', { name: '←' }))
    expect(heading()).toBe(monthTitle(new Date(now.getFullYear(), now.getMonth() - 1, 1)))
    fireEvent.click(screen.getAllByRole('button', { name: 'Today' })[0])  // ours precedes the calendar's own toolbar
    expect(heading()).toBe(monthTitle(now))

    fireEvent.click(screen.getByRole('button', { name: 'day' }))
    const dayTitle = (d: Date) => d.toLocaleString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })
    expect(heading()).toBe(dayTitle(now))
    fireEvent.click(screen.getByRole('button', { name: '→' }))
    expect(heading()).toBe(dayTitle(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)))
    expect(localStorage.getItem('openfamhub_calendar_view')).toBe('day')

    for (const view of ['week', 'agenda', 'month']) {
      fireEvent.click(screen.getByRole('button', { name: view }))
      expect(localStorage.getItem('openfamhub_calendar_view')).toBe(view)
    }
    fireEvent.click(screen.getByRole('button', { name: 'week' }))
    fireEvent.click(screen.getByRole('button', { name: '→' }))
    fireEvent.click(screen.getByRole('button', { name: '←' }))
  })

  it('switches between everyone and just me, and remembers it', async () => {
    signIn('member')
    const calls = mockApi({
      'GET /calendar/events': (params: unknown) => ((params as { scope?: string }).scope === 'mine' ? [] : [DINNER]),
      'GET /calendar/sources': SOURCES,
      'GET /users/me/preferences': { nav: 'side', calendar_scope: 'family', wallpaper: 'none', wallpaper_media_id: null, pages: [] },
      'PUT /users/me/preferences': (body: unknown) => body,
    })
    renderApp(<CalendarPage />)
    expect(await screen.findAllByText('Dinner')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Just me' }))
    await waitFor(() => expect(screen.queryByText('Dinner')).toBeNull())
    expect(screen.getByRole('button', { name: 'Just me' }).getAttribute('aria-pressed')).toBe('true')
    expect(calls.find((c) => c.method === 'PUT')?.body).toMatchObject({ calendar_scope: 'mine' })
    expect(calls.some((c) => c.url === '/calendar/events' && (c.body as { scope?: string }).scope === 'mine')).toBe(true)
  })
})
