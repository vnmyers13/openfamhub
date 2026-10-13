/** Chore/routine repeat rules (mirrors the API's Repeat schema) in words. */
export type WeekdayCode = 'mo' | 'tu' | 'we' | 'th' | 'fr' | 'sa' | 'su'

export interface Repeat {
  every: 'none' | 'day' | 'week' | 'month'
  interval?: number
  weekdays?: WeekdayCode[] | null
  month_day?: number | null
}

export const WEEKDAYS: { code: WeekdayCode; short: string }[] = [
  { code: 'mo', short: 'Mon' }, { code: 'tu', short: 'Tue' }, { code: 'we', short: 'Wed' },
  { code: 'th', short: 'Thu' }, { code: 'fr', short: 'Fri' }, { code: 'sa', short: 'Sat' }, { code: 'su', short: 'Sun' },
]

const JS_DAY_TO_CODE: WeekdayCode[] = ['su', 'mo', 'tu', 'we', 'th', 'fr', 'sa']

function localDate(iso: string): Date {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function ordinal(n: number): string {
  const s = n % 100 >= 11 && n % 100 <= 13 ? 'th' : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[n % 10] ?? 'th'
  return `${n}${s}`
}

function joinDays(codes: WeekdayCode[]): string {
  const names = WEEKDAYS.filter((w) => codes.includes(w.code)).map((w) => w.short)
  return names.length > 1 ? `${names.slice(0, -1).join(', ')} & ${names[names.length - 1]}` : names[0] ?? ''
}

export function describeRepeat(repeat: Repeat | null | undefined, startDate: string): string {
  const start = localDate(startDate)
  const every = repeat?.every ?? 'none'
  const n = Math.max(1, repeat?.interval ?? 1)
  if (every === 'none') {
    return `Once, ${start.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }).replace(',', '')}`
  }
  if (every === 'day') return n === 1 ? 'Every day' : `Every ${n} days`
  if (every === 'week') {
    const days = repeat?.weekdays?.length ? repeat.weekdays : [JS_DAY_TO_CODE[start.getDay()]]
    if (n === 1 && days.length === 5 && !days.includes('sa') && !days.includes('su')) return 'Weekdays'
    return n === 1 ? `Every ${joinDays(days)}` : `Every ${n} weeks on ${joinDays(days)}`
  }
  const day = repeat?.month_day ?? start.getDate()
  const on = day === -1 ? 'the last day' : `the ${ordinal(day)}`
  return n === 1 ? `Monthly on ${on}` : `Every ${n} months on ${on}`
}
