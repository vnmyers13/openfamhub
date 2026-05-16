import { Suspense } from 'react'
import { useAuthStore } from '../stores/auth'
import { useCalendarEvents, useCalendarSources } from '../api/calendar'
import { startOfDay, endOfDay } from 'date-fns'

function Greeting() {
  const user = useAuthStore((s) => s.user)
  const hour = new Date().getHours()
  let period = 'evening'
  if (hour < 12) period = 'morning'
  else if (hour < 17) period = 'afternoon'
  return (
    <h1 className="text-3xl font-bold text-white">
      Good {period}, {user?.display_name ?? 'there'}!
    </h1>
  )
}

function TodaysEventsWidget() {
  const today = new Date()
  const { data: events = [], isLoading } = useCalendarEvents(
    startOfDay(today),
    endOfDay(today),
  )

  if (isLoading) {
    return (
      <div className="animate-pulse rounded-xl bg-slate-800 p-4">
        <div className="mb-2 h-4 w-32 rounded bg-slate-700" />
        <div className="h-3 w-48 rounded bg-slate-700" />
      </div>
    )
  }

  return (
    <div className="rounded-xl bg-slate-800 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">Today's Events</h2>
      {events.length === 0 && (
        <p className="text-sm text-slate-400">No events scheduled for today.</p>
      )}
      <div className="flex flex-col gap-2">
        {events.map((ev) => (
          <div
            key={ev.id}
            className="flex items-center gap-3 rounded bg-slate-700/50 px-3 py-2"
          >
            <span
              className="h-3 w-3 shrink-0 rounded-full"
              style={{ backgroundColor: ev.source_color_hex }}
            />
            <span className="flex-1 truncate text-sm text-slate-200">{ev.title}</span>
            <span className="text-xs text-slate-400">
              {ev.all_day
                ? 'All day'
                : new Date(ev.start_dt).toLocaleTimeString([], {
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

function SyncStatusWidget() {
  const { data: sources = [], isLoading } = useCalendarSources()

  if (isLoading) {
    return (
      <div className="animate-pulse rounded-xl bg-slate-800 p-4">
        <div className="mb-2 h-4 w-40 rounded bg-slate-700" />
        <div className="h-3 w-32 rounded bg-slate-700" />
      </div>
    )
  }

  const errors = sources.filter((s) => s.sync_error)

  return (
    <div className="rounded-xl bg-slate-800 p-4">
      <h2 className="mb-3 text-lg font-semibold text-white">Sync Status</h2>
      <p className="text-sm text-slate-400">
        {sources.length} source{sources.length !== 1 ? 's' : ''} configured
      </p>
      {errors.length > 0 && (
        <div className="mt-2 rounded bg-red-900/30 px-3 py-2 text-sm text-red-300">
          {errors.length} source{errors.length !== 1 ? 's' : ''} with errors
        </div>
      )}
      {errors.length === 0 && sources.length > 0 && (
        <p className="mt-2 text-sm text-green-400">All sources healthy</p>
      )}
    </div>
  )
}

export default function Dashboard() {
  const user = useAuthStore((s) => s.user)
  const isAdmin = user?.role === 'admin' || user?.role === 'co_admin'

  return (
    <div className="flex flex-col gap-6 p-6">
      <Greeting />
      <div className="grid gap-6 md:grid-cols-2">
        <Suspense
          fallback={
            <div className="animate-pulse rounded-xl bg-slate-800 p-4">
              <div className="mb-2 h-4 w-32 rounded bg-slate-700" />
            </div>
          }
        >
          <TodaysEventsWidget />
        </Suspense>
        {isAdmin && (
          <Suspense
            fallback={
              <div className="animate-pulse rounded-xl bg-slate-800 p-4">
                <div className="mb-2 h-4 w-40 rounded bg-slate-700" />
              </div>
            }
          >
            <SyncStatusWidget />
          </Suspense>
        )}
      </div>
    </div>
  )
}
