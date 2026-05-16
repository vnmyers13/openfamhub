import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { Calendar, dateFnsLocalizer, type View } from 'react-big-calendar'
import { format, parse, getDay, addMonths, subMonths, addWeeks, subWeeks, startOfMonth, endOfMonth, startOfWeek as sow, endOfWeek as eow, addDays, subDays } from 'date-fns'
import { enUS } from 'date-fns/locale/en-US'
import { useGesture } from '@use-gesture/react'
import { useCalendarEvents, useCalendarSources, useCreateEvent, useDeleteEvent } from '../api/calendar'
import { useAuthStore } from '../stores/auth'

type ViewType = 'month' | 'week' | 'day' | 'agenda'
interface RBCEvent {
  id: string
  title: string
  start: Date
  end: Date
  allDay: boolean
  resource: { color: string }
}

const locales = { 'en-US': enUS }
const localizer = dateFnsLocalizer({
  format,
  parse,
  startOfWeek: () => sow(new Date(), { weekStartsOn: 0 }),
  getDay,
  locales,
})

const VIEW_KEY = 'openfamhub_calendar_view'

export default function CalendarPage() {
  const { user: currentUser } = useAuthStore()
  const [view, setView] = useState<ViewType>(() => {
    return (localStorage.getItem(VIEW_KEY) as ViewType) || 'month'
  })
  const [date, setDate] = useState(new Date())
  const [filterIds, setFilterIds] = useState<Set<string>>(new Set())
  const [selectedEvent, setSelectedEvent] = useState<RBCEvent | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const swipeRef = useRef<HTMLDivElement>(null)
  const swipeCb = useRef({ view, date })

  swipeCb.current = { view, date }

  useGesture(
    {
      onDragEnd: ({ direction, velocity }) => {
        const dx = direction[0]
        if (Math.abs(dx) < 2 || velocity[0] < 0.3) return
        const { view: v, date: d } = swipeCb.current
        if (dx > 0) {
          setDate(v === 'month' ? subMonths(d, 1) : v === 'week' ? subWeeks(d, 1) : subDays(d, 1))
        } else {
          setDate(v === 'month' ? addMonths(d, 1) : v === 'week' ? addWeeks(d, 1) : addDays(d, 1))
        }
      },
    },
    { target: swipeRef, drag: { axis: 'x' } },
  )

  const dateRange = useMemo(() => getViewRange(view, date), [view, date])

  const { data: events = [] } = useCalendarEvents(
    dateRange.start,
    dateRange.end,
  )
  const { data: sources = [] } = useCalendarSources()

  useEffect(() => {
    localStorage.setItem(VIEW_KEY, view)
  }, [view])

  useEffect(() => {
    if (sources.length > 0 && filterIds.size === 0) {
      setFilterIds(new Set(sources.map((s) => s.id)))
    }
  }, [sources])

  const handleNavigate = useCallback((newDate: Date) => {
    setDate(newDate)
  }, [])

  const handleViewChange = useCallback((newView: View) => {
    if (newView === 'month' || newView === 'week' || newView === 'day' || newView === 'agenda') {
      setView(newView)
    }
  }, [])

  const handlePrev = () => {
    setDate((d) => {
      if (view === 'month') return subMonths(d, 1)
      if (view === 'week') return subWeeks(d, 1)
      return subDays(d, 1)
    })
  }

  const handleNext = () => {
    setDate((d) => {
      if (view === 'month') return addMonths(d, 1)
      if (view === 'week') return addWeeks(d, 1)
      return addDays(d, 1)
    })
  }

  const toggleFilter = (id: string) => {
    setFilterIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const filteredEvents = useMemo(() => {
    return events
      .filter((e) => filterIds.has(e.source_id))
      .map((e) => ({
        id: e.id,
        title: e.title,
        start: new Date(e.start_dt),
        end: new Date(e.end_dt),
        allDay: e.all_day,
        resource: { color: e.source_color_hex || '#4F46E5' },
      }))
  }, [events, filterIds])

  const { mutateAsync: createEvent } = useCreateEvent()
  const { mutateAsync: deleteEvent } = useDeleteEvent()

  const eventPropGetter = useCallback(
    (event: { resource?: { color?: string } }) => ({
      style: {
        backgroundColor: event.resource?.color || '#4F46E5',
        borderColor: event.resource?.color || '#4F46E5',
      },
    }),
    [],
  )

  const handleSelectEvent = useCallback((event: RBCEvent) => {
    setSelectedEvent(event)
  }, [])

  const handleDeleteEvent = async () => {
    if (!selectedEvent?.id) return
    await deleteEvent(selectedEvent.id)
    setSelectedEvent(null)
  }

  return (
    <div className="min-h-screen bg-gray-950 p-4">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold text-white">Calendar</h1>
          <button
            onClick={() => setShowCreate(true)}
            className="bg-primary hover:bg-primary-dark text-white px-4 py-2 rounded-lg font-medium"
          >
            + New Event
          </button>
        </div>

        {/* Source filter chips */}
        {sources.length > 0 && (
          <div className="flex gap-2 mb-4 flex-wrap">
            {sources.map((s) => (
              <button
                key={s.id}
                onClick={() => toggleFilter(s.id)}
                className={`px-3 py-1 rounded-full text-sm border transition ${
                  filterIds.has(s.id)
                    ? 'text-white border-transparent'
                    : 'text-gray-500 border-gray-700'
                }`}
                style={{
                  backgroundColor: filterIds.has(s.id) ? s.color_hex : 'transparent',
                }}
              >
                {s.display_name}
              </button>
            ))}
          </div>
        )}

        {/* Navigation */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex gap-2">
            <button onClick={handlePrev} className="text-gray-400 hover:text-white px-2">&larr;</button>
            <button onClick={() => setDate(new Date())} className="text-gray-400 hover:text-white text-sm px-2">Today</button>
            <button onClick={handleNext} className="text-gray-400 hover:text-white px-2">&rarr;</button>
          </div>
          <div className="text-white font-medium">
            {format(date, view === 'day' ? 'MMMM d, yyyy' : 'MMMM yyyy')}
          </div>
          <div className="flex gap-1 bg-gray-900 rounded-lg p-1">
            {(['month', 'week', 'day', 'agenda'] as ViewType[]).map((v) => (
              <button
                key={v}
                onClick={() => handleViewChange(v)}
                className={`px-3 py-1 rounded text-sm capitalize ${
                  view === v ? 'bg-primary text-white' : 'text-gray-400 hover:text-white'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        </div>

        {/* Calendar */}
        <div ref={swipeRef} className="bg-gray-900 rounded-xl p-2" style={{ minHeight: 600 }}>
          <Calendar
            localizer={localizer}
            events={filteredEvents}
            startAccessor="start"
            endAccessor="end"
            view={view}
            date={date}
            onNavigate={handleNavigate}
            onView={handleViewChange}
            eventPropGetter={eventPropGetter}
            onSelectEvent={handleSelectEvent}
            style={{ height: 600, color: '#fff' }}
            views={['month', 'week', 'day', 'agenda']}
          />
        </div>
      </div>

      {/* Event detail modal */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setSelectedEvent(null)}>
          <div className="bg-gray-900 rounded-xl p-6 max-w-md w-full border border-gray-800" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-white mb-2">{selectedEvent.title}</h2>
            <p className="text-gray-400 text-sm mb-1">
              {format(selectedEvent.start, 'MMM d, yyyy h:mm a')} &ndash; {format(selectedEvent.end, 'MMM d, yyyy h:mm a')}
            </p>
            {selectedEvent.allDay && <p className="text-gray-400 text-sm mb-1">All day</p>}
            {selectedEvent.resource && (
              <div className="flex items-center gap-2 mb-2">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: selectedEvent.resource.color }} />
                <span className="text-gray-400 text-sm">Family Calendar</span>
              </div>
            )}
            <div className="flex gap-2 mt-4">
              {currentUser?.role === 'admin' && (
                <button onClick={handleDeleteEvent} className="bg-red-700 hover:bg-red-600 text-white px-4 py-1.5 rounded text-sm">
                  Delete
                </button>
              )}
              <button onClick={() => setSelectedEvent(null)} className="text-gray-400 hover:text-white text-sm px-4 py-1.5">
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Create event modal */}
      {showCreate && (
        <CreateEventModal
          onClose={() => setShowCreate(false)}
          onCreate={async (data) => {
            await createEvent(data)
            setShowCreate(false)
          }}
        />
      )}
    </div>
  )
}

function CreateEventModal({
  onClose,
  onCreate,
}: {
  onClose: () => void
  onCreate: (data: { title: string; start_dt: string; end_dt: string; all_day?: boolean; location?: string; description?: string }) => Promise<void>
}) {
  const [title, setTitle] = useState('')
  const [startDate, setStartDate] = useState('')
  const [startTime, setStartTime] = useState('')
  const [endDate, setEndDate] = useState('')
  const [endTime, setEndTime] = useState('')
  const [allDay, setAllDay] = useState(false)
  const [location, setLocation] = useState('')
  const [description, setDescription] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    const now = new Date()
    const oneHourLater = new Date(now.getTime() + 60 * 60 * 1000)
    setStartDate(format(now, 'yyyy-MM-dd'))
    setStartTime(format(now, 'HH:mm'))
    setEndDate(format(oneHourLater, 'yyyy-MM-dd'))
    setEndTime(format(oneHourLater, 'HH:mm'))
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title) return
    setSaving(true)
    const startDt = allDay ? `${startDate}T00:00:00Z` : `${startDate}T${startTime}:00Z`
    const endDt = allDay ? `${endDate}T23:59:59Z` : `${endDate}T${endTime}:00Z`
    await onCreate({ title, start_dt: startDt, end_dt: endDt, all_day: allDay, location: location || undefined, description: description || undefined })
  }

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={onClose}>
      <form onSubmit={handleSubmit} className="bg-gray-900 rounded-xl p-6 max-w-md w-full border border-gray-800 space-y-3" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-white">New Event</h2>
        <input
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          placeholder="Event title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          required
        />
        <label className="flex items-center gap-2 text-gray-300 text-sm">
          <input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} />
          All day
        </label>
        <div className="grid grid-cols-2 gap-2">
          <div>
            <label className="block text-xs text-gray-400 mb-1">Start Date</label>
            <input type="date" className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
          </div>
          {!allDay && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">Start Time</label>
              <input type="time" className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" value={startTime} onChange={(e) => setStartTime(e.target.value)} />
            </div>
          )}
          <div>
            <label className="block text-xs text-gray-400 mb-1">End Date</label>
            <input type="date" className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
          </div>
          {!allDay && (
            <div>
              <label className="block text-xs text-gray-400 mb-1">End Time</label>
              <input type="time" className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm" value={endTime} onChange={(e) => setEndTime(e.target.value)} />
            </div>
          )}
        </div>
        <input
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white"
          placeholder="Location (optional)"
          value={location}
          onChange={(e) => setLocation(e.target.value)}
        />
        <textarea
          className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white resize-none"
          placeholder="Description (optional)"
          rows={3}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
        />
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-white text-sm px-4 py-1.5">Cancel</button>
          <button type="submit" disabled={saving} className="bg-primary hover:bg-primary-dark text-white px-4 py-1.5 rounded text-sm disabled:opacity-50">
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </form>
    </div>
  )
}

function getViewRange(view: ViewType, date: Date): { start: Date; end: Date } {
  if (view === 'month') {
    return { start: startOfMonth(date), end: endOfMonth(date) }
  }
  if (view === 'week') {
    return { start: sow(date, { weekStartsOn: 0 }), end: eow(date, { weekStartsOn: 0 }) }
  }
  const weekStart = sow(date, { weekStartsOn: 0 })
  const weekEnd = eow(date, { weekStartsOn: 0 })
  return { start: weekStart, end: weekEnd }
}
