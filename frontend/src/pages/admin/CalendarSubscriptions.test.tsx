import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import CalendarSubscriptions from './CalendarSubscriptions'

const TITLES_SUB = { id: 't1', family_id: 'family', kind: 'titles' as const, active: true, last_published_at: '2026-10-20T10:00:00+00:00', last_error: null }
const FULL_SUB = { id: 'f1', family_id: 'family', kind: 'full' as const, active: false, last_published_at: '2026-10-15T08:00:00+00:00', last_error: 'Could not reach the calendar relay' }

const renderPage = () => renderApp(<CalendarSubscriptions />)

describe('CalendarSubscriptions', () => {
  it('creates a titles feed, presents the URL for copying, then removes it when the dialog closes', async () => {
    mockApi({
      'GET /calendar/subscriptions': [],
      'POST /calendar/subscriptions/titles': { kind: 'titles', subscription_url: 'https://relay.example/secret' },
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Create titles subscription' }))
    expect(await screen.findByText('https://relay.example/secret')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Close' }))
    expect(screen.queryByText('https://relay.example/secret')).toBeNull()
  })

  it('creates a full feed and shows the URL dialog', async () => {
    mockApi({
      'GET /calendar/subscriptions': [],
      'POST /calendar/subscriptions/full': { kind: 'full', subscription_url: 'https://relay.example/full-secret' },
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Create full subscription' }))
    expect(await screen.findByText('https://relay.example/full-secret')).toBeTruthy()
  })

  it('shows delivery error/status and rotates a feed, showing the new URL', async () => {
    const confirm = vi.fn(() => true)
    vi.stubGlobal('confirm', confirm)
    try {
      mockApi({
        'GET /calendar/subscriptions': [TITLES_SUB, FULL_SUB],
        'POST /calendar/subscriptions/titles/rotate': { kind: 'titles', subscription_url: 'https://relay.example/new-titles' },
      })
      renderPage()
      expect(await screen.findByText('titles')).toBeTruthy()
      expect(screen.getByText('full')).toBeTruthy()

      // Error shown for the full subscription (split across "Error:" and the message)
      expect(await screen.findByText(/Could not reach the calendar relay/)).toBeTruthy()

      // Rotating titles: shows the new URL in the dialog
      fireEvent.click(await screen.findByRole('button', { name: 'Rotate titles' }))
      expect(await screen.findByText('https://relay.example/new-titles')).toBeTruthy()
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('revokes a subscription after confirming, and not without', async () => {
    const calls = mockApi({
      'GET /calendar/subscriptions': [TITLES_SUB],
    })
    const confirm = vi.fn(() => false)
    vi.stubGlobal('confirm', confirm)
    try {
      renderPage()
      await screen.findByText('titles')
      fireEvent.click(screen.getByRole('button', { name: 'Revoke titles' }))
      expect(calls.some((c) => c.method === 'DELETE')).toBe(false)
      confirm.mockReturnValue(true)
      fireEvent.click(screen.getByRole('button', { name: 'Revoke titles' }))
      await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
    } finally {
      vi.unstubAllGlobals()
    }
  })

  it('reveals a subscription URL, shows it in a dialog, and clears on close', async () => {
    const calls = mockApi({
      'GET /calendar/subscriptions': [TITLES_SUB],
      'POST /calendar/subscriptions/titles/reveal': { kind: 'titles', subscription_url: 'https://relay.example/revealed' },
    })
    renderPage()
    await screen.findByText('titles')
    fireEvent.click(screen.getByRole('button', { name: 'Reveal titles' }))
    expect(await screen.findByText('https://relay.example/revealed')).toBeTruthy()
    expect(calls.find((c) => c.method === 'POST' && c.url === '/calendar/subscriptions/titles/reveal')).toBeTruthy()
  })

  it('shows a delivery error when the relay is unavailable during create', async () => {
    mockApi({
      'GET /calendar/subscriptions': [],
      'POST /calendar/subscriptions/titles': () => { throw apiError(502, 'Could not reach the calendar relay') },
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Create titles subscription' }))
    expect(await screen.findByText(/Could not reach the calendar relay/)).toBeTruthy()
  })

  it('shows an empty state when no subscriptions exist', async () => {
    mockApi({ 'GET /calendar/subscriptions': [] })
    renderPage()
    expect(await screen.findByText(/No subscriptions yet/)).toBeTruthy()
  })

  it('lists subscriptions without exposing URLs', async () => {
    mockApi({ 'GET /calendar/subscriptions': [TITLES_SUB, FULL_SUB] })
    renderPage()
    expect(await screen.findByText('titles')).toBeTruthy()
    expect(screen.getByText('full')).toBeTruthy()
    // No URL text should appear in the listing
    expect(screen.queryByText(/https:\/\/.+/)).toBeNull()
  })

  it('shows active/inactive badges correctly', async () => {
    mockApi({ 'GET /calendar/subscriptions': [TITLES_SUB, FULL_SUB] })
    renderPage()
    expect(await screen.findByText('Active')).toBeTruthy()
    expect(screen.getByText('Inactive')).toBeTruthy()
  })

  it('copy button copies the URL to clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, writable: true })
    try {
      mockApi({
        'GET /calendar/subscriptions': [TITLES_SUB],
        'POST /calendar/subscriptions/titles': { kind: 'titles', subscription_url: 'https://relay.example/copy-me' },
      })
      renderPage()
      // Existing active subscription -> "Recreate" button
      fireEvent.click(await screen.findByRole('button', { name: 'Recreate titles subscription' }))
      await waitFor(() => screen.getByText('https://relay.example/copy-me'))
      const copyBtn = screen.getByRole('button', { name: 'Copy' })
      fireEvent.click(copyBtn)
      await waitFor(() => expect(writeText).toHaveBeenCalledWith('https://relay.example/copy-me'))
    } finally {
      Object.defineProperty(navigator, 'clipboard', { value: undefined })
    }
  })

  it('shows an error when reveal fails for an inactive subscription', async () => {
    mockApi({
      'GET /calendar/subscriptions': [FULL_SUB],
      'POST /calendar/subscriptions/full/reveal': () => { throw apiError(400, 'Subscription is not active; create it first') },
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Reveal full' }))
    expect(await screen.findByText(/Subscription is not active/)).toBeTruthy()
  })

  it('shows an error when rotate fails for a nonexistent subscription', async () => {
    mockApi({
      'GET /calendar/subscriptions': [],
      'POST /calendar/subscriptions/full': () => { throw apiError(404, 'Subscription not found') },
    })
    renderPage()
    fireEvent.click(await screen.findByRole('button', { name: 'Create full subscription' }))
    expect(await screen.findByText(/Subscription not found/)).toBeTruthy()
  })
})
