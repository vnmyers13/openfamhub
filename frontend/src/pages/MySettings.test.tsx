import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import MySettings from './MySettings'

const PREFS = { nav: 'side', calendar_scope: 'family', wallpaper: 'none', wallpaper_media_id: null, pages: [] }
const photo = (id: string) => ({ id, kind: 'photo', status: 'ready', error: null, original_name: `${id}.jpg`, width: 1, height: 1,
  duration_s: null, uploaded_by: 'kid', created_at: null, wall_url: `/api/media/${id}/wall`, thumb_url: `/api/media/${id}/thumb` })

function setup(role = 'member', extra: Record<string, unknown> = {}) {
  useAuthStore.getState().setUser({ id: 'kid', display_name: 'Kid', role } as User)
  return mockApi({
    'GET /users/me/preferences': PREFS,
    'PUT /users/me/preferences': (body: unknown) => body,
    'GET /users/kid': { id: 'kid', birthday: '2016-05-01' },
    'PATCH /users/kid': {},
    'GET /media': [photo('m1'), { ...photo('v1'), kind: 'video' }],
    ...extra,
  })
}

describe('MySettings', () => {
  afterEach(() => useAuthStore.getState().clearUser())

  it('saves my birthday', async () => {
    const calls = setup()
    renderApp(<MySettings />)
    const input = await screen.findByDisplayValue('2016-05-01')
    fireEvent.change(input, { target: { value: '2016-05-02' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Saved')).toBeTruthy()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ birthday: '2016-05-02' })
  })

  it('explains a birthday that was refused', async () => {
    setup('member', { 'PATCH /users/kid': () => { throw apiError(422, 'birthday must be a past date') } })
    renderApp(<MySettings />)
    fireEvent.change(await screen.findByDisplayValue('2016-05-01'), { target: { value: '2099-01-01' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('birthday must be a past date')).toBeTruthy()
  })

  it('saves the menu position, whose events to show and the wallpaper', async () => {
    const calls = setup()
    renderApp(<MySettings />)
    fireEvent.click(await screen.findByRole('radio', { name: 'Across the top' }))
    await waitFor(() => expect(screen.getByRole('radio', { name: 'Across the top' }).getAttribute('aria-checked')).toBe('true'))
    fireEvent.click(screen.getByRole('radio', { name: 'Just the events I added' }))
    await waitFor(() => expect(screen.getByRole('radio', { name: 'Just the events I added' }).getAttribute('aria-checked')).toBe('true'))
    fireEvent.click(screen.getByRole('radio', { name: 'Forest' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Use photo m1.jpg' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(4))
    expect(calls.filter((c) => c.method === 'PUT').at(-1)?.body).toEqual(
      { ...PREFS, nav: 'top', calendar_scope: 'mine', wallpaper: 'photo', wallpaper_media_id: 'm1' })
    expect(screen.queryByRole('button', { name: 'Use photo v1.jpg' })).toBeNull()
  })

  it('points to Photos when there are none, and viewers have no birthday box', async () => {
    setup('viewer', { 'GET /media': [] })
    renderApp(<MySettings />)
    expect(await screen.findByRole('link', { name: 'Photos' })).toBeTruthy()
    expect(screen.queryByRole('region', { name: 'Birthday' })).toBeNull()
  })

  it('shows when a preference could not be saved', async () => {
    setup('member', { 'PUT /users/me/preferences': () => { throw apiError(422, 'bad preferences') } })
    renderApp(<MySettings />)
    fireEvent.click(await screen.findByRole('radio', { name: 'Across the top' }))
    expect(await screen.findByText('bad preferences')).toBeTruthy()
  })
})
