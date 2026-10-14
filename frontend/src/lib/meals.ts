import { addDays, format, parseISO } from 'date-fns'

/** The Monday `weeks` weeks after (or before) `weekStart` ("yyyy-MM-dd"). */
export function shiftWeek(weekStart: string, weeks: number): string {
  return format(addDays(parseISO(weekStart), weeks * 7), 'yyyy-MM-dd')
}

/** "Mon 13" for a plan column. */
export function dayLabel(day: string): string {
  return format(parseISO(day), 'EEE d')
}

/** "Oct 13 – 19" / "Oct 27 – Nov 2" for the week header. */
export function weekLabel(weekStart: string): string {
  const start = parseISO(weekStart)
  const end = addDays(start, 6)
  return start.getMonth() === end.getMonth()
    ? `${format(start, 'MMM d')} – ${format(end, 'd')}`
    : `${format(start, 'MMM d')} – ${format(end, 'MMM d')}`
}

/** "45 min", "1 hr 15 min", or null. */
export function minutesLabel(minutes: number | null | undefined): string | null {
  if (!minutes) return null
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return [h ? `${h} hr` : '', m ? `${m} min` : ''].filter(Boolean).join(' ')
}

/** Lines typed in a textarea → trimmed, non-empty lines. */
export function toLines(text: string): string[] {
  return text.split('\n').map((l) => l.trim()).filter(Boolean)
}
