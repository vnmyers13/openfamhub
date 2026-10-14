/**
 * Service-worker caching rules (vite-plugin-pwa → workbox runtimeCaching).
 * Kept here, outside vite.config.ts, so tests can check them.
 *
 * Workbox copies each urlPattern function into sw.js as text: a function may
 * use only its own arguments and literals, never a variable from this file
 * (it would be undefined in the service worker). swCaching.test.ts checks.
 */
type Rule = {
  urlPattern: (o: { url: URL }) => boolean
  handler: 'NetworkFirst' | 'CacheFirst'
  options: { cacheName: string; networkTimeoutSeconds?: number; expiration?: { maxEntries?: number; maxAgeSeconds?: number } }
}

export const runtimeCaching: Rule[] = [
  {
    urlPattern: ({ url }) => url.pathname.startsWith('/api/calendar/events'),
    handler: 'NetworkFirst',
    options: { cacheName: 'events-cache', networkTimeoutSeconds: 5 },
  },
  {
    urlPattern: ({ url }) => url.pathname.startsWith('/api/calendar/sources'),
    handler: 'NetworkFirst',
    options: { cacheName: 'sources-cache', networkTimeoutSeconds: 5 },
  },
  {
    urlPattern: ({ url }) => url.pathname.startsWith('/api/users'),
    handler: 'NetworkFirst',
    options: { cacheName: 'users-cache', networkTimeoutSeconds: 5 },
  },
  {
    // Offline (Phase 9): opening the app and the lists you can change
    // offline show their last copy. Writes queue in IndexedDB
    // (lib/offline). These caches are cleared on logout.
    // Workbox copies this function into the service worker as text, so
    // the list must live inside it (an outside constant is undefined there).
    urlPattern: ({ url }) => ['/api/auth/setup/status', '/api/auth/me', '/api/chores/instances', '/api/chores/stats',
      '/api/todos', '/api/meals/shopping', '/api/meals/plan', '/api/meals/recipes', '/api/dashboard/summary'].some((p) => url.pathname.startsWith(p)),
    handler: 'NetworkFirst',
    options: {
      cacheName: 'offline-api',
      networkTimeoutSeconds: 5,
      expiration: { maxEntries: 60, maxAgeSeconds: 7 * 24 * 3600 },
    },
  },
  {
    // The OCR engine and English data (Phase 10, lib/ocr.ts): about 7 MB, so
    // not precached at install (vite.config.ts globIgnores). Kept after the
    // first scan, so scanning works offline from then on.
    urlPattern: ({ url }) => url.pathname.startsWith('/ocr/'),
    handler: 'CacheFirst',
    options: { cacheName: 'ocr', expiration: { maxEntries: 10, maxAgeSeconds: 30 * 24 * 3600 } },
  },
]
