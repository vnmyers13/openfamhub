import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WallClock from './WallClock'

describe('WallClock', () => {
  afterEach(() => vi.useRealTimers())

  it("shows the family's time and date, whatever zone the display itself is in", () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-21T03:30:00Z'))  // Wed 03:30 UTC = Tue 23:30 in Detroit
    const { unmount } = render(<WallClock timeZone="America/Detroit" />)
    expect(screen.getByTestId('wall-time').textContent).toBe('23:30')
    expect(screen.getByTestId('wall-date').textContent).toBe('Tuesday, October 20')
    unmount()
    render(<WallClock timeZone="Asia/Tokyo" />)
    expect(screen.getByTestId('wall-time').textContent).toBe('12:30')
    expect(screen.getByTestId('wall-date').textContent).toBe('Wednesday, October 21')
  })

  it("falls back to the display's own zone if the family zone is unknown", () => {
    render(<WallClock timeZone="Not/AZone" />)
    expect(screen.getByTestId('wall-time').textContent).toMatch(/^\d{2}:\d{2}$/)
  })

  it('shows extra clocks under the main one, with the day when it differs', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-21T03:30:00Z'))  // Tue 23:30 in Detroit
    render(<WallClock timeZone="America/Detroit" clocks={[
      { label: 'Grandma', timezone: 'Europe/London' }, { label: 'Denver', timezone: 'America/Denver' },
    ]} />)
    const rows = screen.getAllByTestId('wall-extra-clock').map((r) => r.textContent)
    expect(rows).toEqual(['Grandma04:30 Wed', 'Denver21:30'])
  })
})
