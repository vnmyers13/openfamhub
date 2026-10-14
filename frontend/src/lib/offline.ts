/**
 * Offline writes (Phase 9): queue a write when there's no connection, and
 * replay the queue when it comes back (and when the tab is shown again).
 *
 * - A write that can't reach the server goes to IndexedDB (lib/idb) and the
 *   caller is told it was queued, so the screen can show it straight away.
 * - Replays go one at a time, oldest first, with credentials (apiClient
 *   sends the sign-in cookie) and the write's id as its Idempotency-Key.
 *   A write is removed only after the server accepts it: all or nothing.
 * - 409 means someone else changed it: the write is kept with the conflict,
 *   and the app asks keep mine / keep theirs / merge. Another refusal keeps
 *   it with the reason until someone discards it. No connection, a server
 *   error or a lapsed sign-in stops the replay with everything still queued.
 */
import { isAxiosError } from 'axios'
import { create } from 'zustand'
import { apiClient } from '../api/client'
import { allWrites, putWrite, queueAvailable, removeWrite, type Conflict, type QueuedWrite } from './idb'

export type { QueuedWrite } from './idb'

interface OfflineState {
  online: boolean
  pending: QueuedWrite[]
  syncing: boolean
  signInNeeded: boolean
  set: (patch: Partial<OfflineState>) => void
}

export const useOffline = create<OfflineState>((set) => ({
  online: typeof navigator === 'undefined' ? true : navigator.onLine,
  pending: [],
  syncing: false,
  signInNeeded: false,
  set: (patch) => set(patch),
}))

function newId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `w-${Date.now()}-${Math.random().toString(36).slice(2)}`
}

type Failure = { response?: { status?: number; data?: { detail?: unknown } } }

/** No reply at all: offline, DNS, server unreachable. */
export function isNetworkError(err: unknown): boolean {
  return isAxiosError(err) && !err.response
}

const statusOf = (err: unknown) => (err as Failure)?.response?.status
const detailOf = (err: unknown) => (err as Failure)?.response?.data?.detail

// Strictly increasing, so writes made in the same millisecond keep their order.
let lastStamp = 0
function stamp(): number {
  lastStamp = Math.max(Date.now(), lastStamp + 1)
  return lastStamp
}

async function send(write: QueuedWrite) {
  const config = { headers: { 'Idempotency-Key': write.id } }
  if (write.method === 'delete') return apiClient.delete(write.url, config)
  return apiClient[write.method](write.url, write.body, config)
}

export async function refreshPending(): Promise<QueuedWrite[]> {
  if (!queueAvailable()) return []
  try {
    const pending = await allWrites()
    useOffline.getState().set({ pending })
    return pending
  } catch {
    return []  // a broken store shouldn't break the app; writes just won't queue
  }
}

export type WriteResult<T> = { queued: true; write: QueuedWrite } | { queued: false; data: T }

/**
 * Send a write now if we can; otherwise queue it. Anything other than "no
 * connection" (403, 422 …) is thrown as usual.
 */
export async function offlineWrite<T>(w: Omit<QueuedWrite, 'id' | 'createdAt'>): Promise<WriteResult<T>> {
  const write: QueuedWrite = { ...w, id: newId(), createdAt: stamp() }
  if (!queueAvailable()) return { queued: false, data: (await send(write)).data as T }  // no queue: plain write
  if (useOffline.getState().online && navigator.onLine) {
    try {
      return { queued: false, data: (await send(write)).data as T }
    } catch (err) {
      if (!isNetworkError(err)) throw err
      useOffline.getState().set({ online: false })
    }
  }
  // Only a queued edit carries "the item as last seen", so a replay can spot
  // that someone else changed it in the meantime.
  if (write.base) write.body = { ...(write.body ?? {}), base: write.base }
  await putWrite(write)
  await refreshPending()
  return { queued: true, write }
}

function conflictFrom(detail: unknown): Conflict {
  if (detail && typeof detail === 'object' && 'message' in detail) {
    const d = detail as { message: string; fields?: string[]; current?: Record<string, unknown> }
    return { message: d.message, fields: d.fields ?? [], current: d.current }
  }
  return { message: typeof detail === 'string' ? detail : 'Someone else changed this', fields: [] }
}

let running: Promise<void> | null = null

/** Replay the queue. Returns the query keys to refresh for writes that landed. */
export function replay(onSaved?: (keys: string[][]) => void): Promise<void> {
  if (!queueAvailable()) return Promise.resolve()
  if (running) return running
  running = (async () => {
    const state = useOffline.getState()
    state.set({ syncing: true })
    try {
      for (const write of await allWrites()) {
        if (write.conflict || write.error) continue // waiting for someone to decide
        try {
          await send(write)
          await removeWrite(write.id)
          onSaved?.(write.refresh)
          state.set({ online: true, signInNeeded: false })
        } catch (err) {
          if (isNetworkError(err)) {
            state.set({ online: false })
            break
          }
          const status = statusOf(err)
          const detail = detailOf(err)
          if (status === 401) {
            state.set({ signInNeeded: true })
            break
          }
          if (status === 409) {
            await putWrite({ ...write, conflict: conflictFrom(detail) })
          } else if (status !== undefined && status < 500) {
            await putWrite({ ...write, error: typeof detail === 'string' ? detail : `Refused (${status})` })
          } else {
            break // server trouble: try again later, in order
          }
        }
      }
    } finally {
      await refreshPending()
      state.set({ syncing: false })
      running = null
    }
  })()
  return running
}

// ---- deciding about a conflict or a refused write ----

/** Keep theirs: drop my change. Also "Discard" for a refused write. */
export async function discard(write: QueuedWrite): Promise<void> {
  await removeWrite(write.id)
  await refreshPending()
}

/** Keep mine: send my change again without the "as last seen" check. */
export async function keepMine(write: QueuedWrite): Promise<void> {
  const body = { ...(write.body ?? {}) }
  delete body.base
  await requeue(write, body)
}

/**
 * A decided conflict is a new request, so it gets a new id and with it a new
 * Idempotency-Key: the server remembers its answer to the old key (the 409)
 * and would otherwise give it back on every replay. It keeps its place in
 * the queue (createdAt).
 */
async function requeue(write: QueuedWrite, body: Record<string, unknown>): Promise<void> {
  await removeWrite(write.id)
  await putWrite({ ...write, id: newId(), body, conflict: undefined, error: undefined })
  await refreshPending()
}

/**
 * Merge: my change wins on fields the other person didn't touch; theirs
 * wins where we both changed something. Nothing left to send → dropped.
 */
export function mergedChanges(write: QueuedWrite): Record<string, unknown> {
  const current = write.conflict?.current ?? {}
  const base = write.base ?? {}
  const out: Record<string, unknown> = {}
  for (const [k, v] of Object.entries(write.local ?? {})) {
    if (current[k] === base[k] && current[k] !== v) out[k] = v
  }
  return out
}

export async function merge(write: QueuedWrite): Promise<void> {
  const changes = mergedChanges(write)
  if (Object.keys(changes).length === 0) return discard(write)
  await requeue(write, changes)
}
