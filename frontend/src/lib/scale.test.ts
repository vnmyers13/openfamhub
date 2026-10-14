import { describe, expect, it } from 'vitest'
import { formatQuantity, parseQuantity, scaleLine } from './scale'

describe('recipe scaling', () => {
  it('reads kitchen quantities', () => {
    expect(parseQuantity('2')).toBe(2)
    expect(parseQuantity('1.5')).toBe(1.5)
    expect(parseQuantity('3/4')).toBe(0.75)
    expect(parseQuantity('1 1/2')).toBe(1.5)
    expect(parseQuantity('1½')).toBe(1.5)
    expect(parseQuantity('⅓')).toBeCloseTo(1 / 3)
    expect(parseQuantity('1/0')).toBeNull()
    expect(parseQuantity('a')).toBeNull()
  })

  it('writes them back as kitchen fractions', () => {
    expect(formatQuantity(1.5)).toBe('1 1/2')
    expect(formatQuantity(0.25)).toBe('1/4')
    expect(formatQuantity(2 / 3)).toBe('2/3')
    expect(formatQuantity(3)).toBe('3')
    expect(formatQuantity(0.99)).toBe('1')
    expect(formatQuantity(2.4)).toBe('2.4')
    expect(formatQuantity(0)).toBe('0')
  })

  it('scales the number at the start of a line and nothing else', () => {
    expect(scaleLine('1 1/2 cups flour', 2)).toBe('3 cups flour')
    expect(scaleLine('3/4 cup milk', 2)).toBe('1 1/2 cup milk')
    expect(scaleLine('½ tsp salt', 2)).toBe('1 tsp salt')
    expect(scaleLine('2-3 cloves garlic', 2)).toBe('4-6 cloves garlic')
    expect(scaleLine('4 eggs', 0.5)).toBe('2 eggs')
    expect(scaleLine('1 can (14 oz) tomatoes', 3)).toBe('3 can (14 oz) tomatoes')
    expect(scaleLine('Salt and pepper', 2)).toBe('Salt and pepper')
    expect(scaleLine('4 eggs', 1)).toBe('4 eggs')
  })
})
