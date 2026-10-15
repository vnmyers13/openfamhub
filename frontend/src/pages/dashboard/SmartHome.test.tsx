import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { stateText, type HAEntity } from '../../api/homeAssistant'
import { useAuthStore, type User } from '../../stores/auth'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import { WallDashboardPageView } from '../../wall/WallDashboard'
import Dashboard from '../Dashboard'

const SUMMARY = {
  today: '2026-10-15', events_today: [], chores: { mine_open: 0, mine_done: 0, family_open: 0, family_done: 0 },
  points_balance: 0, allowance_cents: 0, meals_today: [], meals_week: [], birthdays: [], announcements: [],
}
const PREFS = { nav: 'side', calendar_scope: 'family', wallpaper: 'none', wallpaper_media_id: null,
  pages: [{ name: 'Home', widgets: [{ key: 'home', size: 'normal' }, { key: 'meals', size: 'normal' }] }] }
const light = (state = 'on'): HAEntity => ({ entity_id: 'light.kitchen', name: 'Kitchen light', domain: 'light', state, brightness: 50 })
const ENTITIES: HAEntity[] = [
  light(),
  { entity_id: 'scene.movie_night', name: 'Movie night', domain: 'scene', state: 'scening' },
  { entity_id: 'climate.hall', name: 'Hall thermostat', domain: 'climate', state: 'heat', current_temperature: 20.5, target_temperature: 21, min_temp: 7, max_temp: 22 },
  { entity_id: 'sensor.outside', name: 'Outside', domain: 'sensor', state: '12.3', unit: '°C' },
]
const live = (entities = ENTITIES) => ({ configured: true, available: true, error: null, entities })

function setup(role: string, ha: unknown, extra: Record<string, unknown> = {}) {
  useAuthStore.getState().setUser({ id: 'kid', display_name: 'Kid', role } as User)
  return mockApi({
    'GET /users/me/preferences': PREFS,
    'GET /dashboard/summary': SUMMARY,
    'GET /ha/states': ha,
    ...extra,
  })
}

/** The card once the states have arrived (it shows a placeholder first). */
async function loaded() {
  await screen.findByText('Kitchen light')
  return screen.getByRole('region', { name: 'Smart Home' })
}

