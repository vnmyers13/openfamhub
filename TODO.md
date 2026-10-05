# OpenFamHub — TODO

Known bugs and planned fixes, from the code review of 2026-10-04. Phase 1 shipped in v0.18.

## Decisions (2026-10-04)
- **Direction:** port v0.29's features onto this codebase (0.18 base). `origin/main` is reference only.
- **Data:** start fresh. No importer from a v0.29 database.
- **Sign-in:** an avatar picker + PIN for everyone; a password is required for admin actions.
- **Versioning:** the merged line continues at **0.30**, above every existing tag. CHANGELOG notes that 0.19–0.29 belong to the retired `main` line.
- **Order:** keep the phase order below.

## Release plan
| Release | Contents |
|---|---|
| 0.30 | Phases 2 + 4 (security, sign-in model, infra/CI) |
| 0.31 | Phase 3 (iCal) + Phase 5 (chores) |
| 0.32 | Phase 6 (rewards) |
| 0.33 | Phase 7 (meals) |
| 0.34 | Phase 8 (books, announcements, weather) + dashboard summary |
| 0.35 | Phase 9 (offline sync) |
| 0.36 | Phase 10 (OCR, wall panels) |

Each release is published with `deploy.sh publish` and checked on the `test` VM before the next phase starts.

## How to port each domain
- **Backend:** rewrite on our models (`family_id`, `UTCDateTime`, Alembic, cookie auth). v0.29's backend is a spec, not code to copy.
- **Frontend:** v0.29's pages (Chores, Meals, Rewards, Books, Announcements, wall panels; about 3k lines) are reusable UI. Port them with an API adapter: axios `withCredentials`, our routes, 401 → login and 403 → message (v0.29 logs users out on 403), and `lib/dates.ts` for dates.
- **Tests:** v0.29's 65 backend tests are acceptance criteria. Re-express each one against our fixtures before writing the code it covers.

## Phase 2 — Security ✅ (0.30)
- [x] Enforce roles on events. Viewers are read-only. Members change their own events. Admins change any family event. Synced iCal events are read-only. `PATCH /calendar/events` is scoped by family.
- [x] Rate-limit password login. Block deleted users at login. Make display names unique (case-insensitive) with a clear error.
- [x] Remove `POST /users/switch`. It mints a token for any user ID and nothing uses it.
- [x] Server-side session revocation using the `sessions` table and a `jti` claim, so logout, password changes and user deletion revoke tokens.
- [x] Authenticate the wall WebSocket (now `/api/wall/ws`, paired displays only).
- [x] Fix the remaining react-hooks lint error in `ManageUsers.tsx`.
- [x] **Sign-in model (decision above).**
  - `GET /api/auth/profiles` returns name, avatar and color for the picker. It stays public, because the picker needs it before sign-in, but it returns no other fields.
  - PIN login takes `user_id` + `pin` (never loop over users) and counts **failed** attempts per user with an escalating lockout.
  - Sessions record the method (`amr: pin|password`). Admin endpoints require a password session, or a password re-check within the last 15 minutes.
  - Users get an emoji avatar (reuse `avatar_type="emoji"`, `avatar_value`).
  - Tests first: lockout after N failures; a PIN session gets 403 on an admin endpoint; a password session passes; profiles exposes no other fields.

## Phase 3 — iCal correctness
- [ ] Don't duplicate the first occurrence of recurring events.
- [ ] Honor EXDATE and RECURRENCE-ID (cancelled or moved instances).
- [ ] Keep `all_day` on expanded recurrences.
- [ ] Store a window only (about 90 days back to 365 days ahead) instead of full history.
- [ ] Look up existing UIDs in one batch query per sync.

