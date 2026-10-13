import { describe, expect, it } from 'vitest'
import { routineTimeline } from './routine'

const steps = [{ minutes: 5 }, { minutes: 15 }, { minutes: 3 }] // 07:00-07:05-07:20-07:23

describe('routineTimeline', () => {
  const at = (iso: string, tz = 'America/Detroit') => routineTimeline(new Date(iso), '07:00', steps, tz)

  it('is "before" ahead of the start, with time to go', () => {
    expect(at('2026-10-20T10:50:00Z')).toEqual({ phase: 'before', index: 0, secondsLeft: 600 }) // 06:50
  })

  it('tracks the current step and its countdown', () => {
    expect(at('2026-10-20T11:00:00Z')).toEqual({ phase: 'during', index: 0, secondsLeft: 300 }) // 07:00
    expect(at('2026-10-20T11:06:30Z')).toEqual({ phase: 'during', index: 1, secondsLeft: 810 }) // 07:06:30
    expect(at('2026-10-20T11:22:00Z')).toEqual({ phase: 'during', index: 2, secondsLeft: 60 }) // 07:22
  })

  it('is "after" once the last step ends', () => {
    expect(at('2026-10-20T11:23:00Z')).toEqual({ phase: 'after', index: 2, secondsLeft: 0 })
  })

  it('reads the start time in the family timezone', () => {
    // 11:00Z is 07:00 in Detroit (EDT) but 12:00 in London (BST).
    expect(at('2026-10-20T11:00:00Z', 'Europe/London')?.phase).toBe('after')
    expect(at('2026-10-20T06:02:00Z', 'Europe/London')).toEqual({ phase: 'during', index: 0, secondsLeft: 180 })
  })

  it('has no timeline without a start time', () => {
    expect(routineTimeline(new Date(), null, steps, 'UTC')).toBeNull()
  })
})
