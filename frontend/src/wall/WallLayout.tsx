import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getWallSession, onWallUnauthorized, pairWall, type WallSession } from '../api/wall'
import { isAsleep } from '../lib/sleep'
import WallClock from './WallClock'
import WallProgress from './WallProgress'
import WallBirthdays from './WallBirthdays'
import WallSlideshow from './WallSlideshow'
import WallRoutines from './WallRoutines'
import WallCycle from './WallCycle.tsx'
import { useWallWebSocket } from './useWallWebSocket'

const DEFAULT_IDLE_MS = 300_000
const SLEEP_CHECK_MS = 30_000

type PairState = 'checking' | 'paired' | 'unpaired'

/**
 * Pairing gate: /wall?token=... (from Admin > Wall displays) pairs this browser
 * once; afterwards the device cookie is refreshed on every load.
 */
export default function WallLayout() {
  const [state, setState] = useState<PairState>('checking')
  const [session, setSession] = useState<WallSession | null>(null)

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
        const first = await getWallSession()
        if (cancelled) return
        setSession(first)
        setState('paired')
      } catch {
        if (!cancelled) setState('unpaired')
      }
    }
    check()
    return () => {
      cancelled = true
    }
  }, [])

  // Once paired, a 401 from any display request means this device was revoked
  // (or its cookie expired): forget the board's data and show the pairing
  // screen instead of a frozen calendar.
  const queryClient = useQueryClient()
  useEffect(() => {
    if (state !== 'paired') return
    return onWallUnauthorized(() => {
      for (const key of ['wall-events', 'wall-progress', 'wall-routines', 'wall-birthdays', 'wall-media', 'wall-session']) {
        queryClient.removeQueries({ queryKey: [key] })
      }
      setState('unpaired')
    })
  }, [state, queryClient])

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
  return <WallBoard initialSession={session as WallSession} />
}

/** The current time, refreshed every `ms` (for schedule checks). */
function useNow(ms: number): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), ms)
    return () => clearInterval(id)
  }, [ms])
  return now
}

function WallBoard({ initialSession }: { initialSession: WallSession }) {
  useWallWebSocket() // one live-update socket for the whole board
  // Kept fresh by settings_updated pushes (and a slow poll as a backstop).
  const { data: session = initialSession } = useQuery({
    queryKey: ['wall-session'],
    queryFn: getWallSession,
    initialData: initialSession,
    refetchInterval: 15 * 60 * 1000,
  })
  const idleMs = session.idle_timeout_seconds > 0 ? session.idle_timeout_seconds * 1000 : DEFAULT_IDLE_MS

  const [isIdle, setIsIdle] = useState(false)
  const [wokenUntil, setWokenUntil] = useState(0)
  const [cycleStartedAt] = useState(() => Date.now())
  const idleRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined)
  const now = useNow(SLEEP_CHECK_MS)
  const scheduled = isAsleep(now, session.sleep, session.timezone)
  const asleep = scheduled && now.getTime() >= wokenUntil

  // Any touch or mouse movement wakes the board and restarts the countdown;
  // during the sleep schedule it lights the screen for one idle period.
  useEffect(() => {
    const restart = () => {
      setIsIdle(false)
      setWokenUntil(Date.now() + idleMs)
      if (idleRef.current) clearTimeout(idleRef.current)
      idleRef.current = setTimeout(() => setIsIdle(true), idleMs)
    }
    const handlers = ['touchstart', 'mousemove', 'click'] as const
    for (const ev of handlers) window.addEventListener(ev, restart)
    // First countdown (state is already "not idle").
    idleRef.current = setTimeout(() => setIsIdle(true), idleMs)
    return () => {
      for (const ev of handlers) window.removeEventListener(ev, restart)
      if (idleRef.current) clearTimeout(idleRef.current)
    }
  }, [idleMs])

  if (asleep) {
    // Scheduled sleep: a dark screen until someone touches it.
    return <div className="fixed inset-0 z-50 cursor-none bg-black" data-testid="wall-asleep" />
  }

  if (isIdle) {
    return (
      // A tap anywhere wakes the board (the window "click" listener above).
      <div className="fixed inset-0 z-50 cursor-pointer">
        <WallSlideshow />
        <div className="absolute bottom-8 right-8 z-[60] drop-shadow-lg">
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
          <WallProgress />
        </div>
        <WallBirthdays />
        <WallRoutines timeZone={session.timezone} />
      </div>

      {/* Right panel */}
      <WallCycle startedAt={cycleStartedAt} timeZone={session.timezone} />
    </div>
  )
}
