import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore, type User } from '../stores/auth'
import { apiError, mockApi } from '../test/api'
import { renderApp } from '../test/render'
import { DEFAULT_NOTIFICATIONS } from '../api/prefs'
import MySettings from './MySettings'

const push = vi.hoisted(() => ({ state: 'off' as string, turnOnPush: vi.fn(), turnOffPush: vi.fn(), sendTestPush: vi.fn() }))
vi.mock('../lib/push', () => ({
  pushState: async () => push.state,
  turnOnPush: async () => { await push.turnOnPush(); push.state = 'on' },
  turnOffPush: async () => { await push.turnOffPush(); push.state = 'off' },
  sendTestPush: () => push.sendTestPush(),
}))

const PREFS = { nav: 'side', calendar_scope: 'family', wallpaper: 'none', wallpaper_media_id: null, pages: [] }
const photo = (id: string) => ({ id, kind: 'photo', status: 'ready', error: null, original_name: `${id}.jpg`, width: 1, height: 1,
  duration_s: null, uploaded_by: 'kid', created_at: null, wall_url: `/api/media/${id}/wall`, thumb_url: `/api/media/${id}/thumb` })

function setup(role = 'member', extra: Record<string, unknown> = {}) {
  useAuthStore.getState().setUser({ id: 'kid', display_name: 'Kid', role, color_hex: '#059669', avatar_type: 'emoji', avatar_value: '🦊' } as User)
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
    fireEvent.click(within(screen.getByRole('region', { name: 'Birthday' })).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Saved')).toBeTruthy()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ birthday: '2016-05-02' })
  })

  it('explains a birthday that was refused', async () => {
    setup('member', { 'PATCH /users/kid': () => { throw apiError(422, 'birthday must be a past date') } })
    renderApp(<MySettings />)
    fireEvent.change(await screen.findByDisplayValue('2016-05-01'), { target: { value: '2099-01-01' } })
    fireEvent.click(within(screen.getByRole('region', { name: 'Birthday' })).getByRole('button', { name: 'Save' }))
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
      { ...PREFS, nav: 'top', calendar_scope: 'mine', wallpaper: 'photo', wallpaper_media_id: 'm1', notifications: DEFAULT_NOTIFICATIONS })
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

  it('changes my own name, color and avatar, and the app shows them at once', async () => {
    const calls = setup()
    renderApp(<MySettings />)
    const profile = await screen.findByRole('region', { name: 'Profile' })
    const save = within(profile).getByRole('button', { name: 'Save' }) as HTMLButtonElement
    expect(save.disabled).toBe(true)  // nothing changed yet
    fireEvent.change(within(profile).getByLabelText('My name'), { target: { value: ' Sam ' } })
    fireEvent.change(within(profile).getByLabelText('My color'), { target: { value: '#dc2626' } })
    fireEvent.click(within(profile).getByRole('radio', { name: 'Avatar 🚀' }))
    fireEvent.click(save)
    expect(await within(profile).findByText('Saved')).toBeTruthy()
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ display_name: 'Sam', color_hex: '#dc2626', avatar: '🚀' })
    expect(useAuthStore.getState().user).toMatchObject({ display_name: 'Sam', color_hex: '#dc2626', avatar_value: '🚀' })
  })

  it('starts unchanged for someone with no color or avatar yet', async () => {
    useAuthStore.getState().setUser({ id: 'kid', display_name: 'Kid', role: 'member' } as User)
    mockApi({ 'GET /users/me/preferences': PREFS, 'GET /users/kid': { birthday: null }, 'GET /media': [] })
    renderApp(<MySettings />)
    const profile = await screen.findByRole('region', { name: 'Profile' })
    expect((within(profile).getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true)
    expect(within(profile).queryByRole('radio', { checked: true })).toBeNull()
  })

  it("explains a name that's taken", async () => {
    setup('member', { 'PATCH /users/kid': () => { throw apiError(409, 'Someone in the family is already called "Mom"') } })
    renderApp(<MySettings />)
    const profile = await screen.findByRole('region', { name: 'Profile' })
    fireEvent.change(within(profile).getByLabelText('My name'), { target: { value: 'Mom' } })
    fireEvent.click(within(profile).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Someone in the family is already called "Mom"')).toBeTruthy()
    expect(useAuthStore.getState().user?.display_name).toBe('Kid')
  })

  describe('Notifications', () => {
    afterEach(() => { push.state = 'off'; vi.clearAllMocks() })

    it('turns them on for this device and sends a test', async () => {
      push.sendTestPush.mockResolvedValue(1)
      setup()
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      fireEvent.click(await within(section).findByRole('button', { name: 'Turn on for this device' }))
      expect(await within(section).findByText('On for this device.')).toBeTruthy()
      expect(push.turnOnPush).toHaveBeenCalled()
      fireEvent.click(within(section).getByRole('button', { name: 'Send a test' }))
      expect(await within(section).findByText('Sent. It should show up in a moment.')).toBeTruthy()
      fireEvent.click(within(section).getByRole('button', { name: 'Turn off' }))
      expect(await within(section).findByRole('button', { name: 'Turn on for this device' })).toBeTruthy()
    })

    it('tells iPhone users to add the app to the Home Screen first', async () => {
      push.state = 'install-first'
      setup()
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      expect(await within(section).findByText(/Add to Home Screen/)).toBeTruthy()
      expect(within(section).queryByRole('button', { name: 'Turn on for this device' })).toBeNull()
    })

    it("says why notifications couldn't be turned on", async () => {
      push.turnOnPush.mockRejectedValueOnce(new Error('Allow notifications for OpenFamHub in this browser'))
      setup()
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      fireEvent.click(await within(section).findByRole('button', { name: 'Turn on for this device' }))
      expect(await within(section).findByText(/Allow notifications for OpenFamHub/)).toBeTruthy()
    })

    it('saves which reminders I get', async () => {
      const calls = setup('admin')
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      fireEvent.change(within(section).getByLabelText('Before events'), { target: { value: 'mine' } })
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ events: 'mine', event_minutes: 15 }))
      fireEvent.change(within(section).getByLabelText('How long before'), { target: { value: '30' } })
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ event_minutes: 30 }))
      fireEvent.click(within(section).getByLabelText('A morning list of my chores and to-dos'))
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ daily: false }))
      fireEvent.click(within(section).getByLabelText('Reward requests waiting for a yes'))
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ rewards: false }))
    })

    it('members have no reward-request choice', async () => {
      setup('member')
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      expect(within(section).queryByLabelText('Reward requests waiting for a yes')).toBeNull()
    })

    it('saves birthday, pantry and allowance choices', async () => {
      const calls = setup('member')
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      fireEvent.click(within(section).getByLabelText('Birthdays, the morning before'))
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ birthdays: false }))
      fireEvent.click(within(section).getByLabelText('Pantry food reaching its use-by date'))
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ pantry: false }))
      fireEvent.click(within(section).getByLabelText('When my allowance is paid'))
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ allowance: false }))
    })

    it('adds an ntfy topic and an email address when the server offers them, and tests them without a device', async () => {
      push.sendTestPush.mockResolvedValue(2)
      const calls = setup('member', { 'GET /push/channels': { ntfy: 'https://ntfy.example.test', email: true } })
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      expect(await within(section).findByText(/subscribe to this topic on https:\/\/ntfy.example.test/)).toBeTruthy()
      expect(within(section).queryByRole('button', { name: 'Send a test' })).toBeNull()
      fireEvent.click(within(section).getByRole('button', { name: 'Make one' }))
      const topic = (within(section).getByLabelText('ntfy topic') as HTMLInputElement).value
      expect(topic).toMatch(/^ofh-[a-z2-9]{10}$/)
      fireEvent.click(within(section).getByRole('button', { name: 'Save ntfy topic' }))
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ ntfy_topic: topic }))
      fireEvent.change(within(section).getByLabelText('Email address'), { target: { value: 'not an address' } })
      expect(within(section).getByRole('alert').textContent).toMatch(/doesn't look like an email/)
      expect((within(section).getByRole('button', { name: 'Save email address' }) as HTMLButtonElement).disabled).toBe(true)
      fireEvent.change(within(section).getByLabelText('Email address'), { target: { value: ' kid@example.com ' } })
      fireEvent.click(within(section).getByRole('button', { name: 'Save email address' }))
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ email_to: 'kid@example.com' }))
      fireEvent.click(await within(section).findByRole('button', { name: 'Send a test' }))
      expect(await within(section).findByText('Sent. It should show up in a moment.')).toBeTruthy()
    })

    it('clears a topic when it is emptied, and refuses a bad one', async () => {
      const calls = setup('member', {
        'GET /push/channels': { ntfy: 'https://ntfy.example.test', email: false },
        'GET /users/me/preferences': { ...PREFS, notifications: { ...DEFAULT_NOTIFICATIONS, ntfy_topic: 'ofh-old' } },
      })
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      await waitFor(() => expect((within(section).getByLabelText('ntfy topic') as HTMLInputElement).value).toBe('ofh-old'))
      const input = within(section).getByLabelText('ntfy topic')
      expect(within(section).queryByLabelText('Email address')).toBeNull()
      fireEvent.change(input, { target: { value: 'has space' } })
      expect(within(section).getByRole('alert').textContent).toMatch(/letters, digits/)
      fireEvent.change(input, { target: { value: '' } })
      fireEvent.click(within(section).getByRole('button', { name: 'Save ntfy topic' }))
      await waitFor(() => expect(lastPrefs(calls)?.notifications).toMatchObject({ ntfy_topic: null }))
    })

    it('shows no other channels when the server has none', async () => {
      setup('member', { 'GET /push/channels': { ntfy: null, email: false } })
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      await within(section).findByText('Off on this device.')
      expect(within(section).queryByRole('group', { name: 'Other places to get them' })).toBeNull()
    })

    it('viewers only choose events and birthdays', async () => {
      setup('viewer')
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      expect(within(section).getByLabelText('Birthdays, the morning before')).toBeTruthy()
      expect(within(section).queryByLabelText('Pantry food reaching its use-by date')).toBeNull()
      expect(within(section).queryByLabelText('When my allowance is paid')).toBeNull()
    })

    it('keeps the morning time while birthdays still use it', async () => {
      setup('member')
      renderApp(<MySettings />)
      const section = await screen.findByRole('region', { name: 'Notifications' })
      fireEvent.click(within(section).getByLabelText('A morning list of my chores and to-dos'))
      expect(await within(section).findByLabelText('Morning list time')).toBeTruthy()
    })
  })
})

function lastPrefs(calls: { method: string; url: string; body: unknown }[]) {
  return calls.filter((c) => c.method === 'PUT' && c.url === '/users/me/preferences').at(-1)?.body as
    { notifications?: Record<string, unknown> } | undefined
}
