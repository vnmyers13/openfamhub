import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WallCycle from './WallCycle.tsx'
import type { WallDashboardConfig } from '../api/wall'

vi.mock('./WallDashboard', () => ({ WallDashboardPageView: ({ page }: { page: { name: string } }) => <div>{page.name} dashboard cards</div> }))

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
})
