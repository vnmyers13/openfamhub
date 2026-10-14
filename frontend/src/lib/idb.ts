/**
 * The offline write queue, kept in IndexedDB so changes made without a
 * connection survive closing the tab or restarting the phone (Phase 9).
 * Each entry is one API write; its id doubles as the Idempotency-Key, so a
 * replay can never apply twice.
 */
export interface Conflict {
  message: string
  fields: string[]
  current?: Record<string, unknown>
}

export interface QueuedWrite {
  id: string
  method: 'post' | 'put' | 'patch' | 'delete'
  url: string
  body?: Record<string, unknown>
  /** Shown to people: "Tick off Milk", "Add Coffee". */
  label: string
  createdAt: number
  /** Query keys to refresh once it's saved. */
  refresh: string[][]
  /** For edits: the item as last seen, and just the fields being changed (for merging). */
  base?: Record<string, unknown>
  local?: Record<string, unknown>
  /** Set when a replay was refused; the write waits for a decision. */
  conflict?: Conflict
  error?: string
}

const DB = 'openfamhub-offline'
const STORE = 'writes'

/** Some browsers (private modes, old WebViews) have no usable IndexedDB. */
export function queueAvailable(): boolean {
  return typeof indexedDB !== 'undefined' && indexedDB !== null
}

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    if (!queueAvailable()) {
      reject(new Error('IndexedDB is not available'))
      return
    }
    const req = indexedDB.open(DB, 1)
    req.onupgradeneeded = () => {
      if (!req.result.objectStoreNames.contains(STORE)) req.result.createObjectStore(STORE, { keyPath: 'id' })
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
}

async function tx<T>(mode: IDBTransactionMode, fn: (store: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open()
  try {
    return await new Promise<T>((resolve, reject) => {
      const t = db.transaction(STORE, mode)
      const req = fn(t.objectStore(STORE))
      t.oncomplete = () => resolve(req.result)
      t.onerror = () => reject(t.error)
      t.onabort = () => reject(t.error)
    })
  } finally {
    db.close()
  }
}

/** Every queued write, oldest first (replay order). */
export async function allWrites(): Promise<QueuedWrite[]> {
  const rows = await tx<QueuedWrite[]>('readonly', (s) => s.getAll() as IDBRequest<QueuedWrite[]>)
  return rows.sort((a, b) => a.createdAt - b.createdAt || a.id.localeCompare(b.id))
}

export async function putWrite(write: QueuedWrite): Promise<void> {
  await tx('readwrite', (s) => s.put(write))
}

export async function removeWrite(id: string): Promise<void> {
  await tx('readwrite', (s) => s.delete(id))
}

export async function clearWrites(): Promise<void> {
  await tx('readwrite', (s) => s.clear())
}
