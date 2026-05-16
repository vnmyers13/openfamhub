import { useEffect, useMemo } from 'react'
import { addDays, format, parseISO, startOfDay } from 'date-fns'
import { useQueryClient } from '@tanstack/react-query'
import { useCalendarEvents } from '../api/calendar'
import { cn } from '../lib/utils'

interface CalendarEvent {
  id: string
  source_id: string
  title: string
  start_dt: string
  end_dt: string
  all_day: boolean
  location: string | null
  description: string | null
  created_by: string | null
  source_color_hex: string
}

function useWallWebSocket() {
  const queryClient = useQueryClient()

  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const url = `${protocol}//${window.location.host}/api/ws/wall`
    let ws: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout>

    function connect() {
      ws = new WebSocket(url)
      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          if (msg.type === 'calendar_updated') {
            queryClient.invalidateQueries({ queryKey: ['calendar-events'] })
          }
        } catch {
          // ignore parse errors
        }
      }
      ws.onclose = () => {
        reconnectTimer = setTimeout(connect, 10000)
      }
      ws.onerror = () => {
        ws?.close()
      }
    }

    connect()

    return () => {
      clearTimeout(reconnectTimer)
      ws?.close()
    }
  }, [queryClient])
}

export default function WallSevenDayStrip() {
  useWallWebSocket()

  const today = useMemo(() => startOfDay(new Date()), [])
  const days = useMemo(
    () => Array.from({ length: 7 }, (_, i) => addDays(today, i)),
    [today],
  )

  const startStr = days[0].toISOString()
  const endStr = addDays(days[6], 1).toISOString()

  const { data: events = [] } = useCalendarEvents(
    new Date(startStr),
    new Date(endStr),
  )

  const grouped = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {}
    for (const day of days) {
      const key = format(day, 'yyyy-MM-dd')
      map[key] = []
    }
    for (const ev of events) {
      const d = parseISO(ev.start_dt)
      const key = format(d, 'yyyy-MM-dd')
      if (map[key]) {
        map[key].push(ev)
      }
    }
    for (const key of Object.keys(map)) {
      map[key].sort(
        (a, b) => new Date(a.start_dt).getTime() - new Date(b.start_dt).getTime(),
      )
    }
    return map
  }, [events, days])

  const todayKey = format(today, 'yyyy-MM-dd')

  return (
    <div className="flex h-full w-full">
      {days.map((day) => {
        const key = format(day, 'yyyy-MM-dd')
        const dayEvents = grouped[key] ?? []
        const isToday = key === todayKey
        const display = dayEvents.slice(0, 5)
        const more = dayEvents.length - 5

        return (
          <div
            key={key}
            className={cn(
              'flex flex-1 flex-col border-r border-slate-700 px-2 py-4 last:border-r-0',
            )}
          >
            <div
              className={cn(
                'mb-3 rounded px-3 py-1 text-center text-xl font-semibold',
                isToday
                  ? 'bg-white text-slate-900'
                  : 'text-slate-300',
              )}
            >
              {format(day, 'EEE d')}
            </div>
            <div className="flex flex-col gap-2 overflow-y-auto">
              {display.map((ev) => (
                <div
                  key={ev.id}
                  className="flex flex-col rounded bg-slate-800/60 px-2 py-1.5 text-sm leading-tight"
                  style={{
                    borderLeft: `4px solid ${ev.source_color_hex || '#6366f1'}`,
                  }}
                >
                  <span className="truncate font-medium text-white">
                    {ev.title}
                  </span>
                  {!ev.all_day && (
                    <span className="text-xs text-slate-400">
                      {format(parseISO(ev.start_dt), 'HH:mm')}
                    </span>
                  )}
                  {ev.all_day && (
                    <span className="text-xs text-slate-500">All day</span>
                  )}
                </div>
              ))}
              {more > 0 && (
                <span className="text-xs text-slate-500">+{more} more</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
