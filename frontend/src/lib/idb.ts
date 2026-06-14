const DB_NAME = 'openfamhub-sync'
const DB_VERSION = 1
const STORE_NAME = 'pending-operations'

export interface PendingOperation {
  id: string
  type: 'create' | 'update' | 'delete'
  entity: 'shopping-item' | 'chore-instance' | 'recipe'
  data: Record<string, unknown>
  endpoint: string
  timestamp: number
  serverVersion?: string
}

export function openDB(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onupgradeneeded = (event) => {
      const db = (event.target as IDBOpenDBRequest).result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        const store = db.createObjectStore(STORE_NAME, { keyPath: 'id' })
        store.createIndex('timestamp', 'timestamp', { unique: false })
        store.createIndex('entity', 'entity', { unique: false })
      }
    }

    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}

export async function enqueueOperation(op: Omit<PendingOperation, 'id' | 'timestamp'>): Promise<string> {
  const db = await openDB()
  const id = `${op.entity}-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`
  const operation: PendingOperation = {
    ...op,
    id,
    timestamp: Date.now(),
  }

  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const request = store.add(operation)
    request.onsuccess = () => resolve(id)
    request.onerror = () => reject(request.error)
  })
}

export async function getPendingOperations(): Promise<PendingOperation[]> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    const index = store.index('timestamp')
    const request = index.getAll()
    request.onsuccess = () => resolve(request.result as PendingOperation[])
    request.onerror = () => reject(request.error)
  })
}

export async function dequeueOperation(id: string): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    const request = store.delete(id)
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}

export async function clearOperations(entity?: 'shopping-item' | 'chore-instance' | 'recipe'): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    let request: IDBRequest
    if (entity) {
      const index = store.index('entity')
      request = (index as any).deleteAll(entity)
    } else {
      request = store.clear()
    }
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}

export async function getOperationCount(entity?: 'shopping-item' | 'chore-instance' | 'recipe'): Promise<number> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readonly')
    const store = tx.objectStore(STORE_NAME)
    let request: IDBRequest
    if (entity) {
      const index = store.index('entity')
      request = index.count()
    } else {
      request = store.count()
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
}
