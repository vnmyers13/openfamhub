import { useEffect, useRef, useState } from 'react'
import { getWallSession, pairWall } from '../api/wall'
import WallClock from './WallClock'
import WallSevenDayStrip from './WallSevenDayStrip'
import WallMemberList from './WallMemberList'
import WallPhotoPlaceholder from './WallPhotoPlaceholder'

const IDLE_MS = 300_000

type PairState = 'checking' | 'paired' | 'unpaired'

/**
 * Pairing gate: /wall?token=... (from Admin > Wall displays) pairs this browser
 * once; afterwards the device cookie is refreshed on every load.
 */
export default function WallLayout() {
  const [state, setState] = useState<PairState>('checking')

  useEffect(() => {
    let cancelled = false
    async function check() {
      const params = new URLSearchParams(window.location.search)
      const token = params.get('token')
      try {
        if (token) {
          await pairWall(token)
          // Keep the token out of history and screenshots.
          window.history.replaceState(null, '', '/wall')
        }
        await getWallSession()
        if (!cancelled) setState('paired')
      } catch {
        if (!cancelled) setState('unpaired')
      }
    }
    check()
    return () => {
      cancelled = true
    }
  }, [])

  if (state === 'checking') return <div className="fixed inset-0 bg-slate-900" />
  if (state === 'unpaired') {
    return (
      <div className="fixed inset-0 flex flex-col items-center justify-center gap-4 bg-slate-900 p-8 text-center">
        <WallClock className="items-center" />
        <p className="max-w-lg text-lg text-slate-400">
          This display isn't paired yet. An admin can create a pairing link under
          <span className="text-slate-200"> Admin › Wall displays</span> and open it on this screen.
        </p>
      </div>
    )
  }
  return <WallBoard />
}

function WallBoard() {
  const [isIdle, setIsIdle] = useState(false)
  const idleRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)

  const resetIdle = () => {
    setIsIdle(false)
    if (idleRef.current) clearTimeout(idleRef.current)
    idleRef.current = setTimeout(() => setIsIdle(true), IDLE_MS)
  }

  useEffect(() => {
    const handlers = ['touchstart', 'mousemove'] as const
    for (const ev of handlers) {
      window.addEventListener(ev, resetIdle)
    }
    // Start the first idle countdown (state is already "not idle").
    idleRef.current = setTimeout(() => setIsIdle(true), IDLE_MS)
    return () => {
      for (const ev of handlers) {
        window.removeEventListener(ev, resetIdle)
      }
      if (idleRef.current) clearTimeout(idleRef.current)
    }
  }, [])

  if (isIdle) {
    return (
      <div
        className="fixed inset-0 z-50 cursor-pointer"
        onClick={resetIdle}
      >
        <WallPhotoPlaceholder fullscreen />
        <div className="absolute bottom-8 right-8">
          <WallClock />
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 grid overflow-hidden bg-slate-900"
      style={{
        gridTemplateColumns: '380px 1fr',
      }}
    >
      {/* Left panel */}
      <div className="flex flex-col gap-8 border-r border-slate-700 p-8">
        <WallClock />
        <div>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">
            Family
          </h2>
          <WallMemberList />
        </div>
      </div>

      {/* Right panel */}
      <WallSevenDayStrip />
    </div>
  )
}
