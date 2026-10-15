import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../../stores/auth'
import { mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import Dashboard from '../Dashboard'

const SUMMARY = {
  today: '2026-10-13', events_today: [], chores: { mine_open: 0, mine_done: 0, family_open: 0, family_done: 0 },
  points_balance: 0, allowance_cents: 0, meals_today: [], meals_week: [], birthdays: [], announcements: [],
}
const prefs = (over: object = {}) => ({ nav: 'side', calendar_scope: 'family', wallpaper: 'none', wallpaper_media_id: null, pages: [], ...over })

function setup(saved: object = prefs(), role = 'member') {
  useAuthStore.getState().setUser({ id: 'kid', display_name: 'Kid', role } as User)
  return mockApi({
    'GET /users/me/preferences': saved,
    'PUT /users/me/preferences': (body: unknown) => body,
    'GET /dashboard/summary': SUMMARY,
    'GET /weather': { configured: false },
    'GET /rewards/progress': [],
    'GET /calendar/sources': [],
  })
}
const puts = (calls: { method: string; body: unknown }[]) => calls.filter((c) => c.method === 'PUT').map((c) => c.body as { pages: unknown[] })
const cards = () => within(screen.getByRole('list', { name: 'Cards on this page' })).getAllByRole('listitem').map((li) => li.textContent?.replace(/[⠿↑↓✕]|Normal|Wide/g, '').trim())

describe('Dashboard customization', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('reorders, resizes, removes and adds cards, saving each change', async () => {
    const calls = setup()
    renderApp(<Dashboard />)
    fireEvent.click(await screen.findByRole('button', { name: 'Customize' }))
    expect(cards()).toEqual(["Today's events", 'Weather', 'My day', 'Chores up for grabs', "Today's meals", 'Family stars', 'Announcements', 'Birthdays'])
    fireEvent.click(screen.getByRole('button', { name: 'Move down: Weather' }))
    fireEvent.click(screen.getByRole('button', { name: "Make wide: Today's events" }))
    fireEvent.click(screen.getByRole('button', { name: 'Remove: Birthdays' }))
    fireEvent.change(await screen.findByLabelText('Card to add'), { target: { value: 'birthdays' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add' }))
    await waitFor(() => expect(puts(calls)).toHaveLength(4))
    const last = puts(calls)[3].pages as { name: string; widgets: { key: string; size: string }[] }[]
    expect(last[0].widgets.map((w) => `${w.key}:${w.size}`)).toEqual([
      'events:wide', 'my-day:normal', 'weather:normal', 'chores:normal', 'meals:normal', 'stars:normal', 'announcements:normal', 'birthdays:normal'])
    expect(screen.queryByLabelText('Card to add')).toBeNull()  // every card is on the page again
  })

  it('drags a card to a new place', async () => {
    const calls = setup(prefs({ pages: [{ name: 'Home', widgets: [{ key: 'events', size: 'normal' }, { key: 'meals', size: 'normal' }, { key: 'stars', size: 'normal' }] }] }))
    renderApp(<Dashboard />)
    fireEvent.click(await screen.findByRole('button', { name: 'Customize' }))
    const items = within(screen.getByRole('list', { name: 'Cards on this page' })).getAllByRole('listitem')
    fireEvent.dragStart(items[2])
    fireEvent.dragOver(items[0])
    fireEvent.drop(items[0])
    await waitFor(() => expect(puts(calls)).toHaveLength(1))
    expect((puts(calls)[0].pages[0] as { widgets: { key: string }[] }).widgets.map((w) => w.key)).toEqual(['stars', 'events', 'meals'])
  })

  it('adds a page from a template, switches pages, renames, deletes and resets', async () => {
    const calls = setup()
    renderApp(<Dashboard />)
    fireEvent.click(await screen.findByRole('button', { name: 'Customize' }))
    fireEvent.change(screen.getByLabelText('Template'), { target: { value: 'Kitchen' } })
    fireEvent.click(screen.getByRole('button', { name: 'Add page' }))
    expect(await screen.findByRole('tab', { name: 'Kitchen' })).toBeTruthy()
    expect(cards()).toEqual(["Today's meals", 'Weather', 'Announcements'])
    fireEvent.change(screen.getByLabelText('Page name'), { target: { value: 'Food' } })
    expect(await screen.findByRole('tab', { name: 'Food' })).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Home' }))
    expect(cards()[0]).toBe("Today's events")
    fireEvent.click(screen.getByRole('tab', { name: 'Food' }))
    fireEvent.click(screen.getByRole('button', { name: 'Delete page' }))
    await waitFor(() => expect(screen.queryByRole('tab')).toBeNull())
    fireEvent.click(screen.getByRole('button', { name: 'Reset to default' }))
    await waitFor(() => expect(puts(calls).at(-1)?.pages).toEqual([]))
    fireEvent.click(screen.getByRole('button', { name: 'Done' }))
    expect(screen.queryByRole('region', { name: 'Customize dashboard' })).toBeNull()
  })

  it('shows the saved wallpaper, pages and widths', async () => {
    setup(prefs({ wallpaper: 'ocean', pages: [{ name: 'Mine', widgets: [{ key: 'meals', size: 'wide' }] }, { name: 'Empty', widgets: [] }] }))
    renderApp(<Dashboard />)
    await waitFor(() => expect(screen.getByTestId('dashboard').className).toContain('from-sky-950'))
    expect(screen.getByRole('region', { name: "Today's Meals" }).parentElement?.className).toContain('md:col-span-2')
    expect(screen.queryByRole('region', { name: 'Weather' })).toBeNull()
    fireEvent.click(screen.getByRole('tab', { name: 'Empty' }))
    expect(screen.getByText('This page is empty. Press Customize to add cards.')).toBeTruthy()
  })

  it('uses a family photo as wallpaper and asks for just my events', async () => {
    const calls = setup(prefs({ wallpaper: 'photo', wallpaper_media_id: 'm1', calendar_scope: 'mine' }))
    renderApp(<Dashboard />)
    await waitFor(() => expect(screen.getByTestId('dashboard').style.backgroundImage).toContain('/api/media/m1/wall'))
    await waitFor(() => expect(calls.find((c) => c.url === '/dashboard/summary' && (c.body as { scope?: string } | undefined)?.scope === 'mine')).toBeTruthy())
  })
})
