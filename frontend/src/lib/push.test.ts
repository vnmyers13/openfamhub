import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mockApi } from '../test/api'
import { pushState, turnOffPush, turnOnPush } from './push'

let subscription: { endpoint: string; toJSON: () => object; unsubscribe: ReturnType<typeof vi.fn> } | null
const subscribe = vi.fn()

function browser({ permission = 'default', grant = 'granted', ua = 'Mozilla/5.0 (X11; Linux)', standalone = false,
  push = true }: { permission?: string; grant?: string; ua?: string; standalone?: boolean; push?: boolean } = {}) {
  const registration = {
    pushManager: { getSubscription: vi.fn(async () => subscription), subscribe },
  }
  vi.stubGlobal('Notification', { permission, requestPermission: vi.fn(async () => grant) })
  if (push) vi.stubGlobal('PushManager', function PushManager() {})
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true,
    value: { ready: Promise.resolve(registration), getRegistration: vi.fn(async () => registration) } })
  Object.defineProperty(navigator, 'userAgent', { configurable: true, value: ua })
  vi.stubGlobal('matchMedia', (q: string) => ({ matches: standalone && q.includes('standalone') }))
}

describe('lib/push', () => {
  beforeEach(() => {
    subscription = null
    subscribe.mockImplementation(async () => {
      subscription = { endpoint: 'https://push.example.test/1', toJSON: () => ({ endpoint: 'https://push.example.test/1', keys: { p256dh: 'p', auth: 'a' } }), unsubscribe: vi.fn(async () => true) }
      return subscription
    })
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    delete (navigator as { serviceWorker?: unknown }).serviceWorker
  })

  it('knows when this device is on, off, blocked, unsupported or an iPhone that must add the app first', async () => {
    browser()
    expect(await pushState()).toBe('off')
    browser({ permission: 'denied' })
    expect(await pushState()).toBe('blocked')
    browser({ push: false, ua: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)' })
    vi.stubGlobal('PushManager', undefined)
    expect(await pushState()).toBe('install-first')
    browser({ push: false })
    vi.stubGlobal('PushManager', undefined)
    expect(await pushState()).toBe('unsupported')
  })

  it('turns on: asks permission, subscribes with the server key and registers the device', async () => {
    browser()
    const calls = mockApi({ 'GET /push/key': { public_key: 'BAAA' }, 'POST /push/subscriptions': { ok: true } })
    await turnOnPush()
    expect(subscribe).toHaveBeenCalledWith(expect.objectContaining({ userVisibleOnly: true }))
    expect(calls.find((c) => c.method === 'POST')?.body).toEqual({ endpoint: 'https://push.example.test/1', keys: { p256dh: 'p', auth: 'a' } })
    expect(await pushState()).toBe('on')
  })

  it("explains when permission isn't given", async () => {
    browser({ grant: 'denied' })
    mockApi({})
    await expect(turnOnPush()).rejects.toThrow(/allow notifications/i)
    expect(subscribe).not.toHaveBeenCalled()
  })

  it('turns off: removes the device from the server and the browser', async () => {
    browser()
    const calls = mockApi({ 'GET /push/key': { public_key: 'BAAA' }, 'POST /push/subscriptions': { ok: true }, 'DELETE /push/subscriptions': { ok: true } })
    await turnOnPush()
    const sub = subscription!
    await turnOffPush()
    expect(calls.some((c) => c.method === 'DELETE')).toBe(true)
    expect(sub.unsubscribe).toHaveBeenCalled()
  })
})
