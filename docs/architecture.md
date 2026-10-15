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
services/          calendar (range query, internal source), users, push (Web Push sending, Phase 11), …
integrations/      ical_feed: fetch + parse + expand RRULEs
jobs/              scheduler, calendar_sync (every 15 min, per-source interval), backup (daily), reminders (every minute), …
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

A wall display can only read its `/api/wall/*` data, and open the `/api/wall/ws` live-update socket. It can't call any user endpoint. The data: `events`, `members`, `media`, `routines`, `progress` and `birthdays` (`routers/wall.py`), and the Phase 10 panels in `routers/wall_panels.py`: `chores` (today's, without routine steps), `meals` (this week's plan, or `?start=`), `announcements` (10, pinned first) and `weather`. The panels reuse the member endpoints' queries, scoped to the display's family, and answer only GET.

## Calendar sync

- Every 15 minutes, `jobs.calendar_sync.sync_all_due` syncs each enabled `ical` source whose `sync_interval_hours` has passed.
- **Sync Now** (`POST /api/calendar/sources/{id}/sync`) runs the same code immediately.
- A sync fetches the feed once (following redirects; `webcal://` is treated as `https://`) and `parse_ics` turns it into events inside the **storage window**, 90 days back to 365 days ahead:
  - Every occurrence is computed as a UTC instant. Dates are all-day (`00:00Z`); zoned times use their `TZID` (converted from pytz to zoneinfo so series keep their wall time across DST); **floating times** (no zone) are read in the family timezone.
  - `RRULE`s expand inside the window only, plus `RDATE`s, minus `EXDATE`s. A `RECURRENCE-ID` override replaces the instance it names, or drops it if `STATUS:CANCELLED`, and keeps that instance's UID. The DTSTART occurrence uses the series UID; others are `<uid>_<start>`. Every occurrence keeps the series' duration and `all_day` flag.
- The sync loads the source's existing rows in one query, upserts by `external_uid`, soft-deletes UIDs that disappeared (restored under the same id if they return), and deletes outright rows that have left the window.
- Adding a feed runs its first sync as the reachability check, inside a savepoint: if it fails, nothing is saved and the admin gets the reason (400).
- Each run writes a `sync_logs` row; the last error is stored on the source.
- The family timezone is set in the setup wizard and changed under **Admin › Settings**.

## Photos and videos (wall slideshow)

- **Upload** (`POST /api/media`, admins and members): the file is the raw request body, streamed to `data/photos/media/.incoming/` with a running size check (500 MB upload, 30 MB photo, 10-minute video). The type comes from the first bytes (JPEG, PNG, WebP, GIF, HEIC/HEIF; MP4/MOV, WebM), never the client's header.
- **Photos** are processed in a worker thread with Pillow plus `pillow-heif`: camera rotation applied, converted to RGB, saved as `wall.jpg` (long edge ≤ 1920) and `thumb.jpg` (≤ 400) with no EXIF.
- **Videos** answer 202 and convert in the background (one at a time) with ffmpeg from `imageio-ffmpeg`: H.264/AAC MP4, ≤ 1920×1080, `-map_metadata -1` (no location, titles or dates), faststart, plus a thumbnail. The item is `processing`, then `ready` or `failed` (with the reason). Conversions interrupted by a restart are marked failed at startup.
- **Storage**: `data/photos/media/<family_id>/<media_id>/`; the uploaded original is deleted after processing. The `media` table (migration 007) has `family_id` on every row.
- **Serving**: only `/api/media/{id}/{wall|thumb}` (signed-in family members) and `/api/wall/media/{id}/{wall|thumb}` (paired displays), with HTTP range support for video. There is no public static route to `data/photos`.
- **Deleting**: the uploader or an admin; files go with the row.

## Family settings and the wall's sleep schedule

`GET /api/family` (members) and `PATCH /api/family` (admins with an unlocked session) hold the family name, the IANA timezone and the wall sleep schedule (`enabled`, `off`, `on` as HH:MM; `off` later than `on` means overnight), stored in `families.settings_json`. The wall session returns the timezone and schedule; the wall evaluates the schedule itself with `Intl` in the family timezone (`lib/sleep.ts`), so it follows DST regardless of the display's own zone. The wall clock (`WallClock`) shows the time and date in the family timezone the same way. Up to three extra clocks (`settings_json.clocks`, a label and an IANA zone each, set in Admin › Settings) come in the wall session and show under it. A display can read the timezone but not change it. While asleep the screen is black; a touch lights it for one idle period. Changing settings pushes `settings_updated`, and the wall refetches its session.

While the board is active it shows the family wall dashboard (below): `wall/WallCycle.tsx` turns its pages (timing in `wall/wallCycle.ts`) under a header bar with the time and date in the family timezone, any extra clocks, the page's name and a "Next in …" countdown. The countdown re-renders every second; the page's cards only when the page changes.

On the idle screen `WallSlideshow` shows the family's ready media full screen, in an order from `lib/shuffle.ts` that uses every item before repeating; photos stay up 12 s, videos play muted to the end.

## Chores, routines, to-dos and points

- **Templates** (`chore_templates`, admins) hold a chore's title, points, who does it (`assigned` to one member, or `claimable` by anyone) and a repeat rule: once, every N days, weeks on chosen weekdays, or months on a day (1–28, or −1 for the last day), anchored to a start date and expanded with dateutil's rrule.
- **Instances** (`chore_instances`) are one chore on one **family-local date** (`family_today` uses the family timezone, not UTC). `(template_id, due_date)` is unique. `jobs/chore_generator.py` runs hourly and at startup: it creates instances a week ahead and marks earlier open ones `missed`. Creating or editing a template rebuilds its open instances from today.
- **Lifecycle**: `pending` → `claimed` (claimable chores, by anyone but viewers; assigned chores only by the assignee or an admin) → `completed`; `undo` reopens. Completing is a conditional update (only one request can move it out of an open state), writes a `chore_completions` audit row and, if it's worth points, a `points_ledger` entry for the assignee (else whoever claimed it). Undo marks the completion undone and writes a reversal entry.
- **Points ledger** (`points_ledger`): append-only; a balance is the sum of a member's deltas; `(source_type, source_id)` is unique, so one completion can't credit twice. Rewards spend from it (see below).
- **Routines** (`routines`): a name, start time (family timezone), repeat and assignee, with ordered steps that are chore templates (`routine_id`, `position`, `minutes`). Steps follow the routine's schedule, get daily instances and are completed like chores. Saving a routine's steps keeps their list order; removed steps retire with their history. `GET /api/routines/today` and the paired-display `GET /api/wall/routines` return today's runs.
- **To-dos** (`todos`): one-off tasks with an optional assignee and due date; no repeat, no points.

## Books, announcements, weather, birthdays and Home

- **Books** (`/api/books`): a book is on someone's list (`owner_id`) or in the family library (`owner_id` null). Moving a library book to reading or finished makes you its `reader_id`. Finishing credits the reader 50 points, as a ledger row (`source_type="book"`) keyed by book and reader, so it pays once ever.
- **Announcements** (`/api/announcements`): pinned first, then newest.
- **Weather** (`/api/weather`, `services/weather.py`): Open-Meteo forecast and geocoding at fixed hosts, cached 10 minutes in-process per place, units and timezone. The location is `families.settings_json["weather"]`. Failures return `error` instead of failing.
- **Birthdays** (`users.birthday`): `services/birthdays.py` computes the next birthday and age (29 Feb → 28 Feb in other years). It adds read-only all-day entries (`source_id="birthdays"`, with an `external_uid`) to `get_events_in_range`, so they show on the calendar and the wall. `/api/wall/birthdays` lists the next 14 days.
- **Home** (`/api/dashboard/summary`): today's events, chore counts, my points and allowance, the week's meals, birthdays in the next 30 days and recent announcements. `?scope=mine` (also on `/calendar/events`) keeps only events I added, plus my birthday.
- **Preferences** (`/api/users/me/preferences`, `users.settings_json["prefs"]`):
  - Menu position: side or top. Phones always get the bottom bar, with "More".
  - Calendar scope: everyone or just me.
  - Wallpaper: a gradient or a media id.
  - Up to 6 dashboard pages, each a list of widget keys and sizes. An empty list means the default page.
- **Family wall dashboard** (`/api/family/wall-dashboard`, `families.settings_json["wall_dashboard"]`): shared by the whole family and editable by any signed-in user. It stores wall pages, card order, card size and page duration; `/api/wall/session` returns it to paired wall displays, which render it read-only through paired-device endpoints for events, chores, routines, meals, weather, announcements, progress and birthdays. A `clock` card shows the big wall clock with the extra clocks.

## Reading photos (OCR)

Scan a list (shopping) and Import › read a photo (recipes) read text on the device with tesseract.js; the photo is never uploaded. `lib/ocr.ts` loads the library on demand and runs it LSTM-only with its worker, engine and English model served by OpenFamHub from `/ocr/`, never a CDN, so it works on a LAN without internet. `scripts/ocr-assets.mjs` copies them from `node_modules` into `public/ocr/` before `dev` and `build` (not committed). The service worker skips them at install (about 7 MB) and caches them on first use.

- `lib/ocrLines.ts` turns list text into items with quantities, and classifies headings ("Produce:", "DAIRY") and debris to skip. Things already on the list start unticked.
- `lib/ocrRecipe.ts` joins steps that wrapped across lines (never ingredient lines), and the text goes into the paste box for the existing recipe reader (`smart_import.recipe_from_text`), so people check it first.
- `lib/ocr.real.test.ts` runs the real engine in Node on the sample photos in `src/test/fixtures/`.

## Offline

- **Reads:** the service worker (`lib/swCaching.ts`) caches reads network-first: the calendar, users, and for offline use `auth/me`, chores, to-dos, the shopping list, the meal plan and recipes, and the dashboard summary. Logout clears these caches.
- **Writes:** `lib/offline.offlineWrite` sends the write now, or, if there's no reply, puts it in IndexedDB (`lib/idb.ts`, store `writes`) and the screen updates optimistically. Used for chore actions, adding and ticking shopping items, adding and editing to-dos, and setting and clearing meal-plan slots (a queued clear sends its `base` in the DELETE body).
- **Replay:** `replay()` runs oldest first, one write at a time, with the cookie and `Idempotency-Key: <write id>`. `useOfflineSync` triggers it on start, on `online`, on tab-visible, and every minute while anything is waiting. A write is removed only after a 2xx.
  - 409: the write is kept with the conflict. Keep mine or merge re-queues it under a new id (so a new Idempotency-Key: the server remembers its 409 for the old one).
  - Another 4xx: kept with the reason.
  - 401: kept, and the app asks to sign in again.
  - No reply or 5xx: the replay stops and everything stays queued.
- **Server side:**
  - `core/idempotency.IdempotencyMiddleware` stores the first reply for each (key, cookie, method, path) for 24 h, in process.
  - Edits may carry `base`, the item as last seen. `core/conflicts.check_base` answers 409 with `{message, fields, current}` if it changed.
- **Resolving a conflict** (`OfflineStatus`): keep mine resends without `base`; keep theirs drops the write; merge resends only my fields that the other person didn't change.

## Meals

All under `/api/meals` (`routers/meals.py`, rules in `services/meals.py`). Viewers can read but not change anything.

- **Recipes** (`recipes`): title, tags (lowercase words), servings, times, ingredient and step lines, and source and video links (http(s) only). Deleting is a soft delete, and planned meals keep their title. `GET /catalog` lists the built-in ideas (`app/data/recipe_catalog.json`); `POST /catalog/{key}` copies one in, once.
- **Plan** (`meal_plan_entries`): one row per family, day (family-local `Date`) and slot (`breakfast|lunch|dinner|snack`), holding a recipe or just a title. `PUT /plan/{day}/{slot}` sets one slot; `PUT /plan/week/{monday}` replaces a whole week.
- **Shopping list** (`shopping_items`): `source` is `manual`, `plan` or `pantry`.
  - `POST /shopping/from-plan` makes the week's `plan` lines match the planned recipes. It's idempotent, keyed by recipe and line, and never touches checked or manual items.
  - `jobs/shopping_reset.py` runs hourly. At the family's Monday it archives items bought before this week (`archived_at`; they stay as `GET /shopping/history`) and drops unbought `plan` lines from past weeks.
- **Pantry** (`pantry_items`): low means `quantity <= low_at`; expired or expiring soon (within 3 days) are computed against the family's today. `POST /pantry/restock` puts low or expired items on the list once. Shopping lines show `in_pantry` when a usable pantry item's name appears in them.
- **Smart Import** (`/api/import/recipe`, `/api/import/event`, `integrations/smart_import.py`): a link or pasted text becomes a draft; nothing is saved. schema.org JSON-LD is read first (including `@graph`, `HowToSection` and ISO durations); recipes fall back to a plain-text parser. Event times without an offset are the family's local time; all-day events get an exclusive end. Links are fetched by `core/safe_fetch.fetch_public`, which checks the address and pins the connection on every hop and caps the response at 3 MB and 20 s. Calendar feeds use the same fetcher.

## Rewards, badges and allowance

All under `/api/rewards` (`routers/rewards.py`, rules in `services/rewards.py`). Viewers can look but not spend; admin endpoints need the password gate.

- **Catalog** (`rewards`): name, icon, point cost, and whether it needs an admin's yes. Rewards are retired, never deleted.
- **Redemptions** (`reward_redemptions`): redeeming checks the balance and writes a `-cost` ledger row (`source_type="reward"`) straight away, so a pending request can't be spent twice. An instant reward is `approved` at once; otherwise it's `pending` until an admin approves or rejects it, or its owner cancels it. Leaving `pending` is a conditional update, and rejecting or cancelling writes one `reward_refund` row. The reward's name and cost are copied onto the redemption.
- **Badges** (`badge_definitions`, `user_badges`): earned by `chores_completed`, `streak_days` or `points_earned` (net chore points). `award_badges` runs inside the chore-completion transaction and when a badge is created or edited. `(user_id, badge_id)` is unique, and a bonus is a ledger row keyed by the award.
- **Streaks**: consecutive family-local days with a completion that isn't undone, ending today or yesterday.
- **Allowance** (`allowance_plans`, `allowance_ledger`): whole cents. `jobs/allowance.py` runs hourly: for each plan it pays every week from `start_week` up to the latest Monday 07:00 (family time) not yet paid, capped at 8 weeks back. `(user_id, week_start)` is unique. Admins record payouts as negative adjustments; a new or restarted plan starts at the next Monday.
- **Progress**: `GET /api/rewards/progress` and the paired-display `GET /api/wall/progress` return each non-viewer's balance, points earned since Monday (chores and badges, not spending), streak and badges.
- **Wall**: `WallRoutines` shows a routine from half an hour before its start until its steps are done or its time is up: the current step (steps run back to back from the start time, `lib/routine.ts`), a live countdown and progress, or "No routine right now" (`lib/routine.routineShowsOnWall`). The current step has a **Done** button: `POST /api/wall/routines/steps/{id}/complete` completes it for the step's assignee if it's one of today's routine steps in the display's family and assigned to someone; otherwise 404/403, and a completed step is returned unchanged.

## Notifications (Web Push, ntfy, email)

- **Keys:** the install's VAPID key pair is made on first use and kept in `push_keys` (migration 012). `GET /api/push/key` gives browsers the public half.
- **Devices:** `POST /api/push/subscriptions` stores what `PushManager.subscribe()` returns (endpoint + keys), one row per endpoint; a shared device belongs to whoever subscribed last. `DELETE` removes it; `POST /api/push/test` sends yourself a test. The app side is `lib/push.ts` (state, turn on/off) and `public/push-sw.js` (imported into the generated service worker: shows the notification, and a tap opens the app at its page, same origin only).
- **Sending** (`services/push.py`): each payload is encrypted for the device (RFC 8291, `http-ece`, aes128gcm, a fresh key per message) and signed (RFC 8292 VAPID JWT, `py-vapid`; `sub` is the first `ALLOWED_ORIGINS` URL). Endpoints come from browsers, so they get the SSRF treatment: https only, the host must resolve to public addresses, and the POST is pinned to the checked address. 404/410 drop the subscription; other failures keep it.
- **ntfy and email** (`services/notify.py`): the server's ntfy server and SMTP account are settings (`NTFY_URL`, `NTFY_TOKEN`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY` starttls|ssl|none, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM`; each channel is off while empty), so their secrets stay out of the database and UI. Each person picks `notifications.ntfy_topic` and `notifications.email_to`. `deliver(db, user, payload)` sends to their devices, topic and address and counts what was accepted; ntfy gets a JSON publish with a `click` link (first https `ALLOWED_ORIGINS` URL + the page), email a plain-text message in a thread (`smtplib`, 15 s timeout). The ntfy server is the operator's, so it isn't SSRF-checked (it may be on the LAN). `GET /api/push/channels` says which channels the server offers; `POST /api/push/test` sends to all of them.
- **Reminders** (`jobs/reminders.py`, every minute), per person with a device, ntfy topic or email address, by `Preferences.notifications`: events (`off` by default, `mine` = events they added, `all` = every timed family event; 5–60 minutes before, never after the start; all-day events skipped), a daily list of their chores and to-dos at `daily_time` in the family timezone, reward requests waiting for a yes (admins), at `daily_time` the day before someone's birthday (`birthdays`, not to the birthday person) and pantry items with `expires_on` today or tomorrow (`pantry`, members and admins, one list a day), weekly allowance payouts from the last two days (`allowance`, to the child), and wellness, off by default: `water` every `water_every` minutes from `water_from` to `water_until` and `mindful` once at `mindful_time`, sent with `deliver(..., email=False)` and skipped if more than 15/30 minutes late. `notifications_sent` (unique per person, kind, reference) makes each one go out once; a reminder no channel accepted is tried again next minute (one accepted is enough). Quiet hours are the wall's sleep schedule: nothing is sent; daily lists and waiting requests go out when it ends.

## Realtime

Changes call `queue_event(db, "calendar_updated" | "media_updated" | "settings_updated" | "chores_updated" | "rewards_updated" | "meals_updated" | "books_updated" | "announcements_updated", …)`, and the notice is published only after the transaction commits. The WebSocket hub (`/api/wall/ws`, which only accepts paired displays) forwards it to every connected wall, which then re-fetches its events. Each wall opens one socket (`wall/useWallWebSocket.ts`, which reconnects after a drop and stops cleanly on unmount) and refetches the matching data; walls also poll every 15 minutes.

## Frontend layout (`frontend/src`)

```
App.tsx            boot: setup status → /auth/me; routes (wall is outside the nav shell); pages are React.lazy chunks
api/               axios client (401 → /login, except /auth/* and /wall/*; 403 password_required → one shared password prompt + retry), React Query hooks; wall.ts onWallUnauthorized
lib/               dates.ts (time convention above), permissions.ts and choreActions.ts (client mirrors of the API's rules), sleep.ts, shuffle.ts, timezones.ts, repeat.ts, routine.ts, ocr.ts, ocrLines.ts, ocrRecipe.ts
hooks/             useToday (local midnight, rolls over)
pages/             Dashboard, CalendarPage, chores/ (Today, To-dos, Routines, Manage, History), rewards/ (Rewards, Requests, Badges, Allowance, Manage), meals/ (This week, Recipes, Shopping list, Pantry), books/, dashboard/ (cards, Customize), MySettings, PhotosPage, Login (avatar picker + PIN pad), SetupWizard, ManageUsers, admin/CalendarSettings, admin/WallDisplays, admin/FamilySettings
wall/              WallLayout (pairing gate, revocation → pairing screen, live session, sleep schedule, idle screen), WallSlideshow, WallRoutines, clock, 7-day strip, useWallWebSocket, member list
components/        NavShell (sidebar / mobile bottom nav, "Unlock admin", Help & About), RequireAdmin, PasswordPrompt, Avatar, BuildInfoBadge
test/setup.ts      Vitest setup; tests are *.test.ts[x] next to the code
```

The PWA (`vite-plugin-pwa`) precaches the app shell and every page chunk for offline launch. Only the sign-in page is in the main bundle; each other page loads on first visit.

## Background jobs

| Job | Schedule | What it does |
|---|---|---|
| `calendar_sync_all_due` | every 15 min | Syncs the iCal sources that are due. |
| `chore_generator` | hourly at :05, and at startup | Creates chore instances a week ahead for each family (in its timezone) and marks earlier open ones missed. Idempotent. |
| `reminders` | every minute | Sends due reminders by Web Push (see Notifications). Each one once; nothing in quiet hours. |
| `daily_backup` | `BACKUP_TIME` in `TIMEZONE` | SQLite online backup to `data/backups/homehub_<date>.db`, then prunes copies older than `BACKUP_RETENTION_DAYS`. |
