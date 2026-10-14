/**
 * Turn the text OCR read off a photo of a shopping list into list items
 * (Phase 10). Pure, so it's tested against real OCR output without running
 * OCR. Each line is classified:
 *   item     a thing to buy, with an optional quantity ("2 lb apples")
 *   heading  a section title ("Produce:", "DAIRY", "Shopping list")
 *   noise    OCR debris (borders, smudges, stray punctuation)
 * Only items are offered for the list, and a repeat of an earlier item is
 * unticked so it isn't added twice. People can still change anything in the
 * preview before adding.
 */
export type LineKind = 'item' | 'heading' | 'noise'

export interface ListLine {
  text: string
  kind: LineKind
  name: string
  quantity: string | null
  include: boolean
  duplicate?: boolean
}

const NAME_MAX = 256
const QUANTITY_MAX = 64

// "- ", "* ", "• ", "☐ ", "[ ] ", "[x] ", "1. ", "2) ", "o ", and stray "|" from a page edge.
const BULLET = /^(?:[|¦]+\s*)?(?:(?:[-*•·▪◦‣–—]|☐|☑|☒|□|■|\[[ xX✓]?\]|\(\s?\)|\d{1,2}[.)](?=\s)|o(?=\s))\s*)?/
const UNITS = 'lbs?|lb\\.|[|I]bs?|pounds?|oz|ounces?|kg|g|grams?|l|liters?|litres?|ml|gal(?:lons?)?|qt|quarts?|pints?|dozen|doz|pk|packs?|packets?|cans?|bags?|boxes?|bottles?|jars?|bunch(?:es)?|heads?|loaf|loaves|cartons?|rolls?|bars?|tubs?'
const NUMBER = '(?:\\d+(?:[.,/]\\d+)?|[½¼¾⅓⅔]|\\d+\\s?[½¼¾])'
const LEADING_QTY = new RegExp(`^(${NUMBER})\\s*(?:(${UNITS})\\b\\.?|[x×])?\\s+(?=\\S)`, 'i')
const TRAILING_X = /\s*[x×]\s*(\d+)$/i
const TRAILING_PAREN = /\s*\((\d+[^)]{0,12})\)$/
const SECTIONS = /^(?:shopping(?: list)?|grocer(?:y|ies)(?: list)?|to buy|list|produce|fruits?(?: (?:&|and) veg(?:etables?|gies)?)?|vegetables|veg|dairy|meats?|meat (?:&|and) fish|seafood|bakery|frozen|pantry|deli|household|cleaning|snacks|drinks|beverages|canned(?: goods)?|baking|spices|toiletries|misc(?:ellaneous)?|other)$/i

function tidy(s: string): string {
  return s.replace(/\s+/g, ' ').replace(/^["'`]+|["'`]+$/g, '').replace(/\s*[.,;:]+$/, '').trim()
}

function capitalize(s: string): string {
  return s.charAt(0).toUpperCase() + s.slice(1)
}

function classify(line: string): LineKind {
  const letters = (line.match(/\p{L}/gu) ?? []).length
  const visible = line.replace(/\s/g, '').length
  if (letters < 2 || letters / visible < 0.5) return 'noise'
  const bare = line.replace(BULLET, '').trim()
  if (/:\s*$/.test(bare) || SECTIONS.test(bare.replace(/:\s*$/, ''))) return 'heading'
  return 'item'
}

/** Split an item line into name and quantity. */
function readItem(line: string): { name: string; quantity: string | null } {
  let rest = tidy(line.replace(BULLET, ''))
  let quantity: string | null = null
  const lead = rest.match(LEADING_QTY)
  if (lead) {
    // OCR often reads "lb" as "|b" or "Ib".
    const unit = lead[2]?.replace(/\.$/, '').replace(/^[|I](?=bs?$)/, 'l')
    quantity = unit ? `${lead[1]} ${unit}` : lead[1]
    rest = rest.slice(lead[0].length)
  } else {
    const tail = rest.match(TRAILING_X) ?? rest.match(TRAILING_PAREN)
    if (tail) {
      quantity = tail[1].trim()
      rest = rest.slice(0, tail.index)
    }
  }
  return { name: capitalize(tidy(rest)).slice(0, NAME_MAX), quantity: quantity ? quantity.slice(0, QUANTITY_MAX) : null }
}

export function parseListLines(text: string): ListLine[] {
  const seen = new Set<string>()
  const out: ListLine[] = []
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim()
    if (!line) continue
    const kind = classify(line)
    if (kind !== 'item') {
      out.push({ text: line, kind, name: tidy(line.replace(BULLET, '')), quantity: null, include: false })
      continue
    }
    const { name, quantity } = readItem(line)
    const key = name.toLowerCase()
    const duplicate = seen.has(key)
    seen.add(key)
    out.push({ text: line, kind, name, quantity, include: !duplicate && !!name, ...(duplicate ? { duplicate } : {}) })
  }
  return out
}
