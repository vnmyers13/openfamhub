/** Whole cents → "$3.75" / "-$5.00". Allowance is stored and sent as integer cents. */
export function formatCents(cents: number): string {
  const sign = cents < 0 ? '-' : ''
  const abs = Math.abs(Math.trunc(cents))
  return `${sign}$${Math.floor(abs / 100).toLocaleString('en-US')}.${String(abs % 100).padStart(2, '0')}`
}

/** "3.75", "$3.75", "3" → 375 cents; null for anything that isn't a non-negative amount. */
export function parseDollars(text: string): number | null {
  const m = /^\s*\$?\s*(\d{1,6})(?:\.(\d{1,2}))?\s*$/.exec(text)
  if (!m) return null
  return Number(m[1]) * 100 + Number((m[2] ?? '0').padEnd(2, '0'))
}
