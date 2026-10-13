import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiError, mockApi } from '../../test/api'
import { renderApp } from '../../test/render'
import WallDisplays from './WallDisplays'

const KITCHEN = { id: 'd1', name: 'Kitchen', last_seen_at: null, created_at: '2026-10-12T10:00:00+00:00' }

describe('WallDisplays', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('creates a pairing link once and copies it', async () => {
    const writeText = vi.fn(async () => {})
    vi.stubGlobal('navigator', { ...navigator, clipboard: { writeText } })
    const calls = mockApi({ 'GET /wall/devices': [], 'POST /wall/devices': { ...KITCHEN, token: 'tok en/1' } })
    renderApp(<WallDisplays />)
    const name = screen.getByPlaceholderText('Display name, e.g. Kitchen') as HTMLInputElement
    fireEvent.change(name, { target: { value: '  Kitchen  ' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create pairing link' }))
    const url = `${window.location.origin}/wall?token=${encodeURIComponent('tok en/1')}`
    expect(await screen.findByText(url)).toBeTruthy()
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ name: 'Kitchen' })
    expect(name.value).toBe('')
    fireEvent.click(screen.getByRole('button', { name: 'Copy' }))
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeTruthy()
    expect(writeText).toHaveBeenCalledWith(url)
  })

  it('says when a display could not be created', async () => {
    mockApi({ 'GET /wall/devices': [], 'POST /wall/devices': () => { throw apiError(422, 'name must be 1-64 characters') } })
    renderApp(<WallDisplays />)
    fireEvent.change(screen.getByPlaceholderText('Display name, e.g. Kitchen'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Create pairing link' }))
    expect(await screen.findByText('Could not create the display')).toBeTruthy()
  })

  it('unpairs a display after confirming', async () => {
    const calls = mockApi({ 'GET /wall/devices': [KITCHEN], 'DELETE /wall/devices/d1': null })
    vi.stubGlobal('confirm', vi.fn(() => true))
    renderApp(<WallDisplays />)
    expect(await screen.findByText('Kitchen')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: /unpair/i }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE' && c.url === '/wall/devices/d1')).toBe(true))
  })
})
