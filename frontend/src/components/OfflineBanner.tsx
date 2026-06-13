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
