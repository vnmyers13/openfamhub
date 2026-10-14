import { useEffect, useState } from 'react'
import type { WallDashboardConfig } from '../api/wall'
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

export default function WallCycle({ startedAt, timeZone, dashboard }: { startedAt: number; timeZone: string; dashboard: WallDashboardConfig }) {
  const now = useNow()
  const panels = dashboard.pages.map((page, index) => ({ id: `page-${index}`, label: page.name, durationSeconds: page.duration_seconds }))
  const state = cycleState(panels, now.getTime(), startedAt)
  if (!state.panel) return <div className="flex h-full items-center justify-center p-8 text-2xl text-slate-400">No wall dashboard pages configured.</div>
  const page = dashboard.pages[state.index]
  return (
    <div className="relative h-full w-full overflow-hidden">
      <div className="absolute left-6 right-6 top-4 z-10 flex items-center justify-between rounded-full bg-slate-950/80 px-5 py-2 shadow-lg backdrop-blur">
        <span className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-300">{state.panel.label}</span>
        <span className="font-mono text-sm text-amber-300" aria-label="Next wall panel">
          Next in {state.secondsLeft}s
        </span>
      </div>
      <div className="h-full pt-16">
        <WallDashboardPageView page={page} timeZone={timeZone} />
      </div>
    </div>
  )
}
