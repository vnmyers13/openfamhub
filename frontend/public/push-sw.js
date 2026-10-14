/*
 * Web Push in the service worker (Phase 11). vite.config.ts imports this file
 * into the worker vite-plugin-pwa generates (workbox importScripts). Tested by
 * src/lib/pushSw.test.ts, which loads this file into a fake worker.
 */
self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch (e) {
    data = { body: event.data ? event.data.text() : '' }
  }
  event.waitUntil(self.registration.showNotification(data.title || 'OpenFamHub', {
    body: data.body || '',
    tag: data.tag,
    data: { url: data.url || '/' },
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
  }))
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const origin = self.location.origin
  let url = origin + '/'
  try {
    const target = new URL((event.notification.data && event.notification.data.url) || '/', origin)
    if (target.origin === origin) url = target.href  // only ever open the app itself
  } catch (e) { /* keep the home page */ }
  event.waitUntil((async () => {
    const windows = await self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    for (const w of windows) {
      if (new URL(w.url).origin === origin && 'focus' in w) {
        await w.focus()
        if ('navigate' in w) await w.navigate(url)
        return
      }
    }
    if (self.clients.openWindow) await self.clients.openWindow(url)
  })())
})
