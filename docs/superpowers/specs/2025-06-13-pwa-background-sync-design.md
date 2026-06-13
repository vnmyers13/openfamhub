# PWA Background Sync Design

**Date:** 2026-06-13
**Version:** 0.24
**Scope:** Shopping list + chores with offline support and background sync

## Problem

The PWA runs on a local intranet. When users are away from home, they cannot access the app. When they return, any changes made offline (shopping list items, chore claims/completions) need to sync with the server. Conflicts must be detected and resolved manually.

## Architecture

### Service Worker
- Intercepts all API requests
- Fetch strategy: NetworkFirst with Cache fallback
- Cache API stores responses for offline access
- `network-online` event listener triggers sync when connection restored

### IndexedDB
- Stores pending operations when offline (add, update, delete)
- Each operation has: `id`, `type`, `entity`, `data`, `timestamp`, `serverVersion`
- Queue processes in FIFO order

### Visibility API
- `document.visibilitychange` event triggers sync check
- When app becomes visible and connection is online, sync queued operations

### Conflict Detection
- Each cached response includes a `serverVersion` (ISO timestamp of last modification)
- When syncing, compare local `serverVersion` with server current version
- If different → conflict → show merge UI

## Data Flow

### Normal Operation (Online)
1. User makes mutation (add/complete/delete)
2. API call sent to server
3. Response cached in Cache API
4. UI updated with new data

### Offline Operation
1. User makes mutation
2. Operation queued in IndexedDB with timestamp
3. UI shows "offline" banner
4. UI shows optimistic update (pessimistic about sync, optimistic about UX)

### Sync When Online
1. Visibility API detects app is visible
2. Check `navigator.onLine`
3. If online, process IndexedDB queue
4. For each operation:
   - Send to server
   - If server returns 409 Conflict:
     - Fetch current server version
     - Show merge modal
     - User chooses: keep local, keep server, or combine
   - If success: remove from queue, update cache

## UI Components

### Offline Banner
- Fixed banner at top: "You are offline. Changes will sync when connected."
- Disappears when connection restored

### Sync Status Indicator
- Small icon in header: green dot (online), yellow dot (syncing), red dot (offline)
- Shows sync progress: "Syncing 3 items..."

### Conflict Resolution Modal
- Shows "local version" and "server version" side by side
- Buttons: "Keep My Changes", "Keep Server Version", "Merge Both"
- For shopping list: keep item, remove item, update quantity
- For chores: keep claim, unclaim, keep completion

## Scope

### Synced (Write)
- Shopping list: add, check/uncheck, delete, edit item/quantity
- Chores: claim, complete, unclaim

### Read-Only (No Sync)
- Calendar events
- Announcements
- Meal plans
- Recipes
- Rewards

## Implementation Files

### Backend Changes
- None — existing APIs support all operations
- Add `etag`/`lastModified` headers to shopping list and chores responses

### Frontend Changes
- `frontend/src/sw.ts` — Service Worker with Cache API strategies
- `frontend/src/lib/offline.ts` — IndexedDB queue manager
- `frontend/src/lib/sync.ts` — Sync orchestrator
- `frontend/src/components/OfflineBanner.tsx` — Offline status banner
- `frontend/src/components/SyncStatus.tsx` — Sync indicator in header
- `frontend/src/components/ConflictModal.tsx` — Conflict resolution UI
- `frontend/src/api/client.ts` — Intercept mutations, queue when offline

## Testing

### Unit Tests
- IndexedDB queue: enqueue, dequeue, clear
- Sync: process queue, detect conflicts, resolve conflicts
- Cache: fetch with fallback, invalidate on mutation

### Integration Tests
- Offline → make changes → go online → verify sync
- Conflict → resolve → verify both versions merged correctly
- Visibility API → app visible → sync triggered

## Success Criteria

- [ ] PWA installable on iOS and Android
- [ ] Shopping list works offline (add/check/delete items)
- [ ] Chores work offline (claim/complete)
- [ ] Changes sync when connection restored
- [ ] Conflicts detected and resolved manually
- [ ] Offline banner shows when disconnected
- [ ] Sync indicator shows progress
- [ ] No data loss on conflict resolution
