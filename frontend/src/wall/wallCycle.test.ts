import { describe, expect, it } from 'vitest'
import { cycleState } from './wallCycle'

describe('cycleState', () => {
  it('selects the active panel and live countdown from elapsed time', () => {
    const panels = [
      { id: 'calendar', label: 'Calendar', durationSeconds: 20 },
      { id: 'routines', label: 'Routines', durationSeconds: 10 },
    ]
    expect(cycleState(panels, 5_000, 0)).toMatchObject({ index: 0, secondsLeft: 15, elapsedInPanel: 5 })
    expect(cycleState(panels, 21_000, 0)).toMatchObject({ index: 1, secondsLeft: 9, elapsedInPanel: 1 })
    expect(cycleState(panels, 31_000, 0)).toMatchObject({ index: 0, secondsLeft: 19, elapsedInPanel: 1 })
  })

  it('handles an empty panel list without crashing', () => {
    expect(cycleState([], 10_000, 0)).toEqual({ panel: null, index: -1, secondsLeft: 0, elapsedInPanel: 0 })
  })

  it('uses configured page durations for wall dashboard pages', () => {
    const panels = [
      { id: 'page-0', label: 'Today', durationSeconds: 45 },
      { id: 'page-1', label: 'Family', durationSeconds: 15 },
    ]

    expect(cycleState(panels, 44_000, 0)).toMatchObject({ index: 0, secondsLeft: 1 })
    expect(cycleState(panels, 46_000, 0)).toMatchObject({ index: 1, secondsLeft: 14 })
    expect(cycleState(panels, 61_000, 0)).toMatchObject({ index: 0, secondsLeft: 44 })
  })
})

describe('routineShowsOnWall', () => {
  it('is true from half an hour before a routine until it ends or is done', async () => {
    const { routineShowsOnWall } = await import('../lib/routine')
    const run = { start_time: '06:00', steps: [{ minutes: 15, status: 'pending' }, { minutes: 15, status: 'pending' }] }
    const tz = 'America/Detroit'  // 06:00 there is 10:00Z in October
    expect(routineShowsOnWall(run, new Date('2026-10-20T09:20:00Z'), tz)).toBe(false)
    expect(routineShowsOnWall(run, new Date('2026-10-20T09:31:00Z'), tz)).toBe(true)
    expect(routineShowsOnWall(run, new Date('2026-10-20T10:20:00Z'), tz)).toBe(true)
    expect(routineShowsOnWall(run, new Date('2026-10-20T10:31:00Z'), tz)).toBe(false)
    const done = { ...run, steps: run.steps.map((s) => ({ ...s, status: 'completed' })) }
    expect(routineShowsOnWall(done, new Date('2026-10-20T10:20:00Z'), tz)).toBe(false)
  })
})
