import { describe, expect, it } from 'vitest'
import { ShuffleBag } from './shuffle'

// Deterministic "random" so failures are reproducible.
function seeded(seed = 42) {
  let s = seed
  return () => ((s = (s * 1103515245 + 12345) % 2 ** 31) / 2 ** 31)
}

describe('ShuffleBag', () => {
  it('uses every item before repeating any (Phase 3b)', () => {
    const ids = ['a', 'b', 'c', 'd', 'e', 'f', 'g']
    const bag = new ShuffleBag(ids, seeded())
    for (let round = 0; round < 5; round++) {
      const seen = Array.from({ length: ids.length }, () => bag.next())
      expect(new Set(seen).size).toBe(ids.length)
    }
  })

  it('never shows the same item twice in a row across rounds', () => {
    const bag = new ShuffleBag(['a', 'b', 'c'], seeded(7))
    let previous = bag.next()
    for (let i = 0; i < 300; i++) {
      const current = bag.next()
      expect(current).not.toBe(previous)
      previous = current
    }
  })

  it('picks up new items in the current round and drops removed ones', () => {
    const bag = new ShuffleBag(['a', 'b', 'c'], seeded(3))
    const first = bag.next() as string
    const removed = ['a', 'b', 'c'].find((x) => x !== first) as string
    const kept = ['a', 'b', 'c'].filter((x) => x !== removed)
    bag.update([...kept, 'd'])
    // The round finishes with the rest of what's left, including the new item.
    const rest = [bag.next(), bag.next()]
    expect(rest).toContain('d')
    expect(rest).not.toContain(removed)
    expect(new Set([first, ...rest])).toEqual(new Set([...kept, 'd']))
  })

  it('repeats a single item and returns null when empty', () => {
    const one = new ShuffleBag(['only'])
    expect([one.next(), one.next()]).toEqual(['only', 'only'])
    expect(new ShuffleBag([]).next()).toBeNull()
  })
})
