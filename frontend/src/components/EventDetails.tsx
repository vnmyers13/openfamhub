import { useEffect, type ReactNode } from 'react'
import { useCalendarSources, type CalendarEvent } from '../api/calendar'
import { useFamilyMembers } from '../api/chores'
import { mapsUrl, whenText } from '../lib/eventText'

const SHOWN_ATTENDEES = 10
const URL_PART = /(https?:\/\/[^\s<>"']+[^\s<>"'.,;:!?)\]])/

/** Plain text with web links made clickable. React escapes the rest: nothing is rendered as HTML. */
export function Linkified({ text }: { text: string }) {
  return (
    <>
      {text.split(URL_PART).map((part, i) => (i % 2 === 1
        ? <a key={i} href={part} target="_blank" rel="noopener noreferrer" className="break-all text-primary hover:underline">{part}</a>
        : <span key={i}>{part}</span>))}
    </>
  )
}

function host(link: string): string {
  try {
    return new URL(link).host
  } catch {
    return link
  }
}

/**
 * One event in full: when, which calendar, where (a maps link), the notes
 * with clickable links, the event's own link, organizer and attendees from
 * feeds, and who added it. `children` are the actions the caller allows
 * (Delete in the Calendar, "Open the calendar" on Home).
 */
export default function EventDetails({ event, onClose, children, error }: {
  event: CalendarEvent; onClose: () => void; children?: ReactNode; error?: string
}) {
  const { data: sources = [] } = useCalendarSources()
  const { data: members = [] } = useFamilyMembers()
  const calendar = sources.find((s) => s.id === event.source_id)?.display_name ?? 'Calendar'
  const addedBy = event.created_by ? members.find((m) => m.id === event.created_by)?.display_name : null
  const attendees = event.attendees ?? []
  useEffect(() => {
    const onKey = (ev: KeyboardEvent) => { if (ev.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={event.title} onClick={(e) => e.stopPropagation()}
        className="max-h-[85vh] w-full max-w-md space-y-3 overflow-y-auto rounded-xl border border-gray-800 bg-gray-900 p-6">
        <h2 className="text-xl font-bold text-white">{event.title}</h2>
        <p className="text-sm text-gray-300">{whenText(event)}</p>
        <p className="flex items-center gap-2 text-sm text-gray-400">
          <span className="h-3 w-3 rounded-full" style={{ backgroundColor: event.source_color_hex }} />{calendar}
        </p>
        {event.location && (
          <p className="text-sm">
            <span aria-hidden="true">📍 </span>
            <a href={mapsUrl(event.location)} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline"
              aria-label={`Map: ${event.location}`}>{event.location}</a>
          </p>
        )}
        {event.description && (
          <p className="whitespace-pre-line break-words text-sm text-gray-200" data-testid="event-notes"><Linkified text={event.description} /></p>
        )}
        {event.url && (
          <p className="text-sm">
            <span aria-hidden="true">🔗 </span>
            <a href={event.url} target="_blank" rel="noopener noreferrer" className="text-primary hover:underline">{host(event.url)}</a>
          </p>
        )}
        {event.organizer && <p className="text-sm text-gray-400">Organized by {event.organizer}</p>}
        {attendees.length > 0 && (
          <p className="text-sm text-gray-400">
            With {attendees.slice(0, SHOWN_ATTENDEES).join(', ')}{attendees.length > SHOWN_ATTENDEES ? ` and ${attendees.length - SHOWN_ATTENDEES} more` : ''}
          </p>
        )}
        {addedBy && <p className="text-xs text-gray-500">Added by {addedBy}</p>}
        {error && <div className="rounded bg-red-900/50 px-3 py-2 text-sm text-red-300" role="alert">{error}</div>}
        <div className="flex flex-wrap gap-2 pt-1">
          {children}
          <button onClick={onClose} className="px-4 py-1.5 text-sm text-gray-400 hover:text-white">Close</button>
        </div>
      </div>
    </div>
  )
}
