## [Unreleased] — Phase 3b: wall essentials (builds 0.84–0.88, 2026-10-12)

### Added
- **Photos & videos**: family members add photos and videos on the new Photos page, and the wall shows them full screen when it's idle, each one before any repeats. Photos lose their location data and are resized for the wall; videos are converted so a Raspberry Pi plays them smoothly, with all their metadata removed. The original upload isn't kept.
- **Sleep schedule**: wall screens can go dark overnight, at times set in the family's timezone; a touch lights them for a few minutes.
- **Family settings** (Admin › Settings): change the family name, timezone and sleep schedule after setup.
- **Off-host backups**: `backup-offhost.sh` copies the daily database snapshots and the photos to a NAS or another disk, and the restore steps now include photos.

### Security
- The family's photo folder was readable without signing in at `/photos/…`. That route is gone: photos and videos are served only to signed-in family members and paired wall displays.

### Changed
- The API image is about 70 MB larger (ffmpeg and Pillow).

---

## [Unreleased] — Phase 3: iCal correctness (builds 0.75–0.82, 2026-10-12)

### Fixed
- Subscribed calendars honour cancelled and moved instances of repeating events (EXDATE, RECURRENCE-ID, and cancelled events), and extra dates (RDATE). A moved instance no longer appears twice.
- Repeating events keep their local time across daylight-saving changes (a 9:00 meeting stays at 9:00 in November).
- Times without a timezone in a feed are read in the family's timezone instead of UTC. New installs default the family timezone to the device's zone (it used to default to UTC) and can pick any zone.
- Adding a calendar downloads it once and refuses it, with the reason, if the first sync fails (for example a URL that returns a login page).
- Editing a calendar source through the API no longer fails with a server error.
- If the password prompt is closed unexpectedly, later admin actions no longer hang.

### Changed
- Only events from 90 days ago to a year ahead are stored for subscribed calendars; long-running series no longer generate every instance since they began, and each sync looks up existing events in one query.

### Added
- Test coverage: backend 96% and frontend 93% of statements, measured in CI, which now fails below set thresholds. New tests cover backups, sign-in, the calendar and admin pages, wall pairing and app boot.

---

## [Unreleased] — Review fixes (builds 0.31–0.73, 2026-10-12)

> Entries are keyed by roadmap phase or work batch, not by commit. The per-commit build number lives in `VERSION` (repo root) and advances with every commit; when a batch is confirmed on the `test` VM, its heading gets the build that shipped it (`[0.<n>] - <date> — …`).

### Changed
- Every commit now carries its own version, `0.<n>`, incremented by one per commit by a `pre-commit` hook and enforced in CI. The CI run-number suffix (`0.30.17`) is gone; images are tagged `0.<n>` with a matching `v0.<n>` release tag.
- Pages load on demand, so the first download is about 45% smaller (351 KB, down from 626 KB).

### Fixed
- Wall displays now update live after scheduled and automatic calendar syncs, not only after manual changes. Live-update notices are sent only after the change is saved, so a wall never re-reads stale data.
- Calendar-feed fetches connect to the address the safety check approved (closing a DNS-rebinding gap) and refuse feeds over 10 MB.
- Recurring calendar-feed events no longer show their first occurrence twice, all-day repeating events stay all-day, and all-day series that end with a UTC timestamp keep their repeats.
- The wall's seven-day view moves on at midnight instead of showing yesterday until it's reloaded, and timed events that cross midnight appear on both days.
- A wall display whose pairing is revoked returns to the pairing screen instead of freezing on its last calendar, and closed walls no longer keep reopening live-update connections.
- Two admin actions that both need your password now share one prompt; previously one of them could hang.
- Viewers no longer see "New Event", and failed saves or deletes show the server's reason.
- Admin pages redirect members and viewers to the dashboard instead of showing empty lists.
- Admins can no longer create extra, undeletable "internal" calendars, and event lookups check the event's own family as well as its calendar's.
- Each install holds exactly one family. The database now rejects a second one (even if two setup attempts race), and sign-in only offers and accepts that family's members. Applied automatically at startup (migration 006).

### Added
- Frontend unit tests (Vitest; `npm test`, run in CI) and a startup test that boots the real app to check migrations and scheduled jobs.

---

## [0.30] - 2026-10-05

