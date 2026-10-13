import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../test/api'
import WallSlideshow from './WallSlideshow'

const photo = (id: string) => ({ id, kind: 'photo', width: 1920, height: 1280, duration_s: null,
  wall_url: `/api/wall/media/${id}/wall`, thumb_url: `/api/wall/media/${id}/thumb` })
const video = (id: string) => ({ ...photo(id), kind: 'video', duration_s: 3 })

function renderShow(props = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><WallSlideshow {...props} /></QueryClientProvider>)
}

const shown = () => (screen.queryByTestId('wall-slide') as HTMLImageElement | null)?.getAttribute('src')

describe('WallSlideshow', () => {
  it('shows the logo when there is nothing to show', async () => {
    mockApi({ 'GET /wall/media': [] })
    renderShow()
    expect(await screen.findByText('OpenFamHub')).toBeTruthy()
    expect(screen.queryByTestId('wall-slide')).toBeNull()
  })

  it('shows every photo before repeating any (Phase 3b)', async () => {
    const ids = ['a', 'b', 'c', 'd']
    mockApi({ 'GET /wall/media': ids.map(photo) })
    renderShow({ photoMs: 20 })
    const seen: string[] = []
    await waitFor(() => {
      const src = shown()
      if (src && seen[seen.length - 1] !== src) seen.push(src)
      expect(seen.length).toBeGreaterThanOrEqual(ids.length)
    }, { timeout: 3000, interval: 5 })
    expect(new Set(seen.slice(0, ids.length)).size).toBe(ids.length)
  })

  it('plays a video muted to the end, then moves on', async () => {
    // With random() = 0 each new item joins the front of the round, so the
    // last listed item (the video) plays first.
    mockApi({ 'GET /wall/media': [photo('p'), video('v')] })
    renderShow({ photoMs: 60_000, random: () => 0 })
    const first = (await screen.findByTestId('wall-slide')) as HTMLVideoElement
    expect(first.tagName).toBe('VIDEO')
    expect(first.getAttribute('src')).toBe('/api/wall/media/v/wall')
    expect(first.muted).toBe(true)
    act(() => {
      fireEvent(first, new Event('ended'))
    })
    await waitFor(() => expect(shown()).toBe('/api/wall/media/p/wall'))
    expect(screen.getByTestId('wall-slide').tagName).toBe('IMG')
  })

  it('skips a video that fails to load', async () => {
    mockApi({ 'GET /wall/media': [video('v1'), video('v2')] })
    renderShow()
    const first = await screen.findByTestId('wall-slide')
    const before = first.getAttribute('src')
    act(() => {
      fireEvent(first, new Event('error'))
    })
    await waitFor(() => expect(shown()).not.toBe(before))
  })

  it('restarts a lone video when it ends', async () => {
    mockApi({ 'GET /wall/media': [video('only')] })
    renderShow()
    const first = await screen.findByTestId('wall-slide')
    act(() => {
      fireEvent(first, new Event('ended'))
    })
    await waitFor(() => expect(screen.getByTestId('wall-slide')).not.toBe(first))
    expect(shown()).toBe('/api/wall/media/only/wall')
  })
})
