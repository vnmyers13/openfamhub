/**
 * Photo → recipe (Phase 10). OCR keeps a photo's line breaks, so a step that
 * wraps becomes two lines, and the recipe reader (backend smart_import's
 * text heuristic) would make it two steps. Join a line onto the one before
 * when that one doesn't end a sentence and this one carries on in lowercase.
 * Headings ("Ingredients", "Method"), numbered steps and ingredient lines
 * (which start with a quantity) always start a new line. The result goes into
 * the paste box, so people can still fix it before it's read.
 */
const HEADING = /^#*\s*(ingredients?|instructions|directions|method|steps|preparation|serves|servings|makes|yield)\b/i
const INGREDIENTS = /^#*\s*ingredients?\b/i
const STEPS = /^#*\s*(instructions|directions|method|steps|preparation)\b/i
const STARTS_ITEM = /^(?:[-*•·]|\d+[.)]|\d|[½¼¾⅓⅔⅛]|step\s*\d)/i

function tidy(line: string): string {
  return line
    .replace(/^[|¦]\s*(?=ngredients?\b|nstructions\b)/i, 'I')  // "|ngredients" → "Ingredients"
    .replace(/\s+/g, ' ')
    .trim()
}

function isDebris(line: string): boolean {
  const letters = (line.match(/\p{L}/gu) ?? []).length
  return letters < 2 && !/\d/.test(line)
}

export function recipeTextFromOcr(text: string): string {
  const out: string[] = []
  let canContinue = false
  let inIngredients = false
  for (const raw of text.split(/\r?\n/)) {
    const line = tidy(raw)
    if (!line) { canContinue = false; continue }  // a blank line ends a paragraph
    if (isDebris(line)) continue
    if (INGREDIENTS.test(line)) inIngredients = true
    else if (STEPS.test(line)) inIngredients = false
    const continues = !inIngredients && canContinue && /^\p{Ll}/u.test(line) && !HEADING.test(line) && !STARTS_ITEM.test(line)
    if (continues) out[out.length - 1] += ` ${line}`
    else out.push(line)
    const last = out[out.length - 1]
    canContinue = !HEADING.test(last) && !/[.!?:]$/.test(last)
  }
  return out.join('\n')
}
