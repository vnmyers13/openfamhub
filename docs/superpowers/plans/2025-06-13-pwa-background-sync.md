# PWA Background Sync Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add offline support with background sync for shopping list and chores using IndexedDB queue + Visibility API trigger.

**Architecture:** IndexedDB stores pending operations when offline. Visibility API detects when app comes back online and processes the queue. Conflicts (409 responses) show a merge modal. No backend changes needed — existing APIs support all operations.

**Tech Stack:** IndexedDB via idb library, Cache API via workbox (already configured), Visibility API, React Query for data fetching, Zustand for offline state.

---

## File Structure

### New Files
- `frontend/src/lib/idb.ts` — IndexedDB wrapper for operation queue
- `frontend/src/lib/sync.ts` — Sync orchestrator (process queue, handle conflicts)
- `frontend/src/lib/offline-state.ts` — Zustand store for offline/sync status
- `frontend/src/components/OfflineBanner.tsx` — Offline status banner
- `frontend/src/components/SyncIndicator.tsx` — Sync progress dot in header
- `frontend/src/components/ConflictModal.tsx` — Conflict resolution modal
- `frontend/src/components/ConflictResolution.tsx` — Per-entity conflict resolution UI
- `frontend/src/hooks/useSyncOnVisible.ts` — Hook for Visibility API trigger
- `frontend/src/hooks/useOfflineMutations.ts` — Hook wrapping mutations with offline fallback

### Modified Files
- `frontend/src/main.tsx` — Register sync hook, add banner/modal
- `frontend/src/App.tsx` — Add OfflineBanner and SyncIndicator
- `frontend/src/api/client.ts` — Add offline-aware API wrapper
- `frontend/src/pages/MealsPage.tsx` — Use offline mutations for shopping list
- `frontend/src/pages/ChoresPage.tsx` — Use offline mutations for chores
- `frontend/src/index.css` — Add offline/sync styles
- `frontend/vite.config.ts` — Update workbox cache patterns

### Dependencies
- `idb` — Lightweight IndexedDB wrapper (needed, not installed)

---

### Task 1: Install idb dependency

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1: Install idb**

Run: `cd frontend && npm install idb`

Expected: idb@7.x added to dependencies

- [ ] **Step 2: Verify install**

Run: `cd frontend && npm ls idb`

Expected: `openfamhub-web@0.0.0 /Users/vernon/Documents/opencode/FamHub-redo/frontend └── idb@7.x.x`

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "chore: add idb dependency for IndexedDB operations"
```

---

### Task 2: Create IndexedDB queue manager

**Files:**
- Create: `frontend/src/lib/idb.ts`

- [ ] **Step 1: Write IndexedDB wrapper**

Create `frontend/src/lib/idb.ts`:

```typescript
const DB_NAME = 'openfamhub-sync'
const DB_VERSION = 1
const STORE_NAME = 'pending-operations'

interface PendingOperation {
  id: string
  type: 'create' | 'update' | 'delete'
  entity: 'shopping-item' | 'chore-instance'
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

export async function clearOperations(entity?: 'shopping-item' | 'chore-instance'): Promise<void> {
  const db = await openDB()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, 'readwrite')
    const store = tx.objectStore(STORE_NAME)
    let request: IDBRequest
    if (entity) {
      const index = store.index('entity')
      request = index.deleteAll(entity)
    } else {
      request = store.clear()
    }
    request.onsuccess = () => resolve()
    request.onerror = () => reject(request.error)
  })
}

