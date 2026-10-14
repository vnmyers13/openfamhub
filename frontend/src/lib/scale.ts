/**
 * Scale an ingredient line's leading quantity: "1 1/2 cups flour" × 2 →
 * "3 cups flour". Quantities are free text, so only a number at the start
 * is scaled (whole, decimal, fraction, mixed, unicode ½, or a range like
 * "2-3"); anything else ("Salt to taste") is left alone.
 */
const UNICODE: Record<string, number> = { '¼': 0.25, '½': 0.5, '¾': 0.75, '⅓': 1 / 3, '⅔': 2 / 3, '⅛': 0.125, '⅜': 0.375, '⅝': 0.625, '⅞': 0.875 }
const FRACTIONS: [number, string][] = [[0, ''], [1 / 8, '1/8'], [1 / 4, '1/4'], [1 / 3, '1/3'], [3 / 8, '3/8'], [1 / 2, '1/2'],
  [5 / 8, '5/8'], [2 / 3, '2/3'], [3 / 4, '3/4'], [7 / 8, '7/8'], [1, '']]

// A number: "1 1/2", "1½", "3/4", "1.5", "2", "½"
const NUM = String.raw`(?:\d+\s+\d+\/\d+|\d+\s*[¼½¾⅓⅔⅛⅜⅝⅞]|\d+\/\d+|\d+(?:\.\d+)?|[¼½¾⅓⅔⅛⅜⅝⅞])`
const LEADING = new RegExp(String.raw`^\s*(${NUM})(?:\s*(?:-|–|to)\s*(${NUM}))?`)

export function parseQuantity(text: string): number | null {
  const t = text.trim()
  let m = /^(\d+)\s+(\d+)\/(\d+)$/.exec(t)
  if (m) return Number(m[1]) + Number(m[2]) / Number(m[3])
  m = /^(\d+)\s*([¼½¾⅓⅔⅛⅜⅝⅞])$/.exec(t)
  if (m) return Number(m[1]) + UNICODE[m[2]]
  m = /^(\d+)\/(\d+)$/.exec(t)
  if (m) return Number(m[2]) === 0 ? null : Number(m[1]) / Number(m[2])
  if (t in UNICODE) return UNICODE[t]
  return /^\d+(\.\d+)?$/.test(t) ? Number(t) : null
}

/** 1.5 → "1 1/2", 0.333 → "1/3", 2.4 → "2.4" (when no kitchen fraction is close). */
export function formatQuantity(n: number): string {
  if (n <= 0) return '0'
  const whole = Math.floor(n + 1e-9)
  const frac = n - whole
  let best = FRACTIONS[0]
  for (const f of FRACTIONS) if (Math.abs(frac - f[0]) < Math.abs(frac - best[0])) best = f
  if (Math.abs(frac - best[0]) > 0.02) return String(Math.round(n * 100) / 100)
  const w = best[0] === 1 ? whole + 1 : whole
  if (!best[1]) return String(w)
  return w ? `${w} ${best[1]}` : best[1]
}

export function scaleLine(line: string, factor: number): string {
  if (factor === 1) return line
  const m = LEADING.exec(line)
  if (!m) return line
  const a = parseQuantity(m[1])
  if (a === null) return line
  const b = m[2] !== undefined ? parseQuantity(m[2]) : null
  const scaled = b !== null ? `${formatQuantity(a * factor)}-${formatQuantity(b * factor)}` : formatQuantity(a * factor)
  return scaled + line.slice(m[0].length)
}