> **Version numbering:** this release follows 0.18. Versions 0.19–0.29 (and the
> other line's own "0.18", with chores/rewards/meals) belong to the retired
> `main` line, a separate codebase that is now a reference for features being
> ported (see TODO.md). Numbering continues at 0.30 so no existing tag collides.

### Added
- **Family sign-in picker**: tap your avatar and enter a PIN. Passwords still work, and are required for admin changes. An admin who signed in with a PIN is asked for their password once, which unlocks admin actions for 15 minutes ("Unlock admin" in the sidebar).
- Emoji avatars and colors for family members; the setup wizard accepts an optional admin PIN.
- **Database migrations run automatically at startup** (Alembic). Installs created before 0.30 are detected and stamped, then upgraded.
- CI runs frontend lint and build, and the tests get a `SECRET_KEY`.

### Security
- Sign-in sessions are stored server-side. Signing out, changing a password (other devices) and removing a member now end those sessions immediately. A token without a live session is rejected.
- Failed PIN and password attempts are counted per person, with an escalating lockout (1, 5, then 15 minutes).
- Event permissions: viewers are read-only; members change their own events; admins change any family event; events from subscribed calendars are read-only. Event edits are checked against the family before anything is written.
- Display names are unique within the family (ignoring case).
- Removed `POST /api/users/switch`, which created a login token for any user ID.
- The wall's live-update socket (now `/api/wall/ws`) only accepts paired displays.

### Fixed
- PWA offline caching never matched API requests; it now caches calendar events, sources and members (not sign-in state).
- The wall idle timeout uses `WALL_IDLE_TIMEOUT_SECONDS`.
- `setup-wall-pi.sh` is safe to re-run and works on Raspberry Pi OS Bookworm (`chromium`, Wayland autostart, `raspi-config` blanking).

### Removed
- The unused notifications stub, the `/lists` and `/admin/settings` placeholders, and the nonexistent `co_admin` role checks.
- The sprint planning manifests moved to `docs/archive/planning/`.

---

## [0.18] - 2026-10-04

### Added
- Wall display pairing: admins create a revocable pairing link (Admin › Wall displays). Displays stay signed in without a family member's login, and an unpaired display shows the clock and a pairing hint.
- Registry deployment: `deploy.sh publish` builds multi-arch images and pushes them to the Forgejo registry. `deploy.sh remote <host>` installs or upgrades a server over SSH, using `deploy/compose.yml`.
- Behind-proxy mode (`config/Caddyfile.proxy`); the hostname and ports are configurable.
- `backend/scripts/fix_event_timezones.py` converts events created in the app before 0.18.
- Documentation: rewritten README and developer guide, new `docs/deployment.md` and `docs/architecture.md`.

### Fixed
- Refreshing a page or opening `/wall` no longer redirects to the dashboard.
- A wrong password or PIN now shows an error instead of reloading the login page.
- Event times are stored in UTC and shown in local time. Subscribed-calendar events were shifted by the UTC offset, and all-day events now stay on the correct day.
- Multi-day events and the edge days of the month grid now appear; agenda view covers 30 days.
- **Sync Now** actually syncs. **Delete** removes the source and its events. Feeds that redirect and `webcal://` links work.
- The first event created in the app no longer stays hidden until a reload.
- Scheduled re-syncs no longer crash (naive vs. aware datetime).
- The daily backup runs at `BACKUP_TIME` in `TIMEZONE`, not at that time in UTC.
- `deploy.sh deploy` rebuilds images, and `setup` generates `SECRET_KEY`.
- Docker builds from a Mac checkout no longer break (`.dockerignore`); the API image has a healthcheck.

---

## [0.17] - 2026-05-16

### Added
- Notification service framework with Email and Discord webhook support (stub implementations)
- Test history documentation

### Fixed
- README branding: `OpenFamhub` → `OpenFamHub`

---

## [0.16] - 2026-05-16

### Added
- Deploy script (`scripts/deploy.sh`) for streamlined releases
- Raspberry Pi wall display setup script (`scripts/setup-wall-pi.sh`)
- Wall screen setup guide (`docs/wall-screen-setup.md`)
- MVP readiness checklist (`docs/mvp-checklist.md`)
- Backend test infrastructure: `conftest.py` fixtures, `test_auth.py`
- Test history documentation (`docs/test-history.md`)

### Changed
- README expanded with hardware setup, deployment, and wall display sections

---

## [0.15] - 2026-05-15

### Added
- Sprint 5: Wall display at /wall — full-screen 1920x1080 layout, live clock, 7-day calendar strip with color-coded event pills, family member list, idle mode with photo placeholder
- Sprint 5: WebSocket endpoint `/api/ws/wall` with EventBus + ConnectionManager for real-time calendar updates pushed to wall clients
- Sprint 5: Dashboard with time-based greeting, today's events widget (Suspense-wrapped), sync status summary for admins
- Sprint 5: Navigation shell — desktop left sidebar (240px) with user avatar/logout, mobile bottom nav bar, layout route pattern via `<Outlet>`
- Sprint 5: PWA service worker + install manifest + cert-trust documentation for macOS/iOS/Android/Pi OS/Windows
- Recurring event expansion from ICS feeds now handles RRULE, EXDATE, RDATE across a 12-month window

---
## [0.14] - 2026-05-15

### Added
- Sprint 4: ICS feed integration — fetch, parse, expand recurring events, upsert
- Sprint 4: Calendar sync job — APScheduler runs every 15min, syncs due sources
- Sprint 4: Daily database backup job with retention-based pruning
- Sprint 4: POST /api/integrations/ical endpoint — admin adds ICS URL with color/interval
- Sprint 4: Calendar Settings admin page — connected sources list, Sync Now, sync log drawer, Add ICS Feed form

### Fixed
- Pydantic response datetime serialization for last_synced_at and synced_at fields

### Changed
- Version bump 0.13 → 0.14

---

## [0.13] - 2026-05-15

### Added
- Sprint 3: Calendar data model — CalendarSource, CalendarEvent, SyncLog tables
- Sprint 3: Calendar API — full CRUD for events and sources (GET/POST/PATCH/DELETE)
- Sprint 3: Calendar UI — Month/Week/Day/Agenda views with react-big-calendar
- Source filter chips with color-coded visibility toggles
- Swipe gesture navigation via @use-gesture/react
- Event detail modal with admin delete capability

### Changed
- Event color is driven by source color_hex throughout the stack
- Version bump 0.12 → 0.13

### Fixed
- passlib/bcrypt 4.x compatibility — pinned bcrypt to 4.0.1
- Response datetime serialization in Pydantic schemas (datetime → ISO string)
- SQLAlchemy async MissingGreenlet errors in calendar PATCH/DELETE (using sql_update)

---

## [0.12] - 2026-05-15

### Added
- Sprint 2: Auth system (setup, login, PIN login, logout, /me)
- Sprint 2: User management (CRUD, PIN set, role-based access)
- Sprint 2: Database migrations (sessions table, user timestamps)
- Frontend: Setup wizard, login page, manage users page

---

## [0.11] - 2026-05-15

### Added
- Sprint 1: Infrastructure scaffold — Docker Compose (api + web + caddy), FastAPI skeleton with health endpoint, React/Vite/Tailwind frontend with PWA, CI workflow (AMD64 only)
- GitHub repo renamed from HomeHub to OpenFamHub, pushed to vnmyers13/openfamhub
- All documentation updated to reflect new project name and repo URL

### Changed
- Renamed project from HomeHub to OpenFamHub across all docs, config, and UI

---

# Changelog

All notable changes to OpenFamHub are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Version numbers follow `MAJOR.MINOR` format. MINOR increments by 1 each release.

---

## [0.10] - 2026-05-15

### Added
- Initial MVP: shared family calendar with ICS feed subscriptions
- Internal calendar: create/edit/delete events with recurrence support
- Family member profiles: role-based access, PIN and password login
- Google Calendar and Apple iCloud import via ICS URL feeds
- Wall display at /wall: full-screen 7-day calendar strip at 1920×1080
- PWA support: installable on Android and iOS
- Offline read capability via Workbox service worker
- Admin calendar settings: add/remove ICS feeds, per-source sync interval
- Sync log: view last sync time, events imported, and errors per source
- Docker Compose deployment on AMD64 Linux
- Raspberry Pi kiosk boot script for wall display
- Daily automated SQLite backup

### Infrastructure
- FastAPI async backend with SQLAlchemy 2.0 + aiosqlite
- React 19 + TypeScript + Vite + Tailwind frontend
- Caddy reverse proxy with automatic internal TLS
- GitHub Actions CI (AMD64 only)
- PWA service worker with runtime caching

---

*This file is maintained by the release checklist. Run Phase P2 to bump the version and prepend a new entry.*
