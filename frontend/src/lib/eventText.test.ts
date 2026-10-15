import { describe, expect, it } from 'vitest'
import { mapsUrl, whenText } from './eventText'

const ev = (start_dt: string, end_dt: string, all_day = false) => ({
  id: 'e', source_id: 's', title: 'x', start_dt, end_dt, all_day, location: null, description: null, created_by: null,
  source_color_hex: '#000', created_at: null, updated_at: null,
})
const local = (s: string) => new Date(s).toISOString()

describe('whenText', () => {
  it('says a timed event on one day, or across days', () => {
    expect(whenText(ev(local('2026-10-15T15:00'), local('2026-10-15T16:30')))).toBe('Thu 15 Oct, 3:00 PM – 4:30 PM')
    expect(whenText(ev(local('2026-10-15T20:00'), local('2026-10-16T09:00')))).toBe('Thu 15 Oct 8:00 PM – Fri 16 Oct 9:00 AM')
  })
  it('says all-day events by their dates, with an exclusive end', () => {
    expect(whenText(ev('2026-10-15T00:00:00+00:00', '2026-10-16T00:00:00+00:00', true))).toBe('Thu 15 Oct, all day')
    expect(whenText(ev('2026-10-15T00:00:00+00:00', '2026-10-18T00:00:00+00:00', true))).toBe('Thu 15 Oct – Sat 17 Oct, all day')
  })
})

describe('mapsUrl', () => {
  it('searches for the place, safely encoded', () => {
    expect(mapsUrl('Riverside Park, Field 3 & 4')).toBe('https://www.google.com/maps/search/?api=1&query=Riverside%20Park%2C%20Field%203%20%26%204')
  })
})