describe('Smart home card', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('stays hidden until Home Assistant is set up', async () => {
    setup('member', { configured: false, available: false, error: null, entities: [] })
    renderApp(<Dashboard />)
    expect(await screen.findByText('Nothing planned today.')).toBeTruthy()
    await waitFor(() => expect(screen.queryByRole('region', { name: 'Smart Home' })).toBeNull())
  })

  it('lets members switch a light, run a scene and nudge the thermostat', async () => {
    const calls = setup('member', live(), {
      'POST /ha/action': (body: { entity_id: string; action: string; temperature?: number }) => (
        body.entity_id === 'light.kitchen' ? light('off')
          : body.entity_id === 'climate.hall' ? { ...ENTITIES[2], target_temperature: body.temperature } : ENTITIES[1]),
    })
    renderApp(<Dashboard />)
    const card = await loaded()
    expect(within(card).getByText('12.3 °C')).toBeTruthy()
    expect(within(card).getByText('20.5° · heat')).toBeTruthy()
    fireEvent.click(within(card).getByRole('button', { name: 'Turn off: Kitchen light' }))
    expect(await within(card).findByRole('button', { name: 'Turn on: Kitchen light' })).toBeTruthy()
    const posts = () => calls.filter((c) => c.method === 'POST').length
    // Buttons wait while an action is on its way, so press them one at a time.
    await waitFor(() => expect((within(card).getByRole('button', { name: 'Run: Movie night' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(within(card).getByRole('button', { name: 'Run: Movie night' }))
    await waitFor(() => expect(posts()).toBe(2))
    await waitFor(() => expect((within(card).getByRole('button', { name: 'Warmer: Hall thermostat' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(within(card).getByRole('button', { name: 'Warmer: Hall thermostat' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'POST').map((c) => c.body)).toEqual([
      { entity_id: 'light.kitchen', action: 'toggle' },
      { entity_id: 'scene.movie_night', action: 'turn_on' },
      { entity_id: 'climate.hall', action: 'set_temperature', temperature: 22 },
    ]))
    expect(await within(card).findByText('set 22°')).toBeTruthy()
    await waitFor(() => expect((within(card).getByRole('button', { name: 'Warmer: Hall thermostat' }) as HTMLButtonElement).disabled).toBe(false))
    fireEvent.click(within(card).getByRole('button', { name: 'Warmer: Hall thermostat' }))  // already at the top of its range
    await waitFor(() => expect(posts()).toBe(4))
    expect(calls.filter((c) => c.method === 'POST').at(-1)?.body).toEqual({ entity_id: 'climate.hall', action: 'set_temperature', temperature: 22 })
  })

  it('explains an action that failed', async () => {
    setup('admin', live(), { 'POST /ha/action': () => { throw apiError(502, "Home Assistant isn't reachable right now.") } })
    renderApp(<Dashboard />)
    const card = await loaded()
    fireEvent.click(within(card).getByRole('button', { name: 'Run: Movie night' }))
    expect((await within(card).findByRole('alert')).textContent).toMatch(/isn't reachable/)
  })

  it('viewers only look', async () => {
    setup('viewer', live())
    renderApp(<Dashboard />)
    const card = await loaded()
    expect(within(card).getByText('Kitchen light')).toBeTruthy()
    expect(within(card).queryAllByRole('button')).toEqual([])
  })

  it('says when Home Assistant is down, and tells admins where to choose entities', async () => {
    setup('member', { configured: true, available: false, error: "Home Assistant isn't reachable right now.", entities: [] })
    const { unmount } = renderApp(<Dashboard />)
    expect(await screen.findByText("Home Assistant isn't reachable right now.")).toBeTruthy()
    unmount()
    setup('admin', live([]))
    renderApp(<Dashboard />)
    const card = await screen.findByRole('region', { name: 'Smart Home' })
    expect((await within(card).findByRole('link', { name: 'Settings' })).getAttribute('href')).toBe('/admin/settings')
  })
})

describe('richer smart-home controls', () => {
  afterEach(() => useAuthStore.getState().clearUser())
  const RICH: HAEntity[] = [
    { ...light(), dimmable: true, brightness: 50 },
    { entity_id: 'light.porch', name: 'Porch light', domain: 'light', state: 'on', dimmable: false },
    { entity_id: 'climate.hall', name: 'Hall thermostat', domain: 'climate', state: 'heat', current_temperature: 20.5,
      target_temperature: 21, hvac_modes: ['off', 'heat', 'cool'] },
    { entity_id: 'sensor.outside', name: 'Outside', domain: 'sensor', state: '12.3', unit: '°C' },
    { entity_id: 'sensor.mode', name: 'House mode', domain: 'sensor', state: 'away' },
  ]
  const HISTORY = { entity_id: 'sensor.outside', unit: '°C', low: 9, high: 14,
    points: [['2026-10-14T12:00:00+00:00', 9], ['2026-10-14T18:00:00+00:00', 14], ['2026-10-15T06:00:00+00:00', 11]] }

  it('dims a light once the slider stops, and changes the thermostat mode', async () => {
    const calls = setup('member', live(RICH), {
      'POST /ha/action': (body: { entity_id: string; brightness?: number; hvac_mode?: string }) => (
        body.entity_id === 'light.kitchen' ? { ...RICH[0], brightness: body.brightness } : { ...RICH[2], state: body.hvac_mode }),
      'GET /ha/history/sensor.outside': HISTORY,
    })
    renderApp(<Dashboard />)
    const card = await loaded()
    expect(within(card).queryByLabelText('Brightness: Porch light')).toBeNull()  // not dimmable
    const slider = within(card).getByLabelText('Brightness: Kitchen light')
    fireEvent.change(slider, { target: { value: '40' } })
    fireEvent.change(slider, { target: { value: '30' } })
    expect(within(card).getByText('30%')).toBeTruthy()
    await waitFor(() => expect(calls.filter((c) => c.method === 'POST').map((c) => c.body)).toEqual(
      [{ entity_id: 'light.kitchen', action: 'set_brightness', brightness: 30 }]))
    const mode = within(card).getByLabelText('Mode: Hall thermostat') as HTMLSelectElement
    expect([...mode.options].map((o) => o.textContent)).toEqual(['Off', 'Heat', 'Cool'])
    await waitFor(() => expect(mode.disabled).toBe(false))
    fireEvent.change(mode, { target: { value: 'cool' } })
    await waitFor(() => expect(calls.filter((c) => c.method === 'POST').at(-1)?.body).toEqual(
      { entity_id: 'climate.hall', action: 'set_hvac_mode', hvac_mode: 'cool' }))
    expect(await within(card).findByText('20.5° · cool')).toBeTruthy()
  })

  it('draws a day of a numeric sensor for everyone, without controls for viewers', async () => {
    const calls = setup('viewer', live(RICH), { 'GET /ha/history/sensor.outside': HISTORY })
    renderApp(<Dashboard />)
    const card = await loaded()
    expect(await within(card).findByRole('img', { name: 'Outside, last 24 hours: low 9 °C, high 14 °C' })).toBeTruthy()
    expect(within(card).getByText('9–14 °C')).toBeTruthy()
    expect(calls.some((c) => c.url === '/ha/history/sensor.mode')).toBe(false)  // not a number
    expect(within(card).queryByLabelText('Brightness: Kitchen light')).toBeNull()
    expect(within(card).queryByLabelText('Mode: Hall thermostat')).toBeNull()
  })
})

describe('the wall Smart home card', () => {
  const page = { name: 'Home', duration_seconds: 30, widgets: [{ key: 'home' as const, size: 'normal' as const }] }

  it('shows states and trends with no controls', async () => {
    const calls = mockApi({ 'GET /wall/home-assistant': live(), 'GET /wall/home-assistant/history/sensor.outside': {
      entity_id: 'sensor.outside', unit: '°C', low: 9, high: 14, points: [['2026-10-14T12:00:00+00:00', 9], ['2026-10-15T06:00:00+00:00', 14]] } })
    renderApp(<WallDashboardPageView page={page} timeZone="America/Detroit" />)
    expect(await screen.findByText('Kitchen light')).toBeTruthy()
    expect(await screen.findByRole('img', { name: /Outside, last 24 hours/ })).toBeTruthy()
    expect(screen.queryAllByRole('button')).toEqual([])
    expect(screen.queryByRole('slider')).toBeNull()
    expect(calls.some((c) => c.url.startsWith('/ha/'))).toBe(false)
  })

  it('says when it is not set up or not reachable', async () => {
    mockApi({ 'GET /wall/home-assistant': { configured: false, available: false, error: null, entities: [] } })
    const { unmount } = renderApp(<WallDashboardPageView page={page} timeZone="America/Detroit" />)
    expect(await screen.findByText('Home Assistant is not set up.')).toBeTruthy()
    unmount()
    mockApi({ 'GET /wall/home-assistant': { configured: true, available: false, error: 'Home Assistant refused the access token (check HA_TOKEN).', entities: [] } })
    renderApp(<WallDashboardPageView page={page} timeZone="America/Detroit" />)
    expect(await screen.findByText(/refused the access token/)).toBeTruthy()
  })
})

describe('stateText', () => {
  const e = (over: Partial<HAEntity>): HAEntity => ({ entity_id: 'x.y', name: 'X', domain: 'sensor', state: 'on', ...over })
  it('reads each kind the way a person would say it', () => {
    expect(stateText(e({ domain: 'binary_sensor', device_class: 'door', state: 'on' }))).toBe('Open')
    expect(stateText(e({ domain: 'binary_sensor', device_class: 'window', state: 'off' }))).toBe('Closed')
    expect(stateText(e({ domain: 'binary_sensor', device_class: 'motion', state: 'on' }))).toBe('Someone there')
    expect(stateText(e({ domain: 'binary_sensor', device_class: 'moisture', state: 'off' }))).toBe('Dry')
    expect(stateText(e({ domain: 'binary_sensor', device_class: 'lock', state: 'off' }))).toBe('Locked')
    expect(stateText(e({ domain: 'binary_sensor', state: 'on' }))).toBe('On')
    expect(stateText(e({ domain: 'switch', state: 'off' }))).toBe('Off')
    expect(stateText(e({ domain: 'script', state: 'off' }))).toBe('')
    expect(stateText(e({ domain: 'climate', state: 'off', current_temperature: 19, unit: '°C' }))).toBe('19°C · off')
    expect(stateText(e({ domain: 'sensor', state: '55' }))).toBe('55')
    expect(stateText(e({ state: 'unavailable' }))).toBe('Unavailable')
  })
})
