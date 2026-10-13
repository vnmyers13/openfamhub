import { describe, expect, it } from 'vitest'
import { uploadFraction } from './media'

describe('uploadFraction', () => {
  it("uses axios' progress, else loaded/total, else unknown", () => {
    expect(uploadFraction({ loaded: 5, total: 10, progress: 0.5 })).toBe(0.5)
    expect(uploadFraction({ loaded: 25, total: 100 })).toBe(0.25)
    expect(uploadFraction({ loaded: 25 })).toBeNull()
    expect(uploadFraction({ loaded: 25, total: 0 })).toBeNull()
  })
  it('stays between 0 and 1', () => {
    expect(uploadFraction({ loaded: 120, total: 100 })).toBe(1)
    expect(uploadFraction({ loaded: 0, progress: 1.2 })).toBe(1)
  })
})
