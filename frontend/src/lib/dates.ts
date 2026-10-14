import { addDays, format, parseISO, startOfDay } from 'date-fns'

/**
 * The API returns UTC instants with an explicit offset ("...+00:00").
 *
 * Timed events are real instants: `new Date(iso)` shows them in the viewer's zone.
 * All-day events are calendar dates, stored as 00:00 UTC with an exclusive end
 * (same convention as iCal DTSTART;VALUE=DATE / DTEND). They must NOT be shifted
 * into the local zone, or they land on the previous day west of UTC, so we take
 * the date part and build a local midnight from it.
 */
export interface EventTimes {
  start_dt: string
  end_dt: string
  all_day: boolean
}

function localMidnightFromUtcDate(iso: string): Date {
  return parseISO(iso.slice(0, 10))
}

export function eventStart(e: EventTimes): Date {
  return e.all_day ? localMidnightFromUtcDate(e.start_dt) : new Date(e.start_dt)
}

export function eventEnd(e: EventTimes): Date {
  if (!e.all_day) return new Date(e.end_dt)
  const start = eventStart(e)
  const end = localMidnightFromUtcDate(e.end_dt)
  // Older events used an inclusive 23:59:59 end; treat them as one-day.
  return end > start ? end : addDays(start, 1)
}

/**
 * Local calendar days ("yyyy-MM-dd") an event appears on: every day it
 * overlaps. Ends are exclusive, so an event ending at midnight stays off the
 * next day; a zero-length event still shows on its start day.
 */
export function eventDayKeys(e: EventTimes): string[] {
  const start = eventStart(e)
  const end = eventEnd(e)
  const keys: string[] = []
  for (let d = startOfDay(start); d < end; d = addDays(d, 1)) keys.push(format(d, 'yyyy-MM-dd'))
  return keys.length ? keys : [format(start, 'yyyy-MM-dd')]
}

/** "yyyy-MM-dd" from a date input -> API value for an all-day start. */
export function allDayStartIso(date: string): string {
  return `${date}T00:00:00Z`
}

/** Inclusive last day from a date input -> exclusive API end (next day 00:00Z). */
export function allDayEndIso(lastDate: string): string {
  return `${format(addDays(parseISO(lastDate), 1), 'yyyy-MM-dd')}T00:00:00Z`
}

/** Local date + time inputs -> UTC ISO instant. */
export function localDateTimeIso(date: string, time: string): string {
  return new Date(`${date}T${time}`).toISOString()
}

/**
 * An imported event (API times) → the new-event form's inputs: local dates and
 * times, with an all-day event's exclusive end turned back into its last day.
 */
export function eventFormInputs(e: EventTimes): { startDate: string; startTime: string; endDate: string; endTime: string } {
  const start = eventStart(e)
  const end = eventEnd(e)
  const last = e.all_day ? addDays(end, -1) : end
  return {
    startDate: format(start, 'yyyy-MM-dd'), startTime: format(start, 'HH:mm'),
    endDate: format(last, 'yyyy-MM-dd'), endTime: format(end, 'HH:mm'),
  }
}
