import { describe, expect, it } from 'vitest'
import { parseListLines, type ListLine } from './ocrLines'

const items = (lines: ListLine[]) => lines.filter((l) => l.kind === 'item').map((l) => [l.name, l.quantity])

describe('parseListLines', () => {
  it('strips bullets, checkboxes and numbering', () => {
    const text = '- Milk\n* bread\n• Eggs\n☐ butter\n[ ] Jam\n[x] Tea\n1. Rice\n2) Beans\no Apples'
    expect(items(parseListLines(text))).toEqual([
      ['Milk', null], ['Bread', null], ['Eggs', null], ['Butter', null], ['Jam', null], ['Tea', null],
      ['Rice', null], ['Beans', null], ['Apples', null],
    ])
  })

  it('reads a quantity in front or behind', () => {
    const text = '2 lb apples\n1 gal milk\n3x yogurt\nEggs x 12\nbananas (6)\n½ dozen bagels\n2 cans tomatoes\n1.5 kg flour'
    expect(items(parseListLines(text))).toEqual([
      ['Apples', '2 lb'], ['Milk', '1 gal'], ['Yogurt', '3'], ['Eggs', '12'], ['Bananas', '6'],
      ['Bagels', '½ dozen'], ['Tomatoes', '2 cans'], ['Flour', '1.5 kg'],
    ])
  })

  it('fixes the usual OCR misreads of lb', () => {
    expect(items(parseListLines('- 2 |b apples\n3 Ibs flour'))).toEqual([['Apples', '2 lb'], ['Flour', '3 lbs']])
  })

  it('a bare number is a count, not part of the name; numbers inside names stay', () => {
    expect(items(parseListLines('2 avocados\n7up\nV8 juice'))).toEqual([['Avocados', '2'], ['7up', null], ['V8 juice', null]])
  })

  it('classifies headings and noise, and leaves them out', () => {
    const lines = parseListLines('SHOPPING LIST\nProduce:\n  lettuce\n~~ |\n.\nDAIRY\ncheese\n')
    expect(lines.map((l) => [l.text, l.kind])).toEqual([
      ['SHOPPING LIST', 'heading'], ['Produce:', 'heading'], ['lettuce', 'item'], ['~~ |', 'noise'], ['.', 'noise'],
      ['DAIRY', 'heading'], ['cheese', 'item'],
    ])
    expect(lines.filter((l) => l.include).map((l) => l.name)).toEqual(['Lettuce', 'Cheese'])
  })

  it('tidies OCR leftovers and drops repeats', () => {
    const text = 'Milk.\nmilk\nPeanut  butter ,\nToilet paper;\n| Coffee'
    const lines = parseListLines(text)
    expect(items(lines)).toEqual([['Milk', null], ['Milk', null], ['Peanut butter', null], ['Toilet paper', null], ['Coffee', null]])
    expect(lines.filter((l) => l.include).map((l) => l.name)).toEqual(['Milk', 'Peanut butter', 'Toilet paper', 'Coffee'])
    expect(lines[1]).toMatchObject({ kind: 'item', include: false, duplicate: true })
  })

  it('keeps names to the shopping list limit', () => {
    const [line] = parseListLines(`${'a'.repeat(300)}`)
    expect(line.name.length).toBeLessThanOrEqual(256)
  })
})
