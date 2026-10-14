import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { refreshPending, replay, useOffline } from '../lib/offline'

const RETRY_MS = 60_000

/**
 * Keep the offline queue moving: replay it on start, when the connection
 * comes back, when the tab is shown again, and every minute while anything
 * is waiting. Saved writes refresh the screens that show them.
 */
export function useOfflineSync() {
  const qc = useQueryClient()
  useEffect(() => {
    const set = useOffline.getState().set
    const run = () => {
      void replay((keys) => keys.forEach((queryKey) => qc.invalidateQueries({ queryKey })))
    }
    const online = () => { set({ online: true }); run() }
    const offline = () => set({ online: false })
    const visible = () => { if (document.visibilityState === 'visible') run() }
    window.addEventListener('online', online)
    window.addEventListener('offline', offline)
    document.addEventListener('visibilitychange', visible)
    const timer = setInterval(() => { if (useOffline.getState().pending.length) run() }, RETRY_MS)
    void refreshPending().then((pending) => { if (pending.length) run() })
    return () => {
      window.removeEventListener('online', online)
      window.removeEventListener('offline', offline)
      document.removeEventListener('visibilitychange', visible)
      clearInterval(timer)
    }
  }, [qc])
}
