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
