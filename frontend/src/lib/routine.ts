import { minutesInZone } from './sleep'

export interface RoutineTimeline {
  phase: 'before' | 'during' | 'after'
  index: number // the step that's current (or next, before the start)
  secondsLeft: number // until the start, or until the current step ends
}

function secondsInZone(now: Date, timeZone: string): number {
  return minutesInZone(now, timeZone) * 60 + now.getUTCSeconds()
}

/**
 * Where a routine is right now: steps run back to back from `startTime`
 * (HH:MM in the family timezone), each lasting its `minutes`.
 */
export function routineTimeline(
  now: Date, startTime: string | null | undefined, steps: { minutes: number }[], timeZone: string,
): RoutineTimeline | null {
  if (!startTime || steps.length === 0) return null
  const [h, m] = startTime.split(':').map(Number)
  const start = (h * 60 + m) * 60
  const t = secondsInZone(now, timeZone)
  if (t < start) return { phase: 'before', index: 0, secondsLeft: start - t }
  let end = start
  for (let i = 0; i < steps.length; i++) {
    end += steps[i].minutes * 60
    if (t < end) return { phase: 'during', index: i, secondsLeft: end - t }
  }
  return { phase: 'after', index: steps.length - 1, secondsLeft: 0 }
}
