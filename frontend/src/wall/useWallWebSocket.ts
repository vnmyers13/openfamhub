import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'

const RECONNECT_MS = 10_000

/**
 * Live wall updates: the server pushes "calendar_updated" after a change is
 * committed, and the wall refetches its events. Reconnects after a drop.
 *
 * The close event arrives asynchronously, after cleanup has run, so cleanup
 * marks the hook stopped and detaches the handlers before closing; otherwise
 * an unmounted wall (or React StrictMode's mount/unmount/mount) leaves a
 * reconnect timer that opens orphan sockets forever.
 */
export function useWallWebSocket() {
  const queryClient = useQueryClient()

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/wall/ws`
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined
    let stopped = false

    function connect() {
      if (stopped) return
      const socket = new WebSocket(url)
      ws = socket
      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'calendar_updated') {
            queryClient.invalidateQueries({ queryKey: ['wall-events'] })
          }
        } catch {
          // ignore parse errors
        }
      }
      socket.onclose = () => {
        if (stopped) return
        clearTimeout(reconnectTimer)
        reconnectTimer = setTimeout(connect, RECONNECT_MS)
      }
      socket.onerror = () => {
        socket.close()
      }
    }

    connect()

    return () => {
      stopped = true
      clearTimeout(reconnectTimer)
      if (ws) {
        ws.onclose = null
        ws.onerror = null
        ws.onmessage = null
        ws.close()
      }
    }
  }, [queryClient])
}
