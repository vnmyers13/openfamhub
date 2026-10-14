// @vitest-environment node
/// <reference types="node" />
/**
 * public/push-sw.js runs inside the service worker (imported by the one
 * vite-plugin-pwa generates). Load the real file into a fake worker scope.
 */
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it, vi } from 'vitest'

const source = readFileSync(join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'public', 'push-sw.js'), 'utf8')

function worker(windows: { url: string }[] = []) {
  const listeners: Record<string, (e: unknown) => void> = {}
  const clients = windows.map((w) => ({ ...w, focus: vi.fn(async () => {}), navigate: vi.fn(async () => {}) }))
  const self = {
    location: { origin: 'https://family.test' },
    addEventListener: (type: string, fn: (e: unknown) => void) => { listeners[type] = fn },
    registration: { showNotification: vi.fn(async () => {}) },
    clients: { matchAll: vi.fn(async () => clients), openWindow: vi.fn(async () => {}) },
  }
  new Function('self', source)(self)
  const fire = async (type: string, event: object) => {
    let done: Promise<unknown> = Promise.resolve()
    listeners[type]({ ...event, waitUntil: (p: Promise<unknown>) => { done = p } })
    await done
  }
  return { self, clients, fire }
}

describe('push-sw.js', () => {
  it('shows the notification the server sent', async () => {
    const { self, fire } = worker()
    await fire('push', { data: { json: () => ({ title: 'Dentist', body: 'Starts at 15:30', url: '/calendar', tag: 'event:1' }) } })
    expect(self.registration.showNotification).toHaveBeenCalledWith('Dentist', expect.objectContaining({
      body: 'Starts at 15:30', tag: 'event:1', data: { url: '/calendar' } }))
  })

  it('still shows something for an odd payload', async () => {
    const { self, fire } = worker()
    await fire('push', { data: { json: () => { throw new Error('not json') }, text: () => 'hello' } })
    expect(self.registration.showNotification).toHaveBeenCalledWith('OpenFamHub', expect.objectContaining({ body: 'hello' }))
  })

  it('a tap opens the app at that page, reusing an open window', async () => {
    const { self, clients, fire } = worker([{ url: 'https://family.test/' }])
    const close = vi.fn()
    await fire('notificationclick', { notification: { close, data: { url: '/rewards' } } })
    expect(close).toHaveBeenCalled()
    expect(clients[0].focus).toHaveBeenCalled()
    expect(clients[0].navigate).toHaveBeenCalledWith('https://family.test/rewards')
    expect(self.clients.openWindow).not.toHaveBeenCalled()
  })

  it('opens a new window when none is open, and never leaves the app', async () => {
    const { self, fire } = worker()
    await fire('notificationclick', { notification: { close: vi.fn(), data: { url: 'https://evil.test/x' } } })
    expect(self.clients.openWindow).toHaveBeenCalledWith('https://family.test/')
  })
})
