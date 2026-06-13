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
