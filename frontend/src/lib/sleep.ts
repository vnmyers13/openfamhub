/**
 * The wall's sleep schedule. Times are HH:MM wall-clock times in the *family*
 * timezone (from the wall session), evaluated with Intl so they follow DST and
 * don't depend on the zone the display device is set to.
 */
export interface SleepSchedule {
  enabled: boolean
  off: string // screen goes dark
  on: string // screen comes back
}

function toMinutes(hhmm: string): number {
  const [h, m] = hhmm.split(':').map(Number)
  return h * 60 + m
}

/** Minutes past local midnight in `timeZone` (UTC if the zone is unknown). */
export function minutesInZone(now: Date, timeZone: string): number {
  let parts: Intl.DateTimeFormatPart[]
  try {
    parts = new Intl.DateTimeFormat('en-GB', { timeZone, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(now)
  } catch {
    parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(now)
  }
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value ?? 0)
  return (get('hour') % 24) * 60 + get('minute')
}

/** Whether the screen should be dark at `now`. off > on means overnight. */
export function isAsleep(now: Date, schedule: SleepSchedule | null | undefined, timeZone: string): boolean {
  if (!schedule?.enabled) return false
  const t = minutesInZone(now, timeZone)
  const off = toMinutes(schedule.off)
  const on = toMinutes(schedule.on)
  return off < on ? t >= off && t < on : t >= off || t < on
}
