import { afterEach, describe, expect, it, vi } from 'vitest'
import type { QueuedWrite } from './idb'

/**
 * Two refreshes of the waiting list can overlap (finishing a decision starts a
 * sync, which refreshes at its end, while the next decision refreshes too). The
 * older read must never overwrite the newer one, or the banner shows a change
 * that's already gone ("1 needs a decision") until the next refresh.
 */
const reads: Array<(rows: QueuedWrite[]) => void> = []
vi.mock('./idb', async (orig) => ({
  ...(await orig<typeof import('./idb')>()),
  queueAvailable: () => true,
  allWrites: () => new Promise<QueuedWrite[]>((resolve) => reads.push(resolve)),
}))

import { refreshPending, useOffline } from './offline'

const write = (id: string): QueuedWrite => ({ id, method: 'post', url: '/x', label: id, createdAt: 1, refresh: [], error: 'refused' })

describe('refreshPending', () => {
  afterEach(() => { reads.length = 0 })

  it('a slower, older read never replaces a newer one', async () => {
    const older = refreshPending()   // reads while "b" still exists
    const newer = refreshPending()   // reads after "b" was discarded
    reads[1]([])                     // the newer read comes back first
    await newer
    reads[0]([write('b')])           // then the stale one
    await older
    expect(useOffline.getState().pending).toEqual([])
  })

  it('in order, the last read wins as usual', async () => {
    const first = refreshPending()
    reads[0]([write('a')])
    await first
    expect(useOffline.getState().pending.map((w) => w.id)).toEqual(['a'])
    const second = refreshPending()
    reads[1]([])
    await second
    expect(useOffline.getState().pending).toEqual([])
  })
})
