import { act, renderHook } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode, type ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useWallWebSocket } from './useWallWebSocket'

class FakeSocket {
  static instances: FakeSocket[] = []
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  onerror: (() => void) | null = null
  closed = false
  url: string
  constructor(url: string) {
    this.url = url
    FakeSocket.instances.push(this)
  }
  close() {
    if (this.closed) return
    this.closed = true
    // Browsers fire close asynchronously, after the caller's cleanup ran.
    queueMicrotask(() => this.onclose?.())
  }
}

const open = () => FakeSocket.instances.filter((s) => !s.closed)

function setup({ strict = false } = {}) {
  const client = new QueryClient()
  const invalidate = vi.spyOn(client, 'invalidateQueries')
  const wrapper = ({ children }: { children: ReactNode }) => {
    const tree = <QueryClientProvider client={client}>{children}</QueryClientProvider>
    return strict ? <StrictMode>{tree}</StrictMode> : tree
  }
  const hook = renderHook(() => useWallWebSocket(), { wrapper })
  return { ...hook, invalidate }
}

describe('useWallWebSocket (#11)', () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.useFakeTimers()
    vi.stubGlobal('WebSocket', FakeSocket)
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('refreshes wall events when the server says the calendar changed', () => {
    const { invalidate } = setup()
    act(() => open()[0].onmessage?.({ data: JSON.stringify({ type: 'calendar_updated' }) }))
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['wall-events'] })
  })

  it('refreshes media and settings when the server says they changed', () => {
    const { invalidate } = setup()
    act(() => open()[0].onmessage?.({ data: JSON.stringify({ type: 'media_updated' }) }))
    act(() => open()[0].onmessage?.({ data: JSON.stringify({ type: 'settings_updated' }) }))
    act(() => open()[0].onmessage?.({ data: JSON.stringify({ type: 'chores_updated' }) }))
    act(() => open()[0].onmessage?.({ data: JSON.stringify({ type: 'rewards_updated' }) }))
    act(() => open()[0].onmessage?.({ data: JSON.stringify({ type: 'something_else' }) }))
    act(() => open()[0].onmessage?.({ data: 'not json' }))
    expect(invalidate.mock.calls).toEqual([[{ queryKey: ['wall-media'] }], [{ queryKey: ['wall-session'] }],
      [{ queryKey: ['wall-routines'] }], [{ queryKey: ['wall-progress'] }], [{ queryKey: ['wall-progress'] }]])
  })

  it('reconnects after the server drops the connection', async () => {
    setup()
    await act(async () => {
      open()[0].close()
      await Promise.resolve()
    })
    act(() => {
      vi.advanceTimersByTime(10_000)
    })
    expect(FakeSocket.instances).toHaveLength(2)
    expect(open()).toHaveLength(1)
  })

  it('does not reconnect after unmount', async () => {
    const { unmount } = setup()
    unmount()
    await act(async () => {
      await Promise.resolve() // let the async close event fire
      vi.advanceTimersByTime(60_000)
    })
    expect(FakeSocket.instances).toHaveLength(1)
    expect(open()).toHaveLength(0)
  })

  it('leaves exactly one live socket under StrictMode', async () => {
    const { unmount } = setup({ strict: true })
    await act(async () => {
      await Promise.resolve()
      vi.advanceTimersByTime(60_000)
    })
    expect(open()).toHaveLength(1)
    unmount()
    await act(async () => {
      await Promise.resolve()
      vi.advanceTimersByTime(60_000)
    })
    expect(open()).toHaveLength(0)
  })
})
