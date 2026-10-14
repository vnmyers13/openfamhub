import { act, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import WallCycle from './WallCycle.tsx'

vi.mock('./WallSevenDayStrip', () => ({ default: () => <div>calendar panel</div> }))
vi.mock('./WallRoutines', () => ({ default: () => <div>routines panel</div> }))
vi.mock('./WallProgress', () => ({ default: () => <div>progress panel</div> }))
vi.mock('./WallBirthdays', () => ({ default: () => <div>birthdays panel</div> }))

describe('WallCycle', () => {
  afterEach(() => vi.useRealTimers())

  it('renders the active panel with a live countdown', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-20T10:00:00Z'))
    render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" />)
    expect(screen.getByText('Calendar')).toBeTruthy()
    expect(screen.getByLabelText('Next wall panel').textContent).toContain('20s')
    act(() => vi.advanceTimersByTime(21_000))
    expect(screen.getByText('Routines')).toBeTruthy()
    expect(screen.getByText('routines panel')).toBeTruthy()
  })

  it('shows progress and birthdays together on the progress panel', () => {
    vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
    vi.setSystemTime(new Date('2026-10-20T10:00:00Z'))
    render(<WallCycle startedAt={Date.now() - 40_000} timeZone="America/Detroit" />)
    expect(screen.getByText('Progress')).toBeTruthy()
    expect(screen.getByText('progress panel')).toBeTruthy()
    expect(screen.getByText('birthdays panel')).toBeTruthy()
  })
})
