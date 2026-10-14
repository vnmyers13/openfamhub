import { describe, expect, it } from 'vitest'
import { runtimeCaching } from './swCaching'

type Rule = (typeof runtimeCaching)[number]
const rules = () => runtimeCaching

describe('service worker caching rules', () => {
  it('each match function works on its own, as it will inside sw.js', () => {
    const list = rules()
    expect(list.length).toBeGreaterThan(0)
    for (const rule of list) {
      // Workbox copies the function as text: any outside variable it uses is undefined there.
      const isolated = new Function(`return (${rule.urlPattern.toString()})`)() as Rule['urlPattern']
      expect(() => isolated({ url: new URL('https://x.test/api/todos') })).not.toThrow()
    }
  })

  it("keeps the lists you can change offline, and doesn't cache other pages' data", () => {
    const offline = rules().find((r) => r.options?.cacheName === 'offline-api')!
    for (const path of ['/api/auth/me', '/api/todos', '/api/meals/shopping', '/api/meals/plan', '/api/meals/recipes', '/api/chores/instances', '/api/dashboard/summary']) {
      expect(offline.urlPattern({ url: new URL(`https://x.test${path}`) })).toBe(true)
    }
    for (const path of ['/api/media/abc/wall', '/api/rewards/allowance', '/api/wall/session']) {
      expect(offline.urlPattern({ url: new URL(`https://x.test${path}`) })).toBe(false)
    }
  })

  it('keeps the OCR engine after the first scan, and nothing else under that rule', () => {
    const ocr = rules().find((r) => r.options?.cacheName === 'ocr')!
    expect(ocr.handler).toBe('CacheFirst')
    expect(ocr.urlPattern({ url: new URL('https://x.test/ocr/eng.traineddata.gz') })).toBe(true)
    expect(ocr.urlPattern({ url: new URL('https://x.test/api/ocr') })).toBe(false)
  })
})
