/**
 * Notifications on this device (Phase 11): Web Push through the app's service
 * worker (public/push-sw.js). The server keeps one subscription per device
 * and sends reminders to it (backend jobs/reminders.py).
 *
 * iPhone and iPad only offer Web Push to the app once it's on the Home Screen
 * (iOS 16.4+), so a Safari tab reports "install-first".
 */
import { apiClient } from '../api/client'

export type PushState = 'unsupported' | 'install-first' | 'blocked' | 'off' | 'on'

const isApple = () => /iPhone|iPad|iPod/.test(navigator.userAgent)
const isStandalone = () =>
  (typeof matchMedia === 'function' && matchMedia('(display-mode: standalone)').matches) ||
  (navigator as { standalone?: boolean }).standalone === true

function supported(): boolean {
  return 'serviceWorker' in navigator && typeof PushManager !== 'undefined' && typeof Notification !== 'undefined'
}

async function registration(): Promise<ServiceWorkerRegistration | undefined> {
  return navigator.serviceWorker.getRegistration()
}

export async function pushState(): Promise<PushState> {
  if (!supported()) return isApple() && !isStandalone() ? 'install-first' : 'unsupported'
  if (Notification.permission === 'denied') return 'blocked'
  const reg = await registration()
  if (!reg) return 'unsupported'  // no service worker (development server)
  return (await reg.pushManager.getSubscription()) ? 'on' : 'off'
}

/** The server's VAPID key (base64url) as the bytes PushManager wants. */
function keyBytes(base64url: string): Uint8Array {
  const b64 = base64url.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - (base64url.length % 4)) % 4)
  return Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))
}

export async function turnOnPush(): Promise<void> {
  if (await Notification.requestPermission() !== 'granted') {
    throw new Error('Allow notifications for OpenFamHub in this browser (or phone) settings, then try again.')
  }
  const { public_key } = (await apiClient.get('/push/key')).data as { public_key: string }
  const reg = await navigator.serviceWorker.ready
  const sub = (await reg.pushManager.getSubscription())
    ?? await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) as BufferSource })
  await apiClient.post('/push/subscriptions', sub.toJSON())
}

export async function turnOffPush(): Promise<void> {
  const reg = await registration()
  const sub = reg ? await reg.pushManager.getSubscription() : null
  if (!sub) return
  await apiClient.delete('/push/subscriptions', { data: { endpoint: sub.endpoint } })
  await sub.unsubscribe()
}

export async function sendTestPush(): Promise<number> {
  return ((await apiClient.post('/push/test')).data as { sent: number }).sent
}
