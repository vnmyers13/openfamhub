# Architecture

## Components

| Container | Image | Role |
|---|---|---|
| `caddy` | `caddy:2-alpine` | Edge router. `/api/*` and `/photos/*` go to `api`; everything else goes to `web`. LAN mode terminates HTTPS with Caddy's internal CA. Proxy mode serves plain HTTP behind another proxy. |
| `api` | `openfamhub-api` | FastAPI app (single uvicorn worker) with the scheduler, WebSocket hub and SQLite database in `/data`. |
| `web` | `openfamhub-web` | The built React single-page app, served by nginx on port 3000 with an SPA fallback. |

The app runs a single API worker by design. The scheduler, the in-memory event bus, the WebSocket connection list and the PIN rate limiter all live in that one process.

## Backend layout (`backend/app`)

```
main.py            app factory: lifespan (create tables, start scheduler), CORS, routers, /api/health
core/              config (pydantic-settings from .env), database (async engine, WAL), security (JWT, roles),
                   events (in-process EventBus), types (UTCDateTime)
models/            SQLAlchemy models: Family, User, Session (unused), CalendarSource, CalendarEvent,
                   SyncLog, WallDevice
schemas/           Pydantic request/response models
routers/           auth, users, calendar, integrations (iCal add), wall (pairing + read-only data), ws
services/          calendar (range query, internal source), users, notifications (stub)
integrations/      ical_feed: fetch + parse + expand RRULEs
jobs/              scheduler, calendar_sync (every 15 min, per-source interval), backup (daily)
scripts/           one-off maintenance (fix_event_timezones.py)
```

## Data model

```
families 1─* users
families 1─* calendar_sources 1─* calendar_events
calendar_sources 1─* sync_logs
families 1─* wall_devices
```

- One family per install. `/api/auth/setup` refuses to run a second time.
- Each family gets one `internal` source ("Family Calendar"), created when its first event is created in the app. All other sources are `ical` subscriptions.
- Deletes are soft (`is_deleted`). Events from deleted or disabled sources are hidden.
- `families.timezone` comes from the setup wizard.

## Database migrations

Alembic owns the schema. On startup the API runs `alembic upgrade head` (`core/migrate.py`, in a worker thread). A database created before 0.30 has no `alembic_version` table; it's first stamped at the revision that matches its newest table, then upgraded. `create_all` still runs afterwards as a no-op safety net. Every model change needs a migration in `backend/alembic/versions/`.

## Time handling

SQLite has no timezone type. Every datetime column uses `core.types.UTCDateTime`:

- It converts values to UTC on write, stores them without an offset, and attaches UTC on read.
- The API always returns ISO strings with `+00:00`.
- Naive inputs are treated as UTC.

The frontend uses one convention, implemented in `frontend/src/lib/dates.ts`:

- **Timed events** are instants. The UI sends `Date.toISOString()` and displays the value in the viewer's local zone.
- **All-day events** are dates, stored as `00:00Z` on the start date with an **exclusive** end at `00:00Z` on the day after the last day (the iCal convention). The UI takes the date part and builds a local midnight from it, so all-day events never slip to the previous day west of UTC.
- Range queries match by **overlap** (`start < window_end AND end > window_start`), so multi-day events show on every day they cover.
- `eventDayKeys` lists every local day an event overlaps, timed or all-day, with an exclusive end: a 22:00–02:00 event shows on both days, one ending at midnight stays off the next day.
- Wall views get "today" from `hooks/useToday.ts`, which updates just after local midnight and when the page becomes visible again, so a wall that runs for days doesn't stay on yesterday.

## Authentication

