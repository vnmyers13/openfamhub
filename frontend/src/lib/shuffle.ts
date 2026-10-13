/**
 * Slideshow order: every item once, in random order, before any repeats; a
 * new round never starts with the item that ended the last one. The list can
 * change between picks (uploads, deletions): new items join the current round,
 * removed ones are skipped.
 */
export class ShuffleBag<T> {
  private items: T[]
  private remaining: T[] = []
  private last: T | null = null
  private readonly random: () => number

  constructor(items: T[], random: () => number = Math.random) {
    this.items = [...items]
    this.random = random
  }

  update(items: T[]): void {
    const added = items.filter((i) => !this.items.includes(i))
    this.items = [...items]
    this.remaining = this.remaining.filter((i) => this.items.includes(i))
    for (const item of added) {
      this.remaining.splice(Math.floor(this.random() * (this.remaining.length + 1)), 0, item)
    }
  }

  next(): T | null {
    if (this.items.length === 0) return null
    if (this.remaining.length === 0) {
      this.remaining = this.shuffled()
      if (this.items.length > 1 && this.remaining[0] === this.last) {
        const swap = 1 + Math.floor(this.random() * (this.remaining.length - 1))
        ;[this.remaining[0], this.remaining[swap]] = [this.remaining[swap], this.remaining[0]]
      }
    }
    this.last = this.remaining.shift() as T
    return this.last
  }

  private shuffled(): T[] {
    const a = [...this.items]
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(this.random() * (i + 1))
      ;[a[i], a[j]] = [a[j], a[i]]
    }
    return a
  }
}
