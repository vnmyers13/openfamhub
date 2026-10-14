import { describe, expect, it } from 'vitest'
import { dayLabel, minutesLabel, shiftWeek, toLines, weekLabel } from './meals'

describe('meal helpers', () => {
  it('moves by whole weeks', () => {
    expect(shiftWeek('2026-10-12', 1)).toBe('2026-10-19')
    expect(shiftWeek('2026-11-02', -1)).toBe('2026-10-26')
  })
  it('labels days and weeks', () => {
    expect(dayLabel('2026-10-12')).toBe('Mon 12')
    expect(weekLabel('2026-10-12')).toBe('Oct 12 – 18')
    expect(weekLabel('2026-10-26')).toBe('Oct 26 – Nov 1')
  })
  it('labels minutes', () => {
    expect(minutesLabel(45)).toBe('45 min')
    expect(minutesLabel(75)).toBe('1 hr 15 min')
    expect(minutesLabel(120)).toBe('2 hr')
    expect(minutesLabel(null)).toBeNull()
    expect(minutesLabel(0)).toBeNull()
  })
  it('splits lines', () => {
    expect(toLines(' 1 egg \n\n2 cups milk\n')).toEqual(['1 egg', '2 cups milk'])
  })
})
