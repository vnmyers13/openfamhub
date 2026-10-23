import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import CalendarSettings from './CalendarSettings'

const FAMILY = { id: 'int', provider: 'internal', display_name: 'Family Calendar', color_hex: '#4F46E5',
  ics_url: null, sync_interval_hours: 6, last_synced_at: null, sync_error: null, enabled: true }
const SCHOOL = { id: 'sch', provider: 'ical', display_name: 'School', color_hex: '#059669',
  ics_url: 'https://example.test/s.ics', sync_interval_hours: 6, last_synced_at: null, sync_error: null, enabled: true }

const renderPage = (opts?: { routes?: Record<string, string> }) => renderApp(<CalendarSettings />, opts)

describe('CalendarSettings', () => {
  it('links to calendar subscriptions management', async () => {
    mockApi({ 'GET /calendar/sources': [] })
    renderPage({ routes: { '/admin/subscriptions': 'subscriptions' } })
    expect(await screen.findByText('Calendar subscriptions →')).toBeTruthy()
  })

  it('lists sources; only feeds can be synced or deleted', async () => {
    mockApi({ 'GET /calendar/sources': [FAMILY, SCHOOL] })
    renderPage()
    expect(await screen.findByText('School')).toBeTruthy()
    expect(screen.getByText('Family Calendar')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Sync Now' })).toHaveLength(1)
    expect(screen.getAllByRole('button', { name: 'Delete' })).toHaveLength(1)
  })

  it('adds a feed and clears the form', async () => {
    const calls = mockApi({ 'GET /calendar/sources': [], 'POST /integrations/ical': SCHOOL })
    renderPage()
    const url = screen.getByPlaceholderText('https://example.com/calendar.ics') as HTMLInputElement
    const name = screen.getByPlaceholderText('Holidays') as HTMLInputElement
    fireEvent.change(url, { target: { value: 'https://example.test/s.ics' } })
    fireEvent.change(name, { target: { value: 'School' } })
    fireEvent.submit(url.closest('form')!)
    await waitFor(() => expect(url.value).toBe(''))
    expect(calls.find((c) => c.url === '/integrations/ical')?.body).toMatchObject({
      ics_url: 'https://example.test/s.ics', display_name: 'School', sync_interval_hours: 6,
    })
  })

  it("shows why a feed couldn't be added and keeps what was typed", async () => {
    mockApi({
      'GET /calendar/sources': [],
      'POST /integrations/ical': () => { throw apiError(400, 'The calendar URL timed out') },
    })
    renderPage()
    const url = screen.getByPlaceholderText('https://example.com/calendar.ics') as HTMLInputElement
    fireEvent.change(url, { target: { value: 'https://slow.example.test/s.ics' } })
    fireEvent.change(screen.getByPlaceholderText('Holidays'), { target: { value: 'Slow' } })
    fireEvent.submit(url.closest('form')!)
    expect(await screen.findByText('The calendar URL timed out')).toBeTruthy()
    expect(url.value).toBe('https://slow.example.test/s.ics')
  })

  it('reports sync results', async () => {
    let reply = { ok: true, error: null as string | null }
    mockApi({ 'GET /calendar/sources': [SCHOOL], 'POST /calendar/sources/sch/sync': () => reply })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Sync Now' }))
    expect(await screen.findByText('Synced School')).toBeTruthy()
    reply = { ok: false, error: 'ICS fetch returned HTTP 404' }
    fireEvent.click(screen.getByRole('button', { name: 'Sync Now' }))
    expect(await screen.findByText('School: ICS fetch returned HTTP 404')).toBeTruthy()
  })

  it('shows the sync log', async () => {
    mockApi({
      'GET /calendar/sources': [SCHOOL],
      'GET /calendar/sources/sch/log': [{ id: 'l1', source_id: 'sch', synced_at: '2026-10-12T10:00:00+00:00',
        events_upserted: 12, events_deleted: 1, duration_ms: 340, error: null }],
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Log' }))
    expect(await screen.findByText('Sync Log')).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Hide Log' })).toBeTruthy()
  })

  it('deletes a feed after confirming, and not without', async () => {
    const calls = mockApi({ 'GET /calendar/sources': [SCHOOL], 'DELETE /calendar/sources/sch': null })
    const confirm = vi.fn(() => false)
    vi.stubGlobal('confirm', confirm)
    try {
      renderPage()
      fireEvent.click(await screen.findByRole('button', { name: 'Delete' }))
      expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
      confirm.mockReturnValue(true)
      fireEvent.click(screen.getByRole('button', { name: 'Delete' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('edits a feed: only what changed is sent, and the form closes', async () => {
    const calls = mockApi({
      'GET /calendar/sources': [FAMILY, SCHOOL],
      'PATCH /calendar/sources/sch': { ...SCHOOL, display_name: 'Soccer', ics_url: 'webcal://example.test/team.ics' },
    })
    renderPage()
    await screen.findByText('School')
    fireEvent.click(screen.getByRole('button', { name: 'Edit School' }))
    const form = screen.getByRole('form', { name: 'Edit School' })
    fireEvent.change(within(form).getByLabelText('Name'), { target: { value: 'Soccer' } })
    fireEvent.change(within(form).getByLabelText('Link'), { target: { value: 'webcal://example.test/team.ics' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(screen.queryByRole('form', { name: 'Edit School' })).toBeNull())
    expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ display_name: 'Soccer', ics_url: 'webcal://example.test/team.ics' })
    expect(await screen.findByText('Saved Soccer')).toBeTruthy()
  })

  it("keeps the form open with the reason when a new link doesn't work", async () => {
    mockApi({
      'GET /calendar/sources': [SCHOOL],
      'PATCH /calendar/sources/sch': () => { throw apiError(400, 'Could not reach the calendar URL') },
    })
    renderPage()
    await screen.findByText('School')
    fireEvent.click(screen.getByRole('button', { name: 'Edit School' }))
    const form = screen.getByRole('form', { name: 'Edit School' })
    fireEvent.change(within(form).getByLabelText('Link'), { target: { value: 'https://nowhere.test/x.ics' } })
    fireEvent.click(within(form).getByRole('button', { name: 'Save' }))
    expect(await within(form).findByText('Could not reach the calendar URL')).toBeTruthy()
    expect((within(form).getByLabelText('Link') as HTMLInputElement).value).toBe('https://nowhere.test/x.ics')
  })

  it('the family calendar has no link; pausing a feed sends enabled: false; cancel changes nothing', async () => {
    const calls = mockApi({ 'GET /calendar/sources': [FAMILY, SCHOOL], 'PATCH /calendar/sources/sch': { ...SCHOOL, enabled: false } })
    renderPage()
    await screen.findByText('School')
    fireEvent.click(screen.getByRole('button', { name: 'Edit Family Calendar' }))
    const family = screen.getByRole('form', { name: 'Edit Family Calendar' })
    expect(within(family).queryByLabelText('Link')).toBeNull()
    expect((within(family).getByRole('button', { name: 'Save' }) as HTMLButtonElement).disabled).toBe(true)
    fireEvent.click(within(family).getByRole('button', { name: 'Cancel' }))
    fireEvent.click(screen.getByRole('button', { name: 'Edit School' }))
    const school = screen.getByRole('form', { name: 'Edit School' })
    fireEvent.click(within(school).getByLabelText('Keep syncing'))
    fireEvent.click(within(school).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(calls.find((c) => c.method === 'PATCH')?.body).toEqual({ enabled: false }))
  })
})
