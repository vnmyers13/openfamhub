# OpenFamHub — TODO

Known bugs and planned fixes, from the code review of 2026-10-04. Phase 1 shipped in v0.18.

## Phase 2 — Security
- [ ] Enforce roles on events. Viewers are read-only. Members edit their own and internal events. Admins can edit everything. Synced iCal events are read-only. Scope `PATCH /calendar/events` by family.
- [ ] Rate-limit password login. Block deleted users at login. Make display names unique (case-insensitive) with a clear error.
- [ ] Remove `POST /users/switch`. It mints a token for any user ID and nothing uses it.
- [ ] Server-side session revocation using the `sessions` table and a `jti` claim, so logout, password changes and user deletion revoke tokens.
- [ ] Optional: authenticate the `/api/ws/wall` WebSocket.
- [ ] Fix the remaining react-hooks lint error in `ManageUsers.tsx`.

## Phase 3 — iCal correctness
- [ ] Don't duplicate the first occurrence of recurring events.
- [ ] Honor EXDATE and RECURRENCE-ID (cancelled or moved instances).
- [ ] Keep `all_day` on expanded recurrences.
- [ ] Store a window only (about 90 days back to 365 days ahead) instead of full history.
- [ ] Look up existing UIDs in one batch query per sync.

## Phase 4 — Infra and cleanup
- [ ] Run Alembic migrations on container start instead of `create_all`.
- [ ] CI: set `SECRET_KEY` for tests; add a frontend lint + build job; move to Forgejo Actions once a runner exists.
- [ ] Fix the Workbox `runtimeCaching` URL patterns (they're matched against the full URL, so they never match).
- [ ] `setup-wall-pi.sh`: make it idempotent and Bookworm-compatible (`chromium`, labwc/Wayland autostart).
- [ ] Remove dead code and placeholders: `notifications.py`, the `/lists` nav link, the `co_admin` role checks, and `/admin/settings` rendering the Dashboard.
- [ ] Deduplicate the event response builders and the user validators.
- [ ] Read `WALL_IDLE_TIMEOUT_SECONDS` and `FAMILY_NAME` from settings, or drop them.
- [ ] Add tests for users and permissions.
- [ ] Update `release_checklist.json` and the sprint manifests, or archive them.

## Phases 5–10 — Port the v0.29 feature set

`origin/main` carries a `v0.29` tag on a **divergent history** — no merge base with `master`. It is a
parallel product line (chores/rewards/meals), not 11 releases ahead of us. We port its features onto
*our* architecture, one domain at a time, and inherit our auth, `family_id` tenant scoping,
`UTCDateTime`, deploy tooling and CI rather than its code.

Each phase writes its tests **before** the code, in the same change. Baseline: 17 backend tests in 2
files; `v0.29` has 65 in 13. No frontend test runner exists yet — the first phase that needs one adds it.

Ordering is by dependency: rewards spends the points ledger chores introduce, and books awards points.

### Phase 5 — Chores
- [ ] `chore_templates` and `chore_instances` models + Alembic migration `005`. `UTCDateTime` throughout, `family_id` on both.
- [ ] Recurrence expansion into instances (reuse the Phase 3 iCal recurrence work where it fits).
- [ ] Claim / complete lifecycle, quick-add, completion audit log.
- [ ] Admin "By User" view: group by assignee with pending and completed counts.
- [ ] Per-user completion stats.
- [ ] `jobs/chore_generator.py` on the existing scheduler (06:00), not a second scheduler.
- Tests first: recurrence expansion across DST; instance generation idempotency; claim/complete role gating; admin view counts; generator does not double-generate.

### Phase 6 — Rewards
- [ ] Points ledger as an append-only table (no balances stored on the user).
- [ ] Weekly allowance distributor, Mondays 07:00, **idempotent per week**.
- [ ] Reward catalog with both purchase and request → approve / reject flows.
- [ ] Streaks and badge definitions with auto-award.
- Tests first: ledger balances match the sum of entries; allowance re-run for the same week is a no-op; approve/reject adjusts the ledger exactly once; streak rollover at week boundaries.

### Phase 7 — Meals and recipes
- [ ] `recipes` with dietary tags, plus text and JSON-LD import.
- [ ] 7-day meal-plan grid with bulk update.
- [ ] Shopping list tracking which recipe each item came from, regenerate, weekly reset job.
- Tests first: import parsing for both formats; plan overwrite semantics; regenerate is idempotent; reset does not delete completed purchases.

### Phase 8 — Books, announcements, weather
- [ ] Books: personal lists, shared family library, status transitions, 50-point award on completion (writes to the Phase 6 ledger).
- [ ] Announcements: free text with pin/unpin.
- [ ] Weather: Open-Meteo, no API key, cached ~10 minutes server-side. WMO code → emoji mapping.
- Tests first: cross-family isolation on the shared library; point award fires once; cache hit within the window; WMO mapping table has no unmapped codes.

### Phase 9 — Offline sync
- [ ] Add the frontend test runner and its first tests.
- [ ] IndexedDB write queue in `frontend/src/lib/idb.ts`.
- [ ] Sync orchestrator replaying the queue on reconnect and on tab visibility.
- [ ] Conflict resolution modal: 409 detection, keep-local / keep-server / merge.
- [ ] Offline banner and sync indicator.
- Tests first: queue survives a reload; replay is all-or-nothing per operation; a 409 surfaces the conflict modal rather than silently overwriting; a failed replay leaves the item queued.
- Note: the v0.29 version of this is broken — its `useOfflineMutations` hook is never called and its replay `fetch` sends no credentials, so every replay 401s. Design against the tests above, not against that code.

### Phase 10 — OCR and wall panels
- [ ] `ScanListModal` with `tesseract.js`: capture, OCR, preview, edit, then add to the shopping list.
- [ ] Wall cycling panel mode with a live countdown.
- [ ] `DateTimeWallPanel` with a timezone picker; reuse `frontend/src/lib/dates.ts` and the wall token flow.
- Tests first: OCR line parsing and classification against sample images; cycling-mode panel order and auto-advance; the wall panel renders only for a paired device.

### Do not port from v0.29
Each of these is in that tree. Porting a feature means reimplementing it correctly, not copying the file.

- [ ] `POST /auth/reset-setup` (`v0.29 backend/app/routers/auth.py:64`) deactivates every account with **no auth check**, and `/setup` only counts *active* users — two unauthenticated requests are a full takeover. Do not add this endpoint in any form.
- [ ] `SECRET_KEY: str = "change-me-in-production"` (`v0.29 backend/app/core/config.py:11`) is a committed fallback. Ours has no default on purpose (`backend/app/core/config.py:17`).
- [ ] Timestamps stored as `Text` throughout `v0.29 backend/app/models/event.py`. ISO strings sort lexicographically, so mixed offsets order wrongly. Use `UTCDateTime`.
- [ ] `Event.start_time >= start AND Event.end_time <= end` (`v0.29 backend/app/routers/events.py:23`) is containment, so a partially-overlapping event is dropped. Use the overlap form in `backend/app/services/calendar.py:48`.
- [ ] 365-day tokens (`v0.29 backend/app/core/security.py:32`) that never re-check the database, with `role` baked in at issue time.
- [ ] `allow_origins=["*"]` together with `allow_credentials=True` (`v0.29 backend/app/main.py:18`).
- [ ] PIN login that iterates every active user and checks the rate limit *after* a match (`v0.29 backend/app/routers/auth.py:91`).
- [ ] `announcements.py` list endpoint with no auth dependency.
- [ ] `ChoreInstance.completed_at != None` with no date guard (`v0.29 backend/app/routers/chores.py:284`) — "today's chores" returns everything ever completed.
- [ ] Its committed SQLite WAL (`backend/file:memdb1-wal`, 4.1 MB) contains a bcrypt hash. `.gitignore` already covers `*.db`, `*.db-wal` and `*.db-shm`, but SQLite shared-cache names (`file:memdb1-wal`) slip past them — add a pattern before Phase 5 opens a dev DB.

### Version numbering
Both lineages independently shipped a `0.18` (ours: deploy/wall-pairing/UTC; v0.29's: chores/rewards/meals).
`CHANGELOG.md` entries therefore collide on headings. Decide which tree keeps `0.18` before Phase 5 ships, and
record the decision in `CHANGELOG.md` so the next bump is unambiguous.

## Completed
- [x] v0.18: the Phase 1 fixes (routing, login errors, time zones, range queries, Sync Now, source delete, source filter, wall pairing, deploy script). See CHANGELOG.
