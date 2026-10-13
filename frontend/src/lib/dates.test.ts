import { describe, expect, it } from 'vitest'
import { allDayEndIso, allDayStartIso, eventDayKeys, eventEnd, eventStart } from './dates'

// vitest.config.ts pins TZ=America/Detroit (UTC-4 in October).

describe('all-day events', () => {
  const allDay = { start_dt: '2026-10-07T00:00:00+00:00', end_dt: '2026-10-09T00:00:00+00:00', all_day: true }

  it('stay on their calendar date west of UTC', () => {
    expect(eventStart(allDay).toString()).toContain('Wed Oct 07 2026 00:00')
  })

  it('list every day up to the exclusive end', () => {
    expect(eventDayKeys(allDay)).toEqual(['2026-10-07', '2026-10-08'])
  })

  it('treat an old inclusive 23:59 end as one day', () => {
    const legacy = { start_dt: '2026-10-07T00:00:00+00:00', end_dt: '2026-10-07T23:59:59+00:00', all_day: true }
    expect(eventDayKeys(legacy)).toEqual(['2026-10-07'])
    expect(eventEnd(legacy).getTime() - eventStart(legacy).getTime()).toBe(24 * 3600 * 1000)
  })

  it('round-trip through the date inputs', () => {
    expect(allDayStartIso('2026-10-07')).toBe('2026-10-07T00:00:00Z')
    expect(allDayEndIso('2026-10-08')).toBe('2026-10-09T00:00:00Z')
  })
})

describe('timed events', () => {
  it('show on their local start day', () => {
    // 01:00 UTC on the 8th is 21:00 on the 7th in Detroit.
    const e = { start_dt: '2026-10-08T01:00:00+00:00', end_dt: '2026-10-08T02:00:00+00:00', all_day: false }
    expect(eventDayKeys(e)).toEqual(['2026-10-07'])
  })

  it('show on every local day they overlap (#9)', () => {
    // 22:00 on the 7th to 02:00 on the 8th, Detroit time.
    const e = { start_dt: '2026-10-08T02:00:00+00:00', end_dt: '2026-10-08T06:00:00+00:00', all_day: false }
    expect(eventDayKeys(e)).toEqual(['2026-10-07', '2026-10-08'])
  })

  it('span several days when they run that long', () => {
    // Fri 18:00 to Sun 10:00 local.
    const e = { start_dt: '2026-10-09T22:00:00+00:00', end_dt: '2026-10-11T14:00:00+00:00', all_day: false }
    expect(eventDayKeys(e)).toEqual(['2026-10-09', '2026-10-10', '2026-10-11'])
  })

  it('do not spill onto the next day when they end exactly at midnight', () => {
    // 22:00 to 00:00 local.
    const e = { start_dt: '2026-10-08T02:00:00+00:00', end_dt: '2026-10-08T04:00:00+00:00', all_day: false }
    expect(eventDayKeys(e)).toEqual(['2026-10-07'])
  })

  it('still show a zero-length event on its day', () => {
    const e = { start_dt: '2026-10-07T15:00:00+00:00', end_dt: '2026-10-07T15:00:00+00:00', all_day: false }
    expect(eventDayKeys(e)).toEqual(['2026-10-07'])
  })
})
