import { useEffect, useState } from 'react'
import WallBirthdays from './WallBirthdays'
import WallProgress from './WallProgress'
import WallRoutines from './WallRoutines'
import WallSevenDayStrip from './WallSevenDayStrip'
import { cycleState, WALL_CYCLE_PANELS } from './wallCycle'

function useNow(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

function PanelBody({ id, timeZone }: { id: string; timeZone: string }) {
  if (id === 'routines') return <WallRoutines timeZone={timeZone} />
  if (id === 'progress') {
    return (
      <div className="grid h-full content-start gap-8 overflow-y-auto p-8 lg:grid-cols-2">
        <section>
          <h2 className="mb-4 text-sm font-semibold uppercase tracking-wider text-slate-500">Family progress</h2>
          <WallProgress />
        </section>
        <WallBirthdays />
      </div>
    )
  }
  return <WallSevenDayStrip />
}

export default function WallCycle({ startedAt, timeZone }: { startedAt: number; timeZone: string }) {
  const now = useNow()
  const state = cycleState(WALL_CYCLE_PANELS, now.getTime(), startedAt)
  if (!state.panel) return null
  return (
    <div className="relative h-full w-full overflow-hidden">
      <div className="absolute left-6 right-6 top-4 z-10 flex items-center justify-between rounded-full bg-slate-950/80 px-5 py-2 shadow-lg backdrop-blur">
        <span className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">{state.panel.label}</span>
        <span className="font-mono text-sm text-amber-300" aria-label="Next wall panel">
          Next in {state.secondsLeft}s
        </span>
      </div>
      <div className="h-full pt-16">
        <PanelBody id={state.panel.id} timeZone={timeZone} />
      </div>
    </div>
  )
}
