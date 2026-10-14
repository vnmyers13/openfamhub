import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { WallDashboardPageView } from './WallDashboard'
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

describe('the Clock card', () => {
  afterEach(() => vi.useRealTimers())

  it("shows the family's time, date and extra clocks in a card", () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-21T03:30:00Z'))  // Tue 23:30 in Detroit
    render(<WallDashboardPageView timeZone="America/Detroit" clocks={[{ label: 'Grandma', timezone: 'Europe/London' }]}
      page={{ name: 'Morning', duration_seconds: 30, widgets: [{ key: 'clock', size: 'normal' }] }} />)
    expect(screen.getByTestId('wall-time').textContent).toBe('23:30')
    expect(screen.getByTestId('wall-date').textContent).toBe('Tuesday, October 20')
    expect(screen.getByTestId('wall-extra-clock').textContent).toBe('Grandma04:30 Wed')
  })
})