## Phase 4 — Infra and cleanup ✅ (0.30)
- [x] Run Alembic migrations on container start instead of `create_all`.
- [x] CI: set `SECRET_KEY` for tests; add a frontend lint + build job.
- [ ] Move CI to Forgejo Actions once a runner exists (still GitHub Actions only).
- [x] Fix the Workbox `runtimeCaching` URL patterns (they're matched against the full URL, so they never match).
- [x] `setup-wall-pi.sh`: make it idempotent and Bookworm-compatible (`chromium`, labwc/Wayland autostart).
- [x] Remove dead code and placeholders: `notifications.py`, the `/lists` nav link, the `co_admin` role checks, and `/admin/settings` rendering the Dashboard.
- [x] Deduplicate the event response builders and the user validators.
- [x] `WALL_IDLE_TIMEOUT_SECONDS` drives the wall idle screen. `FAMILY_NAME` stays accepted (an unknown key would break existing `.env` files) but is unused: the name comes from the setup wizard.
- [x] Add tests for users and permissions (`tests/test_phase2.py`).
- [x] Archive `release_checklist.json` and the sprint manifests (`docs/archive/planning/`).
- [x] `.gitignore`: add `file:*` (SQLite shared-cache files) now, before any Phase 5 dev DB.
- [x] Bump to 0.30 and add the CHANGELOG note about the retired 0.19–0.29 line.

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
- [ ] **Fix v0.29 bugs while porting:**
  - Completing a chore never writes to the points ledger (only `points_earned` on the log), so chores earn no points. Credit the ledger in the same transaction, exactly once.
  - `every_N_days` restarts from "today" on each run, so with a daily run every day gets an instance. Anchor the interval to the template's start date.
  - Due dates use the UTC date. Use the family's timezone date.
  - Anyone can claim an *assigned* chore. Only the assignee (or an admin) can.
  - Add a unique (`template_id`, `due_date`) constraint so double generation is impossible.
- Tests first: recurrence expansion across DST; instance generation idempotency; claim/complete role gating; admin view counts; generator does not double-generate.

### Phase 6 — Rewards
- [ ] Points ledger as an append-only table (no balances stored on the user).
- [ ] Weekly allowance distributor, Mondays 07:00, **idempotent per week**.
- [ ] Reward catalog with both purchase and request → approve / reject flows.
- [ ] Streaks and badge definitions with auto-award.
- [ ] Allowance is stored as integer cents (v0.29 uses strings), with a unique (`user_id`, `week_start`) key. A missed Monday is caught up on the next run.
- Tests first: ledger balances match the sum of entries; allowance re-run for the same week is a no-op; approve/reject adjusts the ledger exactly once; streak rollover at week boundaries.

### Phase 7 — Meals and recipes
- [ ] `recipes` with dietary tags, plus text and JSON-LD import.
- [ ] 7-day meal-plan grid with bulk update.
- [ ] Shopping list tracking which recipe each item came from, regenerate, weekly reset job.
- [ ] Every meals endpoint requires auth and family scope. v0.29's GETs for dietary tags, recipes, plans and the shopping list have **no auth**, and its weekly reset job is never registered.
- [ ] Recipe URL import guards against SSRF: http(s) only; block private, loopback and link-local addresses after DNS resolution; size and time limits.
- Tests first: import parsing for both formats; plan overwrite semantics; regenerate is idempotent; reset does not delete completed purchases.

### Phase 8 — Books, announcements, weather
- [ ] Books: personal lists, shared family library, status transitions, 50-point award on completion (writes to the Phase 6 ledger).
- [ ] Announcements: free text with pin/unpin.
- [ ] Weather: Open-Meteo, no API key, cached ~10 minutes server-side. WMO code → emoji mapping. Location is a family setting.
- [ ] Shared family library: implement `POST/PATCH/DELETE /books/shared…`. v0.29's UI calls these, but its backend only has `GET /books/shared`.
- [ ] Dashboard: one `GET /api/dashboard/summary` (today's events, chore stats, points, allowance, this week's meals). v0.29's dashboard calls four `/api/dashboard/*` routes that don't exist.
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
- [ ] Read-only wall endpoints (`/api/wall/chores`, `/meals`, `/announcements`, `/weather`) behind the paired-device cookie. v0.29's panels need a family member's login.
- [ ] The wall timezone is a family setting edited by an admin. v0.29 lets the wall itself write it via an admin-only call.
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
Decided: the merged line continues at **0.30** (see Decisions). Our 0.18 keeps its CHANGELOG entry. The 0.30 entry
notes that 0.19–0.29 (and v0.29's own "0.18") belong to the retired `main` line.

## Completed
- [x] v0.30: Phases 2 and 4 (sign-in picker + PIN with admin password gate, server-side sessions, lockout, event permissions, migrations at startup, CI, cleanup). See CHANGELOG.
- [x] v0.18: the Phase 1 fixes (routing, login errors, time zones, range queries, Sync Now, source delete, source filter, wall pairing, deploy script). See CHANGELOG.
