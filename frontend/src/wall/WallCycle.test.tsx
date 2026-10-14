import { act, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WallCycle from './WallCycle'

let calendarRenders = 0
vi.mock('./WallSevenDayStrip', () => ({ default: () => { calendarRenders += 1; return <div>calendar panel</div> } }))
vi.mock('./WallRoutines', () => ({ default: () => <div>routines panel</div> }))
vi.mock('./WallProgress', () => ({ default: () => <div>progress panel</div> }))
vi.mock('./WallBirthdays', () => ({ default: () => <div>birthdays panel</div> }))

// A routine from 06:00 Detroit time (10:00Z), two 15-minute steps: on the wall from 05:30 to 06:30.
const MORNING = { id: 'r1', name: 'Morning', start_time: '06:00', assigned_name: null, assigned_color: null,
  steps: [{ instance_id: 's1', title: 'Teeth', minutes: 15, status: 'pending' }, { instance_id: 's2', title: 'Dress', minutes: 15, status: 'pending' }] }
let runs: unknown[] = []
vi.mock('../api/wall', () => ({ useWallRoutines: () => ({ data: runs }) }))

const at = (iso: string) => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
  vi.setSystemTime(new Date(iso))
}

describe('WallCycle', () => {
  beforeEach(() => { calendarRenders = 0; runs = [MORNING] })
  afterEach(() => vi.useRealTimers())

  it('renders the active panel with a live countdown', () => {
    at('2026-10-20T10:00:00Z')
    render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" />)
    expect(screen.getByText('Calendar')).toBeTruthy()
    expect(screen.getByLabelText('Next wall panel').textContent).toContain('20s')
    act(() => vi.advanceTimersByTime(21_000))
    expect(screen.getByText('Routines')).toBeTruthy()
    expect(screen.getByText('routines panel')).toBeTruthy()
  })

  it('shows progress and birthdays together on the progress panel', () => {
    at('2026-10-20T10:00:00Z')
    render(<WallCycle startedAt={Date.now() - 40_000} timeZone="America/Detroit" />)
    expect(screen.getByText('Progress')).toBeTruthy()
    expect(screen.getByText('progress panel')).toBeTruthy()
    expect(screen.getByText('birthdays panel')).toBeTruthy()
  })

  it('skips the routines panel when no routine is on the wall', () => {
    at('2026-10-20T16:00:00Z')  // noon in Detroit: the morning routine is long over
    render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" />)
    expect(screen.getByText('Calendar')).toBeTruthy()
    act(() => vi.advanceTimersByTime(21_000))
    expect(screen.getByText('Progress')).toBeTruthy()
    expect(screen.queryByText('Routines')).toBeNull()
    runs = []
    act(() => vi.advanceTimersByTime(20_000))
    expect(screen.getByText('Calendar')).toBeTruthy()
  })

  it('ticks the countdown without redrawing the panel underneath', () => {
    at('2026-10-20T10:00:00Z')
    render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" />)
    const first = calendarRenders
    act(() => vi.advanceTimersByTime(5_000))
    expect(screen.getByLabelText('Next wall panel').textContent).toContain('15s')
    expect(calendarRenders).toBe(first)
  })
})