| Who | How | Lifetime |
|---|---|---|
| Family members | The sign-in page shows avatars from `GET /api/auth/profiles` (public; only the picker's fields). Tapping one posts `user_id` + PIN to `/api/auth/login/pin`. `POST /api/auth/login` (name + password) remains. Either returns a JWT in an `access_token` cookie (`HttpOnly`, `Secure`, `SameSite=Strict`). | 30 days. The token's `jti` is a `sessions` row, checked on every request: logout deletes it, a password change deletes the user's other sessions, and removing a user deletes all of theirs. |
| Wall displays | An admin creates a device and gets `/wall?token=…`. The display posts the token to `/api/wall/pair` and receives a `wall_token` cookie scoped to `/api/wall`. Only the token's SHA-256 is stored. | Refreshed on every load, so it never expires while the display is used. **Unpair** revokes it immediately: the display's next request gets 401 and the wall clears its data and shows the pairing screen. |

**Lockout.** Failed PIN and password attempts are counted per person (`LoginThrottle`, in-process). At 5, 10 and 15 failures, sign-in locks for 1, 5 and 15 minutes, and the API responds 429 with `Retry-After`.

**Admin gate.** Sessions record `auth_method` (`pin` or `password`). Admin-only endpoints (`require_role("admin")`, and changing another member's profile) need a password session, or a PIN session that was unlocked by `POST /api/auth/elevate` within the last 15 minutes. Otherwise they answer **403 `password_required`**. The frontend turns that response into a password prompt and retries the request; requests that need the password at the same time share one prompt. `/api/auth/me` reports `auth_method` and `admin_unlocked`.

**Roles.**

| Role | Can do |
|---|---|
| `admin` | Manage members, calendar sources and wall displays; change any family event. |
| `member` | Add events; change or delete their own. |
| `viewer` | Read only. |

Events from subscribed calendars are read-only for everyone, because the next sync would overwrite any change. The frontend mirrors these rules in `lib/permissions.ts` to hide controls (viewers don't see "New Event"), and `/admin/*` pages sit behind `RequireAdmin`, which sends non-admins to the dashboard. The API remains the enforcement point.

**Tenancy.** An install holds exactly one family: setup refuses a second, and the `families_single_row` trigger (migration 006) rejects a second row even if two setup requests race. The public sign-in queries (avatar list, password and PIN login) run before anyone is signed in, so they scope to that install family. Event reads filter on the event's own `family_id` as well as its source's, so a malformed row can't cross families. Sources are created only as `ical`; each family's single `internal` source is created by the server on demand.

A wall display can only read `/api/wall/events` and `/api/wall/members`, and open the `/api/wall/ws` live-update socket. It can't call any user endpoint.

## Calendar sync

- Every 15 minutes, `jobs.calendar_sync.sync_all_due` syncs each enabled `ical` source whose `sync_interval_hours` has passed.
- **Sync Now** (`POST /api/calendar/sources/{id}/sync`) runs the same code immediately.
- A sync fetches the feed (following redirects; `webcal://` is treated as `https://`), parses `VEVENT`s and expands `RRULE`s up to 12 months ahead. The first occurrence keeps the series UID; later ones are `<uid>_<start>`. Every occurrence keeps the series' duration and `all_day` flag. It then upserts events by `external_uid` and soft-deletes UIDs that have disappeared.
- Each run writes a `sync_logs` row; the last error is stored on the source.
- Known gaps (Phase 3 in [TODO.md](../TODO.md)): EXDATE/RECURRENCE-ID handling, floating times read as UTC instead of the family zone, full history being stored, and one UID lookup per event.

## Realtime

Calendar changes call `queue_event(db, "calendar_updated", …)`, and the notice is published only after the transaction commits. The WebSocket hub (`/api/wall/ws`, which only accepts paired displays) forwards it to every connected wall, which then re-fetches its events. Walls reconnect after a drop (`wall/useWallWebSocket.ts`, which stops cleanly on unmount) and also poll every 15 minutes.

## Frontend layout (`frontend/src`)

```
App.tsx            boot: setup status → /auth/me; routes (wall is outside the nav shell); pages are React.lazy chunks
api/               axios client (401 → /login, except /auth/* and /wall/*; 403 password_required → one shared password prompt + retry), React Query hooks; wall.ts onWallUnauthorized
lib/               dates.ts (time convention above), permissions.ts (client mirror of event roles)
hooks/             useToday (local midnight, rolls over)
pages/             Dashboard, CalendarPage, Login (avatar picker + PIN pad), SetupWizard, ManageUsers, admin/CalendarSettings, admin/WallDisplays
wall/              WallLayout (pairing gate, revocation → pairing screen, idle screen), clock, 7-day strip, useWallWebSocket, member list
components/        NavShell (sidebar / mobile bottom nav, "Unlock admin", Help & About), RequireAdmin, PasswordPrompt, Avatar, BuildInfoBadge
test/setup.ts      Vitest setup; tests are *.test.ts[x] next to the code
```

The PWA (`vite-plugin-pwa`) precaches the app shell and every page chunk for offline launch. Only the sign-in page is in the main bundle; each other page loads on first visit.

## Background jobs

| Job | Schedule | What it does |
|---|---|---|
| `calendar_sync_all_due` | every 15 min | Syncs the iCal sources that are due. |
| `daily_backup` | `BACKUP_TIME` in `TIMEZONE` | SQLite online backup to `data/backups/homehub_<date>.db`, then prunes copies older than `BACKUP_RETENTION_DAYS`. |
