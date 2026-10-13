import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { format } from 'date-fns'
import { useToday } from './useToday'

const day = (d: Date) => format(d, 'yyyy-MM-dd HH:mm')

describe('useToday (#8)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    vi.setSystemTime(new Date(2026, 9, 7, 23, 58)) // 23:58 local
  })
  afterEach(() => vi.useRealTimers())

  it('starts at local midnight today', () => {
    const { result } = renderHook(() => useToday())
    expect(day(result.current)).toBe('2026-10-07 00:00')
  })

  it('rolls over after midnight without a reload', () => {
    const { result } = renderHook(() => useToday())
    act(() => {
      vi.advanceTimersByTime(3 * 60 * 1000)
    })
    expect(day(result.current)).toBe('2026-10-08 00:00')
  })

  it('keeps rolling over on later nights', () => {
    const { result } = renderHook(() => useToday())
    act(() => {
      vi.advanceTimersByTime(24 * 3600 * 1000 + 3 * 60 * 1000)
    })
    expect(day(result.current)).toBe('2026-10-09 00:00')
  })

  it('catches up when the page becomes visible again', () => {
    const { result } = renderHook(() => useToday())
    // A sleeping tablet can miss the timer; the clock jumps without it firing.
    vi.setSystemTime(new Date(2026, 9, 8, 7, 0))
    act(() => {
      document.dispatchEvent(new Event('visibilitychange'))
    })
    expect(day(result.current)).toBe('2026-10-08 00:00')
  })

  it('returns a stable value within the same day', () => {
    const { result, rerender } = renderHook(() => useToday())
    const first = result.current
    rerender()
    expect(result.current).toBe(first)
  })

  it('clears its timer on unmount', () => {
    const { unmount } = renderHook(() => useToday())
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})
