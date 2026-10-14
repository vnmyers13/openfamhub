import 'fake-indexeddb/auto'
import { IDBFactory } from 'fake-indexeddb'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { apiError, mockApi } from '../test/api'
import { allWrites } from './idb'
import { discard, keepMine, merge, mergedChanges, offlineWrite, refreshPending, replay, useOffline, type QueuedWrite } from './offline'

/** An axios failure with no reply: what being offline looks like. */
const networkError = () => Object.assign(new Error('Network Error'), { isAxiosError: true, request: {} })
const goOffline = () => useOffline.getState().set({ online: false })
const goOnline = () => useOffline.getState().set({ online: true })

const tick = (id: string, name: string) => ({
  method: 'patch' as const, url: `/meals/shopping/${id}`, body: { checked: true }, label: `Tick off ${name}`,
  refresh: [['shopping']], base: { name, quantity: null, checked: false }, local: { checked: true },
})

describe('offline writes', () => {
  beforeEach(() => {
    globalThis.indexedDB = new IDBFactory()  // a fresh, empty browser database per test
    useOffline.setState({ online: true, pending: [], syncing: false, signInNeeded: false })
  })
  afterEach(() => vi.restoreAllMocks())

  it('sends straight away when online', async () => {
    const calls = mockApi({ 'PATCH /meals/shopping/s1': { id: 's1', checked: true } })
    const res = await offlineWrite(tick('s1', 'Milk'))
    expect(res).toEqual({ queued: false, data: { id: 's1', checked: true } })
    expect(calls[0].body).toEqual({ checked: true })  // no "as last seen" when sent live
    expect(await allWrites()).toEqual([])
  })

  it('queues when offline, and the queue survives a reload', async () => {
    goOffline()
    const res = await offlineWrite(tick('s1', 'Milk'))
    expect(res.queued).toBe(true)
    // A reload: nothing in memory, only what IndexedDB kept.
    useOffline.setState({ pending: [] })
    const [kept] = await refreshPending()
    expect(kept).toMatchObject({ label: 'Tick off Milk', url: '/meals/shopping/s1',
      body: { checked: true, base: { name: 'Milk', quantity: null, checked: false } } })
    expect(useOffline.getState().pending).toHaveLength(1)
  })

  it('queues when the request gets no reply, but other errors are thrown', async () => {
    mockApi({ 'PATCH /meals/shopping/s1': () => { throw networkError() },
      'PATCH /meals/shopping/s2': () => { throw apiError(403, "Viewers can't change meals") } })
    expect((await offlineWrite(tick('s1', 'Milk'))).queued).toBe(true)
    expect(useOffline.getState().online).toBe(false)
    goOnline()
    await expect(offlineWrite(tick('s2', 'Eggs'))).rejects.toThrow()
    expect(await allWrites()).toHaveLength(1)
  })

  it('replays oldest first with the idempotency key; each write lands fully or stays', async () => {
    goOffline()
    await offlineWrite({ method: 'post', url: '/meals/shopping', body: { name: 'Coffee' }, label: 'Add Coffee', refresh: [['shopping']] })
    await offlineWrite(tick('s1', 'Milk'))
    goOnline()
    const seen: unknown[] = []
    const post = vi.fn()
    mockApi({
      'POST /meals/shopping': (body: unknown, config?: unknown) => { post(body); seen.push(config); return { id: 'n1' } },
      'PATCH /meals/shopping/s1': () => { throw networkError() },
    })
    const saved = vi.fn()
    await replay(saved)
    expect(post).toHaveBeenCalledWith({ name: 'Coffee' })
    expect((seen[0] as { headers: Record<string, string> }).headers['Idempotency-Key']).toBeTruthy()
    expect(saved).toHaveBeenCalledWith([['shopping']])
    const left = await allWrites()
    expect(left.map((w) => w.label)).toEqual(['Tick off Milk'])  // the one that didn't land is still queued
    expect(useOffline.getState().online).toBe(false)
  })

  it('a 409 keeps the write with the conflict instead of overwriting, and waits for a decision', async () => {
    goOffline()
    await offlineWrite(tick('s1', 'Milk'))
    goOnline()
    let attempts = 0
    mockApi({ 'PATCH /meals/shopping/s1': () => {
      attempts++
      throw apiError(409, { message: 'Someone else changed this while you were offline', fields: ['quantity'],
        current: { name: 'Milk', quantity: '2 gal', checked: false } } as never)
    } })
    await replay()
    await replay()  // not retried until someone decides
    expect(attempts).toBe(1)
    const [w] = await allWrites()
    expect(w.conflict).toEqual({ message: 'Someone else changed this while you were offline', fields: ['quantity'],
      current: { name: 'Milk', quantity: '2 gal', checked: false } })
  })

  it('a refused replay stays queued with the reason; a server error or a lapsed sign-in leaves it untouched', async () => {
    goOffline()
    await offlineWrite(tick('s1', 'Milk'))
    await offlineWrite(tick('s2', 'Eggs'))
    goOnline()
    mockApi({ 'PATCH /meals/shopping/s1': () => { throw apiError(422, 'name is too long') },
      'PATCH /meals/shopping/s2': () => { throw apiError(503, 'down') } })
    await replay()
    const [a, b] = await allWrites()
    expect(a.error).toBe('name is too long')
    expect(b.error).toBeUndefined()
    mockApi({ 'PATCH /meals/shopping/s2': () => { throw apiError(401, 'Session expired') } })
    await replay()
    expect((await allWrites())[1].error).toBeUndefined()
    expect(useOffline.getState().signInNeeded).toBe(true)
  })

  it("keep mine resends without the check; keep theirs drops it; merge keeps both people's changes", async () => {
    const write: QueuedWrite = {
      ...tick('s1', 'Milk'), id: 'w1', createdAt: 1,
      body: { checked: true, quantity: '1 gal', base: { name: 'Milk', quantity: null, checked: false } },
      local: { checked: true, quantity: '1 gal' }, base: { name: 'Milk', quantity: null, checked: false },
      conflict: { message: 'changed', fields: ['quantity'], current: { name: 'Milk', quantity: '2 gal', checked: false } },
    }
    // Merge: they changed the quantity, I ticked it: send only the tick.
    expect(mergedChanges(write)).toEqual({ checked: true })
    const { putWrite } = await import('./idb')
    await putWrite(write)
    await merge(write)
    const [merged] = await allWrites()
    expect(merged).toMatchObject({ body: { checked: true }, conflict: undefined, createdAt: 1 })
    expect(merged.id).not.toBe('w1')  // a new request, so a new Idempotency-Key
    await keepMine({ ...write, id: merged.id })
    const [mine] = await allWrites()
    expect(mine.body).toEqual({ checked: true, quantity: '1 gal' })
    await discard(mine)
    expect(await allWrites()).toEqual([])
    // Nothing left to merge → dropped.
    await putWrite({ ...write, local: { quantity: '1 gal' } })
    await merge({ ...write, local: { quantity: '1 gal' } })
    expect(await allWrites()).toEqual([])
  })

  it('keep mine and merge go through even though the server remembers the first answer per key', async () => {
    // Like IdempotencyMiddleware: the same key gets the same answer back, refusals included.
    const answers = new Map<string, () => unknown>()
    let landed = 0
    let changedByThem = true
    const server = (body: unknown, config?: unknown) => {
      const key = (config as { headers: Record<string, string> }).headers['Idempotency-Key']
      if (!answers.has(key)) {
        const stale = changedByThem && (body as { base?: unknown }).base !== undefined
        answers.set(key, stale
          ? () => { throw apiError(409, 'Someone else changed this while you were offline') }
          : () => { landed += 1; return { id: 's1', checked: true } })
      }
      return answers.get(key)!()
    }
    mockApi({ 'PATCH /meals/shopping/s1': server })
    goOffline()
    await offlineWrite(tick('s1', 'Milk'))
    goOnline()
    await replay()
    const [conflicted] = await allWrites()
    expect(conflicted.conflict).toBeDefined()
    await keepMine(conflicted)
    await replay()
    expect(await allWrites()).toEqual([])
    expect(landed).toBe(1)

    // Merge, the same way.
    goOffline()
    await offlineWrite(tick('s1', 'Milk'))
    goOnline()
    await replay()
    const [again] = await allWrites()
    await merge({ ...again, conflict: { message: 'changed', fields: ['quantity'], current: { name: 'Milk', quantity: '2 gal', checked: false } } })
    changedByThem = false
    await replay()
    expect(await allWrites()).toEqual([])
    expect(landed).toBe(2)
  })
})

describe('without IndexedDB', () => {
  afterEach(() => {
    globalThis.indexedDB = new IDBFactory()
    vi.restoreAllMocks()
  })

  it('writes go straight to the server and nothing breaks', async () => {
    // @ts-expect-error simulate a browser with no IndexedDB
    delete globalThis.indexedDB
    useOffline.setState({ online: true, pending: [] })
    mockApi({ 'POST /meals/shopping': { id: 'n1' } })
    expect(await offlineWrite({ method: 'post', url: '/meals/shopping', body: { name: 'x' }, label: 'Add x', refresh: [] }))
      .toEqual({ queued: false, data: { id: 'n1' } })
    expect(await refreshPending()).toEqual([])
    await expect(replay()).resolves.toBeUndefined()
  })
})
