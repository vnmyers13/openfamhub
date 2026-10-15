import { format, isSameDay, subDays } from 'date-fns'
import type { CalendarEvent } from '../api/calendar'
import { eventEnd, eventStart } from './dates'

/** "Thu 15 Oct, 3:00 PM – 4:00 PM", "Thu 15 Oct – Sat 17 Oct, all day". */
export function whenText(e: CalendarEvent): string {
  const start = eventStart(e)
  const end = eventEnd(e)
  const day = (d: Date) => format(d, 'EEE d MMM')
  const time = (d: Date) => format(d, 'h:mm a')
  if (e.all_day) {
    const last = subDays(end, 1)
    return isSameDay(start, last) ? `${day(start)}, all day` : `${day(start)} – ${day(last)}, all day`
  }
  return isSameDay(start, end) ? `${day(start)}, ${time(start)} – ${time(end)}` : `${day(start)} ${time(start)} – ${day(end)} ${time(end)}`
}

/** A maps search for the place; it opens the phone's maps app where it has one. Nothing is looked up by our server. */
export function mapsUrl(location: string): string {
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(location)}`
}
