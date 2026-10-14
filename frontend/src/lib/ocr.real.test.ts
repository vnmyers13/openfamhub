// @vitest-environment node
/// <reference types="node" />
/**
 * The real OCR engine against sample photos (src/test/fixtures/ocr-*.png:
 * tilted, blurred and speckled like a phone picture), through the same
 * readText + parseListLines the app uses. Slower than the rest (a few
 * seconds), so it lives in its own file.
 */
import { mkdtempSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { readText } from './ocr'
import { parseListLines } from './ocrLines'
import { recipeTextFromOcr } from './ocrRecipe'

const here = dirname(fileURLToPath(import.meta.url))
const fixture = (name: string) => join(here, '..', 'test', 'fixtures', name)
const NODE_PATHS = {
  langPath: join(here, '..', '..', 'node_modules', '@tesseract.js-data', 'eng', '4.0.0_best_int'),
  cachePath: mkdtempSync(join(tmpdir(), 'ocr-')),
}

const picked = async (name: string) => {
  const lines = parseListLines(await readText(fixture(name), undefined, NODE_PATHS))
  return { lines, items: lines.filter((l) => l.include).map((l) => [l.name, l.quantity]) }
}

describe('OCR on sample photos', () => {
  it('reads a bulleted list with quantities and skips the title', async () => {
    const { lines, items } = await picked('ocr-list.png')
    expect(items).toEqual([
      ['Apples', '2 lb'], ['Milk', null], ['Bread', null], ['Yogurt', '3'], ['Eggs', '12'], ['Peanut butter', null],
    ])
    expect(lines.find((l) => /shopping list/i.test(l.text))?.kind).toBe('heading')
  }, 60_000)

  it('reads a list in sections and leaves the section names out', async () => {
    const { lines, items } = await picked('ocr-sections.png')
    expect(items).toEqual([['Bananas', '6'], ['Lettuce', null], ['Milk', '1 gal'], ['Cheddar cheese', null]])
    expect(lines.filter((l) => l.kind === 'heading').map((l) => l.name)).toEqual(['PRODUCE', 'DAIRY'])
  }, 60_000)

  it('reads a recipe photo into text the recipe reader understands, with wrapped steps joined', async () => {
    const text = recipeTextFromOcr(await readText(fixture('ocr-recipe.png'), undefined, NODE_PATHS))
    expect(text.split('\n')).toEqual([
      'Banana Bread', 'Serves 8', 'Ingredients', '3 ripe bananas', '1/3 cup melted butter', '1 cup sugar', 'Method',
      '1. Heat the oven to 350F and butter a loaf pan.', '2. Mash the bananas, then stir in the butter and sugar.',
      '3. Bake for 60 minutes.',
    ])
  }, 60_000)
})
