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
})
