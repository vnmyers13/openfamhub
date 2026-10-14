import { useEffect, useMemo, useState } from 'react'
import type { WorldClock } from '../api/family'
import type { WallDashboardConfig } from '../api/wall'
import WallClock from './WallClock'
import { WallDashboardPageView } from './WallDashboard'
import { cycleState } from './wallCycle'

function useNow(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(id)
  }, [])
  return now
}

const NO_CLOCKS: WorldClock[] = []  // stable, so the page memo below holds

/**
 * The wall board: the family's dashboard pages in turn, under a header bar
 * that always shows the time (family timezone, with any extra clocks), the
 * page's name and a countdown to the next page.
 */
export default function WallCycle({ startedAt, timeZone, dashboard, clocks = NO_CLOCKS }: {
  startedAt: number; timeZone: string; dashboard: WallDashboardConfig; clocks?: WorldClock[]
}) {
  const now = useNow()
  const panels = dashboard.pages.map((page, index) => ({ id: `page-${index}`, label: page.name, durationSeconds: page.duration_seconds }))
  const state = cycleState(panels, now.getTime(), startedAt)
  const page = state.panel ? dashboard.pages[state.index] : undefined
  // The countdown ticks every second; the page's cards redraw only when the
  // page changes (redrawing every card each second is heavy on a Pi).
  const body = useMemo(() => (page ? <WallDashboardPageView page={page} timeZone={timeZone} clocks={clocks} /> : null), [page, timeZone, clocks])
  if (!state.panel) return <div className="flex h-full items-center justify-center p-8 text-2xl text-slate-400">No wall dashboard pages configured.</div>
  return (
    <div className="relative h-full w-full overflow-hidden">
      <div className="absolute left-6 right-6 top-4 z-10 flex items-center justify-between gap-6 rounded-full bg-slate-950/80 px-5 py-2 shadow-lg backdrop-blur"
        data-testid="wall-header">
        <WallClock compact timeZone={timeZone} clocks={clocks} />
        <span className="shrink-0 text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">{state.panel.label}</span>
        <span className="shrink-0 font-mono text-sm text-amber-300" aria-label="Next wall panel">
          Next in {state.secondsLeft}s
        </span>
      </div>
      <div className="h-full pt-16">
        {body}
      </div>
    </div>
  )
}
