import { describe, expect, it } from 'vitest'
import { describeRepeat } from './repeat'

describe('describeRepeat', () => {
  it.each([
    [null, '2026-10-14', 'Once, Wed Oct 14'],
    [{ every: 'none' }, '2026-10-14', 'Once, Wed Oct 14'],
    [{ every: 'day' }, '2026-10-01', 'Every day'],
    [{ every: 'day', interval: 3 }, '2026-10-01', 'Every 3 days'],
    [{ every: 'week' }, '2026-10-01', 'Every Thu'],
    [{ every: 'week', weekdays: ['mo', 'th'] }, '2026-10-01', 'Every Mon & Thu'],
    [{ every: 'week', interval: 2, weekdays: ['sa'] }, '2026-10-01', 'Every 2 weeks on Sat'],
    [{ every: 'week', weekdays: ['mo', 'tu', 'we', 'th', 'fr'] }, '2026-10-01', 'Weekdays'],
    [{ every: 'month', month_day: 15 }, '2026-10-01', 'Monthly on the 15th'],
    [{ every: 'month', month_day: 1 }, '2026-10-01', 'Monthly on the 1st'],
    [{ every: 'month', month_day: 22 }, '2026-10-01', 'Monthly on the 22nd'],
    [{ every: 'month', month_day: -1 }, '2026-10-01', 'Monthly on the last day'],
    [{ every: 'month', interval: 3 }, '2026-10-03', 'Every 3 months on the 3rd'],
  ])('%j from %s', (repeat, start, text) => {
    expect(describeRepeat(repeat as never, start)).toBe(text)
  })
})
