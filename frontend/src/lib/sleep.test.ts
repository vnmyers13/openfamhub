import { describe, expect, it } from 'vitest'
import { isAsleep, minutesInZone } from './sleep'

// vitest pins the process to America/Detroit; the schedule must follow the
// *family* zone, not the device's.
const overnight = { enabled: true, off: '22:00', on: '06:30' }

describe('minutesInZone', () => {
  it('reads the wall-clock time in a given zone', () => {
    const t = new Date('2026-10-20T12:15:00Z')
    expect(minutesInZone(t, 'UTC')).toBe(12 * 60 + 15)
    expect(minutesInZone(t, 'America/Detroit')).toBe(8 * 60 + 15)
    expect(minutesInZone(t, 'Asia/Kolkata')).toBe(17 * 60 + 45)
  })

  it('falls back to UTC for an unknown zone', () => {
    expect(minutesInZone(new Date('2026-10-20T12:15:00Z'), 'Not/AZone')).toBe(12 * 60 + 15)
  })
})

describe('isAsleep', () => {
  it('is never asleep when the schedule is off', () => {
    expect(isAsleep(new Date('2026-10-20T03:00:00Z'), { ...overnight, enabled: false }, 'UTC')).toBe(false)
  })

  it('handles an overnight window', () => {
    const tz = 'America/Detroit' // EDT, UTC-4
    expect(isAsleep(new Date('2026-10-21T01:59:00Z'), overnight, tz)).toBe(false) // 21:59
    expect(isAsleep(new Date('2026-10-21T02:00:00Z'), overnight, tz)).toBe(true) // 22:00
    expect(isAsleep(new Date('2026-10-21T08:00:00Z'), overnight, tz)).toBe(true) // 04:00
    expect(isAsleep(new Date('2026-10-21T10:30:00Z'), overnight, tz)).toBe(false) // 06:30, back on
  })

  it('handles a daytime window', () => {
    const nap = { enabled: true, off: '09:00', on: '15:00' }
    expect(isAsleep(new Date('2026-10-20T12:00:00Z'), nap, 'UTC')).toBe(true)
    expect(isAsleep(new Date('2026-10-20T16:00:00Z'), nap, 'UTC')).toBe(false)
  })

  it('uses the family zone, not the device zone', () => {
    // 22:30 in London (BST) is 17:30 in Detroit, where this device thinks it is.
    expect(isAsleep(new Date('2026-10-24T21:30:00Z'), overnight, 'Europe/London')).toBe(true)
    expect(isAsleep(new Date('2026-10-24T21:30:00Z'), overnight, 'America/Detroit')).toBe(false)
  })

  it('keeps local times across a DST change', () => {
    // London leaves BST on 25 Oct 2026. 21:30 UTC is 22:30 the day before
    // (asleep) but 21:30 the day after (awake): the schedule follows the clock.
    expect(isAsleep(new Date('2026-10-24T21:30:00Z'), overnight, 'Europe/London')).toBe(true)
    expect(isAsleep(new Date('2026-10-25T21:30:00Z'), overnight, 'Europe/London')).toBe(false)
    expect(isAsleep(new Date('2026-10-25T22:00:00Z'), overnight, 'Europe/London')).toBe(true)
    // Detroit leaves EDT on 1 Nov 2026: 06:30 local is 10:30Z before and 11:30Z after.
    expect(isAsleep(new Date('2026-10-31T10:45:00Z'), overnight, 'America/Detroit')).toBe(false)
    expect(isAsleep(new Date('2026-11-02T10:45:00Z'), overnight, 'America/Detroit')).toBe(true)
  })
})
