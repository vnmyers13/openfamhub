import { useOfflineStore } from './offline-state'
import type { PendingOperation } from './idb'
import {
  getPendingOperations,
  dequeueOperation,
  clearOperations,
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

  const conflicts: PendingOperation[] = []

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

async function executeOperation(op: PendingOperation): Promise<Response> {
  const url = `${API_BASE}${op.endpoint}`

  switch (op.type) {
    case 'create':
      return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(op.data),
      })

    case 'update':
      const id = (op.data as { id: string }).id
      return fetch(`${url}/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(op.data),
      })

    case 'delete':
      const deleteId = (op.data as { id: string }).id
      return fetch(`${url}/${deleteId}`, { method: 'DELETE' })

    default:
      throw new Error(`Unknown operation type: ${op.type}`)
  }
}

export async function checkOnlineStatus(): Promise<boolean> {
  return navigator.onLine
}

export async function getPendingCount(entity?: 'shopping-item' | 'chore-instance'): Promise<number> {
  const { getOperationCount } = await import('./idb')
  return getOperationCount(entity)
}
