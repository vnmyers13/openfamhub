import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import { apiError, mockApi } from '../../test/api'
import FamilySettings from './FamilySettings'

const plain = (value: string | number, locked = false) => ({ value, locked })
const secret = (is_set: boolean, locked = false, unreadable?: boolean) => ({ is_set, locked, ...(unreadable ? { unreadable } : {}) })
const SETTINGS = {
  ha_url: plain(''), ha_token: secret(false),
  ntfy_url: plain('https://ntfy.sh'), ntfy_token: secret(true),
  smtp_host: plain(''), smtp_port: plain(587), smtp_security: plain('starttls'), smtp_username: plain(''),
  smtp_password: secret(false), smtp_from: plain(''),
  backup_time: plain('03:00'), backup_retention_days: plain(30), wall_idle_timeout_seconds: plain(300),
}
const FAMILY = { name: 'Myers', timezone: 'America/Detroit', sleep: { enabled: false, off: '22:00', on: '06:30' }, clocks: [] }

function open(section?: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[section ? `/admin/settings/${section}` : '/admin/settings']}>
        <Routes>
          <Route path="/admin/settings" element={<FamilySettings />} />
          <Route path="/admin/settings/:section" element={<FamilySettings />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('Admin › Settings sections', () => {
  it('has a menu of sections and opens each one', async () => {
    mockApi({ 'GET /family': FAMILY, 'GET /admin/server-settings': SETTINGS, 'GET /weather/location': null,
      'GET /ha/status': { configured: false, reachable: false, error: null }, 'GET /ha/config': { entities: [], routine_scenes: {} } })
    open()
    const nav = screen.getByRole('navigation', { name: 'Settings sections' })
    expect(within(nav).getAllByRole('link').map((a) => a.textContent)).toEqual(
      ['Family and wall', 'Weather', 'Notifications', 'Home Assistant', 'Backups and system'])
    expect(within(nav).getByRole('link', { name: 'Family and wall' }).getAttribute('aria-current')).toBe('page')
    expect(await screen.findByLabelText('Family name')).toBeTruthy()
    fireEvent.click(within(nav).getByRole('link', { name: 'Notifications' }))
    expect(await screen.findByRole('form', { name: 'ntfy' })).toBeTruthy()
    expect(screen.getByRole('form', { name: 'Email' })).toBeTruthy()
    fireEvent.click(within(nav).getByRole('link', { name: 'Home Assistant' }))
    expect(await screen.findByRole('form', { name: 'Connection' })).toBeTruthy()
    expect(await screen.findByText(/Not set up yet/)).toBeTruthy()
    fireEvent.click(within(nav).getByRole('link', { name: 'Backups and system' }))
    expect(await screen.findByRole('form', { name: 'Backups' })).toBeTruthy()
    expect(screen.getByRole('form', { name: 'Wall displays' })).toBeTruthy()
    fireEvent.click(within(nav).getByRole('link', { name: 'Weather' }))
    expect(await screen.findByLabelText('Find a place')).toBeTruthy()
  })

  it('saves only what changed, sets a secret without showing it, and tests the connection', async () => {
    const calls = mockApi({
      'GET /admin/server-settings': SETTINGS,
      'PUT /admin/server-settings': (body: Record<string, unknown>) => ({ ...SETTINGS, ha_url: plain(String(body.ha_url ?? '')), ha_token: secret(true) }),
      'POST /admin/server-settings/test/home-assistant': { ok: false, message: 'Home Assistant refused the access token; check the token.' },
      'GET /ha/status': { configured: false, reachable: false, error: null }, 'GET /ha/config': { entities: [], routine_scenes: {} },
    })
    open('home-assistant')
    const form = await screen.findByRole('form', { name: 'Connection' })
    const token = within(form).getByLabelText('Long-lived access token') as HTMLInputElement
    expect(token.type).toBe('password')
    expect(token.placeholder).toBe('Not set')
    fireEvent.change(within(form).getByLabelText('Home Assistant address'), { target: { value: 'http://192.168.1.20:8123' } })
    fireEvent.change(token, { target: { value: 'tok-123' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await within(form).findByText('Saved.')).toBeTruthy()
    expect(calls.find((c) => c.method === 'PUT')?.body).toEqual({ ha_url: 'http://192.168.1.20:8123', ha_token: 'tok-123' })
    const again = await screen.findByRole('form', { name: 'Connection' })
    await waitFor(() => expect((within(again).getByLabelText('Long-lived access token') as HTMLInputElement).placeholder).toBe('Set (type to replace)'))
    expect((within(again).getByLabelText('Long-lived access token') as HTMLInputElement).value).toBe('')
    fireEvent.click(within(again).getByRole('button', { name: 'Test connection' }))
    expect((await within(again).findByRole('alert')).textContent).toMatch(/refused the access token/)
  })

  it('clears a secret, keeps numbers as numbers, and says when nothing changed', async () => {
    const calls = mockApi({ 'GET /admin/server-settings': SETTINGS, 'PUT /admin/server-settings': SETTINGS,
      'POST /admin/server-settings/test/ntfy': { ok: true, message: 'Sent to your topic mom-7f3k.' } })
    open('notifications')
    const ntfy = await screen.findByRole('form', { name: 'ntfy' })
    fireEvent.click(within(ntfy).getByRole('button', { name: 'Save' }))
    expect(await within(ntfy).findByText('Nothing changed.')).toBeTruthy()
    fireEvent.click(within(ntfy).getByRole('button', { name: 'Clear Access token' }))
    fireEvent.click(within(ntfy).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'PUT').at(-1)?.body).toEqual({ ntfy_token: '' }))
    fireEvent.click(within(await screen.findByRole('form', { name: 'ntfy' })).getByRole('button', { name: 'Send me a test' }))
    expect(await screen.findByText('Sent to your topic mom-7f3k.')).toBeTruthy()
    const email = screen.getByRole('form', { name: 'Email' })
    fireEvent.change(within(email).getByLabelText('Port'), { target: { value: '465' } })
    fireEvent.change(within(email).getByLabelText('Security'), { target: { value: 'ssl' } })
    fireEvent.click(within(email).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'PUT').at(-1)?.body).toEqual({ smtp_port: 465, smtp_security: 'ssl' }))
  })

  it("shows what's set in .env as read-only, a secret that needs re-entering, and why a save failed", async () => {
    mockApi({
      'GET /admin/server-settings': { ...SETTINGS, backup_time: plain('04:00', true), smtp_password: secret(false, false, true) },
      'PUT /admin/server-settings': () => { throw apiError(422, 'backup_retention_days: a whole number from 1 to 3650') },
    })
    open('system')
    const backups = await screen.findByRole('form', { name: 'Backups' })
    expect((within(backups).getByLabelText('Daily backup at') as HTMLInputElement).disabled).toBe(true)
    expect(within(backups).getByText(/Set in .env/)).toBeTruthy()
    fireEvent.change(within(backups).getByLabelText('Keep backups for (days)'), { target: { value: '0' } })
    fireEvent.click(within(backups).getByRole('button', { name: 'Save' }))
    expect((await within(backups).findByRole('alert')).textContent).toMatch(/1 to 3650/)
  })

  it('warns when a saved secret can no longer be read', async () => {
    mockApi({ 'GET /admin/server-settings': { ...SETTINGS, smtp_password: secret(false, false, true) } })
    open('notifications')
    const email = await screen.findByRole('form', { name: 'Email' })
    expect(within(email).getByRole('alert').textContent).toMatch(/SECRET_KEY changed/)
  })
})
