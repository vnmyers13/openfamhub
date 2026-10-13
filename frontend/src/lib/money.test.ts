import { describe, expect, it } from 'vitest'
import { formatCents, parseDollars } from './money'

describe('formatCents', () => {
  it('formats whole cents as dollars', () => {
    expect(formatCents(375)).toBe('$3.75')
    expect(formatCents(5)).toBe('$0.05')
    expect(formatCents(0)).toBe('$0.00')
    expect(formatCents(123456)).toBe('$1,234.56')
  })
  it('puts the sign in front', () => {
    expect(formatCents(-500)).toBe('-$5.00')
  })
})

describe('parseDollars', () => {
  it('reads dollar amounts as cents', () => {
    expect(parseDollars('3.75')).toBe(375)
    expect(parseDollars('$3')).toBe(300)
    expect(parseDollars('3.5')).toBe(350)
    expect(parseDollars(' 0.05 ')).toBe(5)
  })
  it('refuses anything else', () => {
    for (const bad of ['', 'abc', '-1', '3.999', '1e3']) expect(parseDollars(bad)).toBeNull()
  })
})