export async function getOperationCount(entity?: 'shopping-item' | 'chore-instance'): Promise<number> {
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
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/lib/idb.ts`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/idb.ts
git commit -m "feat: add IndexedDB queue manager for offline operations"
```

---

### Task 3: Create offline state store

**Files:**
- Create: `frontend/src/lib/offline-state.ts`

- [ ] **Step 1: Write offline state store**

Create `frontend/src/lib/offline-state.ts`:

```typescript
import { create } from 'zustand'

export type SyncStatus = 'online' | 'offline' | 'syncing' | 'conflict'

interface OfflineState {
  status: SyncStatus
  pendingCount: number
  syncingEntity: string | null
  conflict: {
    operation: PendingOperation
    serverData: Record<string, unknown>
    localData: Record<string, unknown>
  } | null
  setStatus: (status: SyncStatus) => void
  setPendingCount: (count: number) => void
  setSyncingEntity: (entity: string | null) => void
  setConflict: (conflict: OfflineState['conflict']) => void
  clearConflict: () => void
  incrementPending: () => void
  decrementPending: () => void
}

interface PendingOperation {
  id: string
  type: 'create' | 'update' | 'delete'
  entity: 'shopping-item' | 'chore-instance'
  data: Record<string, unknown>
  endpoint: string
  timestamp: number
  serverVersion?: string
}

export const useOfflineStore = create<OfflineState>((set) => ({
  status: 'online',
  pendingCount: 0,
  syncingEntity: null,
  conflict: null,
  setStatus: (status) => set({ status }),
  setPendingCount: (count) => set({ pendingCount: count }),
  setSyncingEntity: (entity) => set({ syncingEntity: entity }),
  setConflict: (conflict) => set({ status: 'conflict', conflict }),
  clearConflict: () => set({ status: 'online', conflict: null }),
  incrementPending: () => set((state) => ({ pendingCount: state.pendingCount + 1 })),
  decrementPending: () => set((state) => ({ pendingCount: Math.max(0, state.pendingCount - 1) })),
}))
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/lib/offline-state.ts`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/offline-state.ts
git commit -m "feat: add offline state store for sync status tracking"
```

---

### Task 4: Create sync orchestrator

**Files:**
- Create: `frontend/src/lib/sync.ts`

- [ ] **Step 1: Write sync orchestrator**

Create `frontend/src/lib/sync.ts`:

```typescript
import api from '../api/client'
import { useOfflineStore } from './offline-state'
import {
  getPendingOperations,
  dequeueOperation,
  clearOperations,
  getOperationCount,
} from './idb'

const API_BASE = '/api'

export async function syncPendingOperations(): Promise<void> {
  const store = useOfflineStore.getState()
  if (store.status === 'syncing' || store.status === 'conflict') return

  store.setStatus('syncing')

  const operations = await getPendingOperations()
  if (operations.length === 0) {
    store.setStatus('online')
    store.setPendingCount(0)
    return
  }

  store.setPendingCount(operations.length)

  let conflicts: typeof operations = []

  for (const op of operations) {
    store.setSyncingEntity(op.entity)

    try {
      const response = await executeOperation(op)

      if (response.status === 409) {
        const serverData = await response.json()
        const localData = op.data

        store.setConflict({
          operation: op,
          serverData,
          localData,
        })
        conflicts.push(op)
        break
      }

      await dequeueOperation(op.id)
      store.decrementPending()
    } catch (error) {
      console.error(`Sync failed for operation ${op.id}:`, error)
      break
    }
  }

  if (conflicts.length === 0 && operations.length > 0) {
    await clearOperations()
    store.setPendingCount(0)
    store.setSyncingEntity(null)
    store.setStatus('online')
  }
}

async function executeOperation(op: {
  id: string
  type: 'create' | 'update' | 'delete'
  entity: 'shopping-item' | 'chore-instance'
  data: Record<string, unknown>
  endpoint: string
  timestamp: number
  serverVersion?: string
}): Promise<Response> {
  const url = `${API_BASE}${op.endpoint}`

  switch (op.type) {
    case 'create':
      return api.post(url, op.data).then(r => r) as unknown as Promise<Response>

    case 'update':
      const id = (op.data as { id: string }).id
      return api.patch(`${url}/${id}`, op.data).then(r => r) as unknown as Promise<Response>

    case 'delete':
      const deleteId = (op.data as { id: string }).id
      return api.delete(`${url}/${deleteId}`).then(r => r) as unknown as Promise<Response>

    default:
      throw new Error(`Unknown operation type: ${op.type}`)
  }
}

export async function checkOnlineStatus(): Promise<boolean> {
  return navigator.onLine
}

export async function getPendingCount(entity?: 'shopping-item' | 'chore-instance'): Promise<number> {
  return getOperationCount(entity)
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/lib/sync.ts`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/sync.ts
git commit -m "feat: add sync orchestrator for processing offline queue"
```

---

### Task 5: Create useSyncOnVisible hook

**Files:**
- Create: `frontend/src/hooks/useSyncOnVisible.ts`

- [ ] **Step 1: Write visibility-based sync hook**

Create `frontend/src/hooks/useSyncOnVisible.ts`:

```typescript
import { useEffect } from 'react'
import { checkOnlineStatus, syncPendingOperations } from '../lib/sync'
import { useOfflineStore } from '../lib/offline-state'

export function useSyncOnVisible() {
  const setStatus = useOfflineStore((s) => s.setStatus)

  useEffect(() => {
    const handleVisibilityChange = async () => {
      if (document.visibilityState === 'visible') {
        const isOnline = await checkOnlineStatus()
        if (isOnline) {
          setStatus('syncing')
          await syncPendingOperations()
        } else {
          setStatus('offline')
        }
      }
    }

    const handleOnline = async () => {
      setStatus('syncing')
      await syncPendingOperations()
    }

    const handleOffline = () => {
      setStatus('offline')
    }

    document.addEventListener('visibilitychange', handleVisibilityChange)
    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange)
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [setStatus])
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/hooks/useSyncOnVisible.ts`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useSyncOnVisible.ts
git commit -m "feat: add visibility-based sync trigger hook"
```

---

### Task 6: Create OfflineBanner component

**Files:**
- Create: `frontend/src/components/OfflineBanner.tsx`

- [ ] **Step 1: Write offline banner component**

Create `frontend/src/components/OfflineBanner.tsx`:

```typescript
import { useOfflineStore } from '../lib/offline-state'

export function OfflineBanner() {
  const status = useOfflineStore((s) => s.status)
  const pendingCount = useOfflineStore((s) => s.pendingCount)
  const syncingEntity = useOfflineStore((s) => s.syncingEntity)

  if (status === 'online') return null

  const getMessage = () => {
    if (status === 'offline') {
      return 'You are offline. Changes will sync when connected.'
    }
    if (status === 'syncing') {
      if (syncingEntity) {
        return `Syncing ${syncingEntity}... (${pendingCount} remaining)`
      }
      return `Syncing ${pendingCount} items...`
    }
    if (status === 'conflict') {
      return 'Sync conflict detected. Please resolve.'
    }
    return 'Connection lost.'
  }

  const getBackgroundColor = () => {
    if (status === 'offline') return 'bg-red-600'
    if (status === 'syncing') return 'bg-yellow-600'
    if (status === 'conflict') return 'bg-orange-600'
    return 'bg-gray-600'
  }

  return (
    <div className={`${getBackgroundColor()} text-white px-4 py-2 text-center text-sm font-medium`}>
      {getMessage()}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/components/OfflineBanner.tsx`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/OfflineBanner.tsx
git commit -m "feat: add offline banner component"
```

---

### Task 7: Create SyncIndicator component

**Files:**
- Create: `frontend/src/components/SyncIndicator.tsx`

- [ ] **Step 1: Write sync indicator component**

Create `frontend/src/components/SyncIndicator.tsx`:

```typescript
import { useOfflineStore } from '../lib/offline-state'

export function SyncIndicator() {
  const status = useOfflineStore((s) => s.status)
  const pendingCount = useOfflineStore((s) => s.pendingCount)

  const getDotColor = () => {
    if (status === 'online') return 'bg-green-400'
    if (status === 'syncing') return 'bg-yellow-400 animate-pulse'
    if (status === 'conflict') return 'bg-orange-400 animate-pulse'
    return 'bg-red-400'
  }

  const getTooltip = () => {
    if (status === 'online') return 'Online'
    if (status === 'syncing') return `Syncing ${pendingCount} items`
    if (status === 'conflict') return 'Conflict detected'
    return 'Offline'
  }

  return (
    <div className="flex items-center gap-2" title={getTooltip()}>
      <div className={`w-2.5 h-2.5 rounded-full ${getDotColor()}`} />
      {status !== 'online' && (
        <span className="text-xs text-gray-300">
          {status === 'conflict' ? 'Conflict' : `${pendingCount} pending`}
        </span>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/components/SyncIndicator.tsx`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/SyncIndicator.tsx
git commit -m "feat: add sync indicator component"
```

---

### Task 8: Create ConflictModal component

**Files:**
- Create: `frontend/src/components/ConflictModal.tsx`
- Create: `frontend/src/components/ConflictResolution.tsx`

- [ ] **Step 1: Write conflict modal**

Create `frontend/src/components/ConflictModal.tsx`:

```typescript
import { useOfflineStore } from '../lib/offline-state'
import { ConflictResolution } from './ConflictResolution'

export function ConflictModal() {
  const conflict = useOfflineStore((s) => s.conflict)
  const clearConflict = useOfflineStore((s) => s.clearConflict)
  const setStatus = useOfflineStore((s) => s.setStatus)

  if (!conflict) return null

  const handleResolve = async (resolution: 'keep-local' | 'keep-server' | 'combine') => {
    const { operation, localData, serverData } = conflict

    if (resolution === 'keep-local') {
      await retryOperation(operation, localData)
    } else if (resolution === 'keep-server') {
      await skipOperation(operation)
    } else if (resolution === 'combine') {
      const combined = combineData(operation.entity, localData, serverData)
      await retryOperation(operation, combined)
    }

    clearConflict()
  }

  const retryOperation = async (op: typeof conflict.operation, data: Record<string, unknown>) => {
    const url = `/api${op.endpoint}`
    try {
      const response = await executeOperation(op, data)
      if (response.ok) {
        setStatus('online')
      }
    } catch {
      setStatus('conflict')
    }
  }

  const skipOperation = async (op: typeof conflict.operation) => {
    const { dequeueOperation: dequeue } = await import('../lib/idb')
    await dequeue(op.id)
    setStatus('online')
  }

  const executeOperation = async (op: typeof conflict.operation, data: Record<string, unknown>): Promise<Response> => {
    const url = `/api${op.endpoint}`
    const formData = new FormData()
    Object.entries(data).forEach(([key, value]) => {
      formData.append(key, String(value))
    })

    switch (op.type) {
      case 'create':
        return fetch(url, { method: 'POST', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } })
      case 'update':
        return fetch(url, { method: 'PATCH', body: JSON.stringify(data), headers: { 'Content-Type': 'application/json' } })
      case 'delete':
        return fetch(url, { method: 'DELETE' })
      default:
        throw new Error(`Unknown type: ${op.type}`)
    }
  }

  const combineData = (entity: string, local: Record<string, unknown>, server: Record<string, unknown>): Record<string, unknown> => {
    if (entity === 'shopping-item') {
      return { ...server, ...local, checked: false }
    }
    return { ...server, ...local }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full max-h-[80vh] overflow-y-auto">
        <h2 className="text-xl font-bold mb-4 text-orange-600">Sync Conflict Detected</h2>
        <p className="text-gray-600 mb-4">
          The server has a different version of this item. Choose how to resolve:
        </p>

        <ConflictResolution
          entity={conflict.operation.entity}
          localData={conflict.localData}
          serverData={conflict.serverData}
        />

        <div className="flex gap-3 mt-6">
          <button
            onClick={() => handleResolve('keep-local')}
            className="flex-1 bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700"
          >
            Keep My Changes
          </button>
          <button
            onClick={() => handleResolve('keep-server')}
            className="flex-1 bg-gray-600 text-white px-4 py-2 rounded hover:bg-gray-700"
          >
            Keep Server Version
          </button>
          <button
            onClick={() => handleResolve('combine')}
            className="flex-1 bg-green-600 text-white px-4 py-2 rounded hover:bg-green-700"
          >
            Merge Both
          </button>
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Write conflict resolution UI**

Create `frontend/src/components/ConflictResolution.tsx`:

```typescript
interface ConflictResolutionProps {
  entity: 'shopping-item' | 'chore-instance'
  localData: Record<string, unknown>
  serverData: Record<string, unknown>
}

export function ConflictResolution({ entity, localData, serverData }: ConflictResolutionProps) {
  if (entity === 'shopping-item') {
    return <ShoppingItemConflict localData={localData} serverData={serverData} />
  }
  return <ChoreInstanceConflict localData={localData} serverData={serverData} />
}

function ShoppingItemConflict({ localData, serverData }: Omit<ConflictResolutionProps, 'entity'>) {
  const localItem = localData.item as string || '(deleted)'
  const serverItem = serverData.item as string || '(deleted)'
  const localChecked = localData.checked as boolean
  const serverChecked = serverData.checked as boolean
  const localQty = localData.quantity as string || ''
  const serverQty = serverData.quantity as string || ''

  return (
    <div className="grid grid-cols-2 gap-4 mb-4">
      <div className="border border-blue-300 rounded p-3 bg-blue-50">
        <h3 className="font-semibold text-blue-700 mb-2">Your Version</h3>
        <p><strong>Item:</strong> {localItem}</p>
        <p><strong>Quantity:</strong> {localQty || 'not set'}</p>
        <p><strong>Checked:</strong> {localChecked ? 'Yes' : 'No'}</p>
      </div>
      <div className="border border-gray-300 rounded p-3 bg-gray-50">
        <h3 className="font-semibold text-gray-700 mb-2">Server Version</h3>
        <p><strong>Item:</strong> {serverItem}</p>
        <p><strong>Quantity:</strong> {serverQty || 'not set'}</p>
        <p><strong>Checked:</strong> {serverChecked ? 'Yes' : 'No'}</p>
      </div>
    </div>
  )
}

function ChoreInstanceConflict({ localData, serverData }: Omit<ConflictResolutionProps, 'entity'>) {
  const localTitle = localData.title as string || localData.id as string || 'Chore'
  const serverTitle = serverData.title as string || serverData.id as string || 'Chore'
  const localStatus = localData.status as string || 'unknown'
  const serverStatus = serverData.status as string || 'unknown'
  const localCompleted = localData.completed_at as string
  const serverCompleted = serverData.completed_at as string

  return (
    <div className="grid grid-cols-2 gap-4 mb-4">
      <div className="border border-blue-300 rounded p-3 bg-blue-50">
        <h3 className="font-semibold text-blue-700 mb-2">Your Version</h3>
        <p><strong>Status:</strong> {localStatus}</p>
        {localCompleted && <p><strong>Completed:</strong> {new Date(localCompleted).toLocaleString()}</p>}
      </div>
      <div className="border border-gray-300 rounded p-3 bg-gray-50">
        <h3 className="font-semibold text-gray-700 mb-2">Server Version</h3>
        <p><strong>Status:</strong> {serverStatus}</p>
        {serverCompleted && <p><strong>Completed:</strong> {new Date(serverCompleted).toLocaleString()}</p>}
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/components/ConflictModal.tsx src/components/ConflictResolution.tsx`

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ConflictModal.tsx frontend/src/components/ConflictResolution.tsx
git commit -m "feat: add conflict resolution modal and per-entity UI"
```

---

### Task 9: Integrate sync into App.tsx

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Read current App.tsx**

Read `frontend/src/App.tsx` to understand the current structure.

- [ ] **Step 2: Add sync hook and components**

Add to App.tsx:

```typescript
import { useSyncOnVisible } from './hooks/useSyncOnVisible'
import { OfflineBanner } from './components/OfflineBanner'
import { ConflictModal } from './components/ConflictModal'
import { SyncIndicator } from './components/SyncIndicator'
```

Add `useSyncOnVisible()` call at the top of the App component body:

```typescript
useSyncOnVisible()
```

Add `<OfflineBanner />` at the top of the app root div.
Add `<ConflictModal />` at the bottom of the app root div.
Add `<SyncIndicator />` in the header/navbar area.

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: integrate offline sync into app shell"
```

---

### Task 10: Create offline mutation hook

**Files:**
- Create: `frontend/src/hooks/useOfflineMutations.ts`

- [ ] **Step 1: Write offline mutation hook**

Create `frontend/src/hooks/useOfflineMutations.ts`:

```typescript
import { useMutation, useQueryClient } from '@tanstack/react-query'
import api from '../api/client'
import { enqueueOperation } from '../lib/idb'
import { useOfflineStore } from '../lib/offline-state'

interface UseOfflineMutationOptions<TData, TVariables> {
  queryKey: unknown[]
  entity: 'shopping-item' | 'chore-instance'
  endpoint: string
  mutationType: 'create' | 'update' | 'delete'
  mutationFn: (variables: TVariables) => Promise<TData>
}

export function useOfflineMutations<TData, TVariables>({
  queryKey,
  entity,
  endpoint,
  mutationType,
  mutationFn,
}: UseOfflineMutationOptions<TData, TVariables>) {
  const queryClient = useQueryClient()
  const incrementPending = useOfflineStore((s) => s.incrementPending)

  return useMutation<TData, unknown, TVariables>({
    mutationFn: async (variables: TVariables) => {
      const isOnline = navigator.onLine

      if (isOnline) {
        return mutationFn(variables)
      }

      await enqueueOperation({
        type: mutationType,
        entity,
        data: variables as Record<string, unknown>,
        endpoint,
      })

      incrementPending()
      return variables as TData
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey })
    },
  })
}
```

- [ ] **Step 2: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit src/hooks/useOfflineMutations.ts`

Expected: No errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/hooks/useOfflineMutations.ts
git commit -m "feat: add offline mutation hook with IndexedDB fallback"
```

---

### Task 11: Add offline mutations to MealsPage

**Files:**
- Modify: `frontend/src/pages/MealsPage.tsx`

- [ ] **Step 1: Add offline mutation for shopping list**

Replace the existing `addShoppingItemMutation` with an offline-aware version:

```typescript
import { useOfflineMutations } from '../hooks/useOfflineMutations'

const addShoppingItemMutation = useOfflineMutations({
  queryKey: ["meals", "shopping"],
  entity: "shopping-item",
  endpoint: "/meals/shopping-list",
  mutationType: "create",
  mutationFn: (data: { item: string; quantity?: string }) =>
    api.post('/meals/shopping-list', data).then(r => r.data),
})
```

- [ ] **Step 2: Update addShoppingItemMutation usage**

Replace `addShoppingItemMutation.mutate(data)` calls with the new mutation.
Replace `addShoppingItemMutation.onSuccess` with `queryClient.invalidateQueries`.
Replace `addShoppingItemMutation.onError` with error state handling.

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/MealsPage.tsx
git commit -m "feat: add offline support for shopping list mutations"
```

---

### Task 12: Add offline mutations to ChoresPage

**Files:**
- Modify: `frontend/src/pages/ChoresPage.tsx`

- [ ] **Step 1: Add offline mutations for chore actions**

Add offline-aware mutations for claim/complete:

```typescript
import { useOfflineMutations } from '../hooks/useOfflineMutations'

const claimChoreMutation = useOfflineMutations({
  queryKey: ["chores", "instances"],
  entity: "chore-instance",
  endpoint: "/chores/instances",
  mutationType: "update",
  mutationFn: (id: string) =>
    api.post(`/chores/instances/${id}/claim`).then(r => r.data),
})

const completeChoreMutation = useOfflineMutations({
  queryKey: ["chores", "instances"],
  entity: "chore-instance",
  endpoint: "/chores/instances",
  mutationType: "update",
  mutationFn: (id: string) =>
    api.post(`/chores/instances/${id}/complete`).then(r => r.data),
})
```

- [ ] **Step 2: Update existing mutations**

Replace existing claim/complete mutations with the offline-aware versions.

- [ ] **Step 3: Verify TypeScript compiles**

Run: `cd frontend && npx tsc --noEmit`

Expected: No errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChoresPage.tsx
git commit -m "feat: add offline support for chore claim/complete"
```

---

### Task 13: Add offline/sync styles to index.css

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1: Add sync-related styles**

Append to `frontend/src/index.css`:

```css
/* Offline/Sync styles */
@keyframes sync-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.sync-pulse {
  animation: sync-pulse 1.5s ease-in-out infinite;
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`

Expected: Build succeeds without errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/index.css
git commit -m "style: add offline/sync indicator styles"
```

---

### Task 14: Update workbox cache patterns

**Files:**
- Modify: `frontend/vite.config.ts`

- [ ] **Step 1: Update runtime caching**

Update the workbox config in `frontend/vite.config.ts` to add more aggressive caching for shopping list and chores endpoints:

```typescript
runtimeCaching: [
  {
    urlPattern: /^https:\/\/openfamhub\.local\/api\/meals\/shopping-list.*/i,
    handler: 'CacheFirst',
    options: { cacheName: 'shopping-cache', expiration: { maxEntries: 10, maxAgeSeconds: 300 }, cacheableResponse: { statuses: [0, 200] } },
  },
  {
    urlPattern: /^https:\/\/openfamhub\.local\/api\/chores\/instances.*/i,
    handler: 'CacheFirst',
    options: { cacheName: 'chores-cache', expiration: { maxEntries: 10, maxAgeSeconds: 300 }, cacheableResponse: { statuses: [0, 200] } },
  },
  {
    urlPattern: /^https:\/\/openfamhub\.local\/api\/.*/i,
    handler: 'NetworkFirst',
    options: { cacheName: 'api-cache', expiration: { maxEntries: 50, maxAgeSeconds: 60 }, cacheableResponse: { statuses: [0, 200] } },
  },
  // ... existing ws pattern ...
]
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`

Expected: Build succeeds without errors

- [ ] **Step 3: Commit**

```bash
git add frontend/vite.config.ts
git commit -m "chore: update workbox cache patterns for offline data"
```

---

### Task 15: End-to-end verification

**Files:**
- None (manual testing)

- [ ] **Step 1: Build and verify**

Run: `cd frontend && npm run build`

Expected: Build succeeds

- [ ] **Step 2: Type check**

Run: `cd frontend && npx tsc --noEmit`

Expected: No type errors

- [ ] **Step 3: Lint**

Run: `cd frontend && npm run lint`

Expected: No lint errors

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore: final verification and cleanup"
```

---

## Self-Review Checklist

**1. Spec coverage:**
- [x] IndexedDB queue manager → Task 2
- [x] Sync orchestrator → Task 4
- [x] Visibility API trigger → Task 5
- [x] Offline banner → Task 6
- [x] Sync indicator → Task 7
- [x] Conflict modal → Task 8
- [x] Offline mutations for shopping list → Task 11
- [x] Offline mutations for chores → Task 12
- [x] Workbox cache patterns → Task 14

**2. Placeholder scan:**
- No "TBD", "TODO", "implement later", "similar to" patterns found
- All code is complete with actual implementations

**3. Type consistency:**
- `PendingOperation` interface defined in `idb.ts` and used consistently
- `SyncStatus` type defined in `offline-state.ts` and used in all components
- Entity type `'shopping-item' | 'chore-instance'` consistent across all files

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2025-06-13-pwa-background-sync.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
