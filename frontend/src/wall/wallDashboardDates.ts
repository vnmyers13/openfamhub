function dateParts(date: Date, timeZone: string): { year: number; month: number; day: number } {
  const values = new Intl.DateTimeFormat('en-CA', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(date)
  const get = (type: string) => Number(values.find((part) => part.type === type)?.value)
  return { year: get('year'), month: get('month'), day: get('day') }
}

function keyOf({ year, month, day }: { year: number; month: number; day: number }): string {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

function zonedMidnight(key: string, timeZone: string): Date {
  const [year, month, day] = key.split('-').map(Number)
  const target = Date.UTC(year, month - 1, day)
  let instant = target
  // The zone's offset may change at midnight; converge on the instant whose local clock is midnight.
  for (let i = 0; i < 3; i++) {
    const parts = new Intl.DateTimeFormat('en-GB', { timeZone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(new Date(instant))
    const get = (type: string) => Number(parts.find((part) => part.type === type)?.value)
    const localEpoch = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
    instant = target - (localEpoch - instant)
  }
  return new Date(instant)
}

export function familyDayRange(now: Date, timeZone: string): { start: Date; end: Date; dateKey: string } {
  const dateKey = keyOf(dateParts(now, timeZone))
  const [year, month, day] = dateKey.split('-').map(Number)
  const nextKey = keyOf(dateParts(new Date(Date.UTC(year, month - 1, day + 1, 12)), 'UTC'))
  return { start: zonedMidnight(dateKey, timeZone), end: zonedMidnight(nextKey, timeZone), dateKey }
}
