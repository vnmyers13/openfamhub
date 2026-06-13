import { useOfflineStore } from '../lib/offline-state'
import { ConflictResolution } from './ConflictResolution'
import { dequeueOperation } from '../lib/idb'

interface ConflictModalProps {
  onRetry?: (data: Record<string, unknown>) => Promise<void>
}

export function ConflictModal({ onRetry }: ConflictModalProps) {
  const conflict = useOfflineStore((s) => s.conflict)
  const clearConflict = useOfflineStore((s) => s.clearConflict)
  const setStatus = useOfflineStore((s) => s.setStatus)

  if (!conflict) return null

  const handleResolve = async (resolution: 'keep-local' | 'keep-server' | 'combine') => {
    const { operation, localData, serverData } = conflict

    if (resolution === 'keep-local') {
      if (onRetry) {
        await onRetry(localData)
      } else {
        await retryWithFetch(operation, localData)
      }
    } else if (resolution === 'keep-server') {
      await skipOperation(operation)
    } else if (resolution === 'combine') {
      const combined = combineData(operation.entity, localData, serverData)
      if (onRetry) {
        await onRetry(combined)
      } else {
        await retryWithFetch(operation, combined)
      }
    }

    clearConflict()
  }

  const retryWithFetch = async (op: typeof conflict.operation, data: Record<string, unknown>) => {
    const url = `/api${op.endpoint}`
    try {
      let response: Response
      switch (op.type) {
        case 'create':
          response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
          break
        case 'update':
          response = await fetch(url, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) })
          break
        case 'delete':
          response = await fetch(url, { method: 'DELETE' })
          break
        default:
          throw new Error(`Unknown type: ${op.type}`)
      }
      if (response.ok) {
        setStatus('online')
      } else {
        setStatus('conflict')
      }
    } catch {
      setStatus('conflict')
    }
  }

  const skipOperation = async (op: typeof conflict.operation) => {
    await dequeueOperation(op.id)
    setStatus('online')
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
