import { describe, expect, it } from 'vitest'
import { effectivePages, missingWidgets, moveWidget, TEMPLATES, WIDGETS } from './dashboard'

describe('dashboard layout', () => {
  it('uses one default page until someone saves their own', () => {
    const [page] = effectivePages([], true)
    expect(page.widgets.map((w) => w.key)).toEqual(WIDGETS.map((w) => w.key))
    expect(effectivePages([{ name: 'Mine', widgets: [{ key: 'meals', size: 'wide' }] }], true))
      .toEqual([{ name: 'Mine', widgets: [{ key: 'meals', size: 'wide' }] }])
  })
  it("drops admin-only cards for everyone else", () => {
    const [page] = effectivePages([], false)
    expect(page.widgets.some((w) => w.key === 'sync')).toBe(false)
    expect(missingWidgets({ name: 'x', widgets: [] }, false)).not.toContain('sync')
    expect(missingWidgets({ name: 'x', widgets: [] }, true)).toContain('sync')
  })
  it('moves cards and ignores impossible moves', () => {
    const ws = [{ key: 'events', size: 'normal' }, { key: 'meals', size: 'normal' }, { key: 'stars', size: 'normal' }] as const
    expect(moveWidget([...ws], 0, 2).map((w) => w.key)).toEqual(['meals', 'stars', 'events'])
    expect(moveWidget([...ws], 2, 0).map((w) => w.key)).toEqual(['stars', 'events', 'meals'])
    expect(moveWidget([...ws], 1, 5)).toEqual([...ws])
  })
  it('lists what a page is missing', () => {
    expect(missingWidgets(TEMPLATES[3].page, true)).toEqual(['events', 'week', 'my-day', 'chores', 'home', 'stars', 'birthdays', 'sync'])
  })
})
