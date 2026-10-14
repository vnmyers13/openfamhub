import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WallCycle from './WallCycle'
import type { WallDashboardConfig } from '../api/wall'

let pageRenders = 0
vi.mock('./WallDashboard', () => ({ WallDashboardPageView: ({ page }: { page: { name: string } }) => { pageRenders += 1; return <div>{page.name} dashboard cards</div> } }))

const dashboard: WallDashboardConfig = {
  pages: [
    { name: 'Today', duration_seconds: 45, widgets: [{ key: 'events', size: 'wide' }] },
    { name: 'Family', duration_seconds: 15, widgets: [{ key: 'progress', size: 'wide' }] },
  ],
}

describe('WallCycle', () => {
  afterEach(() => vi.useRealTimers())

  it('renders the active panel with a live countdown', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-20T10:00:00Z'))
    render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" dashboard={dashboard} />)
    expect(screen.getByText('Today')).toBeTruthy()
    expect(screen.getByText('Today dashboard cards')).toBeTruthy()
    expect(screen.getByLabelText('Next wall panel').textContent).toContain('45s')
    act(() => vi.advanceTimersByTime(46_000))
    expect(screen.getByText('Family')).toBeTruthy()
    expect(screen.getByText('Family dashboard cards')).toBeTruthy()
    expect(screen.getByLabelText('Next wall panel').textContent).toContain('14s')
  })

  it('renders an empty dashboard message when no pages are configured', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-20T10:00:00Z'))
    render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" dashboard={{ pages: [] }} />)
    expect(screen.getByText('No wall dashboard pages configured.')).toBeTruthy()
  })

  it('ticks the countdown without redrawing the page underneath (a Pi redraws slowly)', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-20T10:00:00Z'))
    render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" dashboard={dashboard} />)
    const first = pageRenders
    act(() => vi.advanceTimersByTime(5_000))
    expect(screen.getByLabelText('Next wall panel').textContent).toContain('40s')
    expect(pageRenders).toBe(first)
  })

  it("always shows the family's time in the header bar, with any extra clocks", () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-21T03:30:00Z'))  // Tue 23:30 in Detroit
    render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" dashboard={dashboard}
      clocks={[{ label: 'Grandma', timezone: 'Europe/London' }]} />)
    const header = screen.getByTestId('wall-header')
    expect(header.querySelector('[data-testid="wall-time"]')?.textContent).toBe('23:30')
    expect(header.textContent).toContain('Tuesday, October 20')
    expect(header.querySelector('[data-testid="wall-extra-clock"]')?.textContent).toBe('Grandma04:30 Wed')
  })
})
