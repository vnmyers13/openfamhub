import { describe, expect, it } from 'vitest'
import { familyDayRange } from './wallDashboardDates'

describe('familyDayRange', () => {
  it('uses the family timezone rather than the display timezone', () => {
    const { start, end, dateKey } = familyDayRange(new Date('2026-10-14T02:30:00Z'), 'America/Detroit')

    expect(dateKey).toBe('2026-10-13')
    expect(start.toISOString()).toBe('2026-10-13T04:00:00.000Z')
    expect(end.toISOString()).toBe('2026-10-14T04:00:00.000Z')
  })

  it('uses the offset after a daylight-saving transition', () => {
    const { start, end, dateKey } = familyDayRange(new Date('2026-11-01T18:00:00Z'), 'America/Detroit')

    expect(dateKey).toBe('2026-11-01')
    expect(start.toISOString()).toBe('2026-11-01T04:00:00.000Z')
    expect(end.toISOString()).toBe('2026-11-02T05:00:00.000Z')
  })
})
