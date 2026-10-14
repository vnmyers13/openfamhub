# OpenFamHub — TODO

Known bugs and planned fixes, from the code review of 2026-10-04. Phase 1 shipped in v0.18.

## Decisions (2026-10-04)
- **Direction:** port v0.29's features onto this codebase (0.18 base). `origin/main` is reference only.
- **Data:** start fresh. No importer from a v0.29 database.
- **Sign-in:** an avatar picker + PIN for everyone; a password is required for admin actions.
- **Versioning:** the merged line continues at **0.30**, above every existing tag. CHANGELOG notes that 0.19–0.29 belong to the retired `main` line.
- **Order:** keep the phase order below.
- **Families (2026-10-12):** one family per install, enforced by setup and a database trigger; public sign-in is scoped to that family (#5). Multi-family hosting would need an explicit family on sign-in and is not planned.

## Release plan

Releases are **phases**, not version numbers. Every commit gets its own build number (`<release>`, named from the integer in `VERSION`), so a number can't be reserved for a planned release. When a phase's tests pass in CI and its build is checked on the `test` VM, record that build in **Shipped in** and give the phase its CHANGELOG entry.

| Release | Contents | Shipped in |
|---|---|---|
| Phases 2 + 4 | Security, sign-in model, infra/CI | 0.30 |
| Review fixes | Review backlog below (SSRF, wall live updates, per-commit versioning, iCal recurrences, wall/auth UI fixes, test runner, code splitting) | code complete at 0.73 except the prod host (deferred); 1.01, confirmed on test at 1.28 |
| Phase 3 + 3b | iCal correctness (code complete at 0.82); wall essentials: photo/video slideshow, sleep schedule, family settings, off-host backups (code complete at 0.88) | 1.01, confirmed on test at 1.28 |
| Phase 5 | Chores, to-dos, routines (code complete at 0.94) | 1.01, confirmed on test at 1.28 |
| CI + release process | Trivy scan, issues closed from TODO.md, Triage report, release names past 0.99 | 1.01, confirmed on test at 1.28 |
| Phase 6 | Rewards: catalog with approval, badges and streaks, weekly allowance in cents, family progress widget (code complete at 1.12) | 1.28 |
| Phase 7 | Meals: recipes with import, catalog and cook mode; weekly plan; shopping list from the plan; pantry; event import (code complete at 1.19) | 1.28 |
| Phase 8 | Books, announcements, weather, birthdays, dashboard summary and customization, top/side menu (code complete at 1.24) | 1.28 |
| Phase 9 | Offline sync: queued writes for chores, to-dos and shopping, idempotent replay, conflict choices, offline banner (code complete at 1.28) | 1.28 |
| Phase 10 | OCR, wall panels | |
| Phase 11 | Notifications and reminders | |
| Phase 12 | Home Assistant, AI, notes | |
| Phase 13 | Two-way calendar sync | |

**Release 1.01 (2026-10-13)** collects Review fixes, Phases 3 + 3b and Phase 5 with the CI and release-process work; notes in [docs/releases/v1.01.md](docs/releases/v1.01.md). It was never checked on `test` on its own; `test` ran 1.28 when it was confirmed (2026-10-14).

**Release 1.28 (2026-10-14)** collects Phases 6–9, recipe scaling and the 1.08 security fixes; notes in [docs/releases/v1.28.md](docs/releases/v1.28.md). Follow-ups left open in those phases (wall routine check-off, reward notifications, members editing their own profile, more offline writes) are listed under each phase.

The `pre-commit` hook bumps `VERSION` on every commit (see `docs/ci.md`); CI publishes each `master` build and deploys it to `test`. The release steps, including the issue checks, are in [docs/releasing.md](docs/releasing.md).

**Before starting any phase:**
1. Read the pinned **Triage report** issue on Forgejo (CI refreshes it on every build), or run `python3 scripts/issues.py triage`.
2. Add every issue it lists as missing to TODO.md, in the phase that will fix it or under **Open issues**, with a priority.
3. Fix open **P0** and **P1** items before the phase's feature work. **P2**/**P3** items can wait for the phase they're scheduled in.
4. Tick the phase's "Before starting" item below, then write the phase's tests first.

## Open issues

Forgejo issues not yet scheduled into a phase, highest priority first. Every open issue must appear in this file, here or in the phase that will fix it, with a priority: **P0** fix before the next release is confirmed, **P1** before the next phase starts, **P2** schedule into a phase, **P3** someday. Run `python3 scripts/issues.py triage` at the start of each phase and before each release; it lists issues missing from this file with a line ready to paste. An issue closes automatically once every line naming it is ticked (see [docs/releasing.md](docs/releasing.md)).

Triaged 2026-10-13: 68 open issues, all from the Trivy image scan. Build 1.08 cleared 24 of them (closed by CI); the 44 Debian package issues remain. They're grouped by the change that clears them; tick a line once the rebuilt image scans clean for every issue on it.

- [x] **P1** Replace `python-jose` with PyJWT in `backend/app/core/security.py` (only `jwt.encode`/`jwt.decode` with HS256 are used). Clears python-jose CVE-2026-85394 ([#17](http://192.168.10.2:3002/vernon/OpenFamHub/issues/17)). Fix before Phase 6.
- [x] **P2** Drop `ecdsa` with the python-jose swap above; it only comes in as a python-jose dependency. CVE-2024-23342 (#18).
- [x] **P2** Bump `fastapi` (pinned 0.115.6) to a release whose Starlette is patched: starlette CVE-2025-62727, CVE-2026-48818, CVE-2026-54283 (#19, #31, #36).
- [x] **P2** Bump `python-multipart` (pinned 0.0.20): CVE-2026-24486, CVE-2026-42561, CVE-2026-53539 (#26, #30, #32).
- [x] **P2** Bump `Pillow` (pinned 11.3.0; check `pillow-heif` compatibility and rerun the media tests): CVE-2026-25990, -40192, -42311, -54058, -54059, -54060, -55379, -55380, -59197, -59199, -59200, -59204, -59205 (#27, #28, #29, #33, #34, #35, #41, #42, #43, #44, #45, #46, #47).
- [x] **P2** Frontend npm advisories (found 2026-10-13, already in the lockfile before Phase 10): axios (prototype pollution, high), react-router / react-router-dom (open redirect and XSS in RSC error handling, high), form-data (CRLF injection, high, via axios), moment (path traversal, moderate). `npm audit fix` (no `--force`) resolves all five; rerun the frontend tests after. Done 2026-10-14 with `npm update` of just these (axios 1.20.0, form-data 4.0.6, moment 2.31.0, react-router(-dom) 7.18.4); `npm audit --omit=dev` finds 0. (`npm audit fix` also moved Vite, Rolldown and ~50 build packages, so it wasn't used.)
- [ ] **P3** Build-time npm advisories in Tailwind CSS 3's file watcher and selector parser: braces / micromatch / fast-glob (stack-exhaustion DoS, high) and postcss-selector-parser (CPU exhaustion, moderate). Dev and build only; nothing ships in the app. The only fix is Tailwind 4, a major upgrade that changes the config and some class names: schedule it as its own change.
- [x] **P3** `WallLayout.test.tsx` "drops back to the pairing screen" failed once in a full frontend run on 2026-10-13 and passed in six reruns. Fixed by waiting for the wall 401 listener before simulating revocation, with a delayed-registration regression in the test.
- [ ] **P3** API image OS packages (`python:3.12-slim`): rebuild on a current base and add `apt-get upgrade -y` (or move to a newer Debian tag). ncurses CVE-2025-69720 (#20, #21, #22, #23); systemd CVE-2026-16742 (#24, #25); libacl1 CVE-2026-54369 (#40); perl-base CVE-2026-9538 (#85); util-linux CVE-2026-76642 (#48, #49, #50, #51, #52, #53, #54, #55, #56), CVE-2026-78408 (#57, #58, #59, #60, #61, #62, #63, #64, #65), CVE-2026-78409 (#66, #67, #68, #69, #70, #71, #72, #73, #74), CVE-2026-78410 (#75, #76, #77, #78, #79, #81, #82, #83, #84). Still open after 1.08's `apt-get upgrade`: Debian has no fix for these yet (P3 since 2026-10-13). Every build upgrades and pulls a fresh base, so Trivy closes them once Debian ships fixes; then tick this line.
- [x] **P2** Web image OS packages (`nginx:alpine`): rebuild on a current tag and add `apk upgrade --no-cache`. pcre2 CVE-2026-103111 (#37), tiff CVE-2026-4775 (#38), libexpat CVE-2026-93990 (#39).

## Review backlog (2026-10-11)

Findings from the codebase review. Each item should be handled with tests first where practical, and can be picked up independently unless noted. Open items are tracked as issues on Forgejo (https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues, labels `backend`/`frontend`/`infra`); each open item below links to its issue.

### Backend security and data correctness
- [x] Require password/elevation for admin self-updates to security-sensitive fields. A PIN-only admin session can currently change its own `password`, then use that password for admin actions (`backend/app/routers/users.py`, `backend/app/services/users.py`). Add a regression test for PIN login + self password/PIN/role update returning 403 `password_required`.
- [x] Harden iCal feed fetching against SSRF. Calendar URLs are fetched server-side with redirects and no host/IP restrictions (`backend/app/integrations/ical_feed.py`, `backend/app/routers/integrations.py`). Restrict schemes, reject private/loopback/link-local/multicast targets after DNS resolution, validate redirect targets, and cover blocked hosts in tests. ([#1](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/1)) Fixed: `backend/app/core/url_safety.py` validates every hop; `fetch_ics_bytes` follows redirects manually (`backend/tests/test_ssrf.py`).
- [x] Delete stale events when a successful iCal sync returns zero events. `sync_source()` only soft-deletes stale events when `incoming_uids` is non-empty (`backend/app/jobs/calendar_sync.py`). Add a test that syncs one event, then an empty feed, and expects the old event hidden. ([#2](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/2)) Fixed: guard removed; `test_empty_feed_hides_previous_events`.
- [x] Treat all-day iCal events without `DTEND` or `DURATION` as one-day events. The parser currently falls back to one hour (`backend/app/integrations/ical_feed.py`). Add parser tests for `DTSTART;VALUE=DATE` with no end. ([#3](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/3)) Fixed: all-day no-end events now end at the next UTC midnight; timed no-end events still default to one hour (`backend/tests/test_ssrf.py`).
- [x] Preserve `all_day` on recurring iCal expansions and avoid duplicating the first occurrence. This overlaps Phase 3; keep it there if fixing it with Phase 3 (`backend/app/integrations/ical_feed.py`). ([#4](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/4)) Fixed: the DTSTART occurrence is no longer re-emitted, every occurrence keeps the series duration and `all_day`, and an all-day series with a UTC `UNTIL` expands (`backend/tests/test_ical_recurrence.py`).
- [x] Decide whether public auth queries must enforce a single-family invariant or explicit family scope. `profiles()`, password login, and PIN login are global today (`backend/app/routers/auth.py`); add multi-family regression tests or document/enforce one-family-per-install at the DB/application boundary. ([#5](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/5)) Decided: one family per install. Migration 006 adds a `families_single_row` trigger, setup turns a lost race into 400, and all three sign-in queries filter by the install family (`backend/tests/test_single_family.py`).
- [x] Reject `provider: "internal"` on calendar source creation. The admin source API can create extra internal sources that are then protected from deletion (`backend/app/routers/calendar.py`, `backend/app/schemas/calendar.py`). ([#6](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/6)) Fixed: the schema accepts only `ical` (`backend/tests/test_calendar_scoping.py`).
- [x] Add `CalendarEvent.family_id == family_id` to event reads, in addition to source family joins, so malformed rows cannot cross tenants (`backend/app/services/calendar.py`, `backend/app/routers/calendar.py`). ([#7](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/7)) Fixed in the event list and single-event lookup (`backend/tests/test_calendar_scoping.py`).

### Frontend wall, auth, and role behavior
- [x] Make the wall 7-day window roll over after midnight. `WallSevenDayStrip` computes `today` once and keeps querying/highlighting the stale range until reload (`frontend/src/wall/WallSevenDayStrip.tsx`). ([#8](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/8)) Fixed: `hooks/useToday.ts` updates after midnight and on visibility change.
- [x] Show timed events on every local day they overlap. `eventDayKeys()` returns only the start day for timed events, so wall views drop events that span midnight (`frontend/src/lib/dates.ts`, `frontend/src/wall/WallSevenDayStrip.tsx`). ([#9](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/9)) Fixed in `eventDayKeys` (`lib/dates.test.ts`).
- [x] Clear wall state and cached wall queries when a paired display receives 401 after revocation. Wall requests intentionally skip the global login redirect, but no wall-specific handler switches the board back to unpaired (`frontend/src/wall/WallLayout.tsx`, `frontend/src/api/client.ts`, `frontend/src/api/wall.ts`). ([#10](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/10)) Fixed: `onWallUnauthorized` in `api/wall.ts`; `WallLayout` clears wall queries and shows the pairing screen.
- [x] Prevent wall WebSocket reconnect timers from surviving unmount/React StrictMode cleanup. Add a stopped flag or remove handlers before closing (`frontend/src/wall/WallSevenDayStrip.tsx`). ([#11](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/11)) Fixed: `wall/useWallWebSocket.ts` stops on cleanup (tested under StrictMode).
- [x] Queue or coalesce concurrent `password_required` prompts. The prompt component stores one pending request, so simultaneous admin requests can orphan the earlier promise (`frontend/src/api/client.ts`, `frontend/src/components/PasswordPrompt.tsx`). ([#12](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/12)) Fixed: concurrent callers share one prompt (`api/client.test.ts`).
- [x] Hide or disable event creation for viewer users and show API error details when create/update fails (`frontend/src/pages/CalendarPage.tsx`). ([#13](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/13)) Fixed: `lib/permissions.ts`; create/delete failures show the API's message.
- [x] Add a frontend admin guard for every `/admin/*` route/page. `CalendarSettings` and `WallDisplays` are directly reachable by non-admin users and can show misleading 403-derived empty states (`frontend/src/App.tsx`, `frontend/src/pages/admin/CalendarSettings.tsx`, `frontend/src/pages/admin/WallDisplays.tsx`). ([#14](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/14)) Fixed: `components/RequireAdmin.tsx` wraps `/admin/*`.
- [x] Add a frontend test runner and cover the high-risk date/auth/wall cases above. Suggested first tests: `lib/dates.ts`, wall midnight rollover, wall revocation handling, password elevation concurrency, and role-gated event creation. ([#15](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/15)) Done: Vitest + jsdom + Testing Library (`npm test`, run in CI); 35 tests in 8 files.

### Infra, deployment, and test coverage
- [x] Restrict GHCR `latest` image publishing to the canonical `master` branch. The GitHub workflow currently runs on both `main` and `master`, but `main` is the retired/divergent v0.29 line (`.github/workflows/build.yml`).
- [x] Upsert `OPENFAMHUB_VERSION` during remote deploy. `scripts/deploy.sh remote` only replaces the line if it already exists, leaving older `.env` files with an unset image tag (`scripts/deploy.sh`, `deploy/compose.yml`). Validate with `docker compose config` before pull.
- [x] Stop caching service worker assets as immutable for one year. Add no-cache rules for `/sw.js`, Workbox files, and the manifest; keep immutable caching for hashed `/assets/*` (`frontend/nginx.conf`).
- [x] Push live wall updates after background and automatic iCal syncs, and only after the change is committed (`queue_event`/`publish_queued`, `backend/tests/test_realtime.py`).
- [x] Close the SSRF DNS-rebinding window: `fetch_ics_bytes` connects to the IP the guard approved (Host header + TLS SNI keep the name) and caps feeds at 10 MB (`TestDnsRebinding`, `TestResponseLimits` in `backend/tests/test_ssrf.py`; see `docs/security-notes.md`).
- [x] Give every CI publish its own image tag and show the running build in `/api/health` plus setup/login/sidebar Help & About, so "what's deployed?" has an answer and rollback can target a build. Shipped first as `<version>.<run>` (e.g. `0.30.17`); since the per-commit numbering change the tag is `0.<n>`.
- [x] Production path: CI deploys only to `test`. Add a `prod` host and a deliberate promotion step once the family uses it daily. Done: `scripts/deploy.sh promote <prod-host> <checked-build>` requires an explicit checked build, rejects `latest`/unsafe tag strings, and delegates to the remote deploy path; docs use the `prod` SSH host alias.
- [x] Code-split the frontend (route-level `React.lazy`). The main bundle is 623 KB (Vite warns at 500 KB) before chores, meals and the rest add pages. Done: main bundle 351 KB; the calendar page is its own chunk.
- [x] Add a production-startup/migration smoke test. Current backend tests create metadata directly and do not exercise Alembic startup or scheduler registration (`backend/tests/conftest.py`, `backend/app/main.py`). ([#16](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/16)) Done: `backend/tests/test_startup.py` boots the app twice against a fresh SQLite file.
- [x] Fix manual backup docs for SQLite WAL mode. The deployment docs copy only `homehub.db`; document online backup, stopping the API first, or copying `homehub.db`, `homehub.db-wal`, and `homehub.db-shm` together (`docs/deployment.md`).
- [x] Run CI on pull requests without pushing images. Add a PR trigger for `master`; gate image publishing to push events (`.github/workflows/build.yml`).

## Cozyla Calendar+ parity (2026-10-11)

Feature audit against Cozyla Calendar+ (CalendarOS). The **NEW** items in Phases 5–10 and the new Phases 11–13 come from this list; `N/A` rows are device/OS-specific and are deliberately not planned.

| Cozyla feature | OpenFamHub |
|---|---|
| Shared calendar, profiles, color tags | ✅ have |
| Day/week/month views | ✅ have (plus agenda) |
| Personal vs family view | NEW, Phase 8 |
| URL iCal import (read-only) | ✅ have; correctness fixes in Phase 3 |
| Two-way sync (Google/Outlook/CalDAV) | NEW, Phase 13 |
| Chores (points, repetition) | Phase 5 |
| Routines + visual timers | NEW, Phase 5 |
| To-do list (one-off tasks) | NEW, Phase 5 |
| Rewards + approval | Phase 6 |
| Family progress widget | NEW, Phase 6 |
| Meal planning | Phase 7 |
| Grocery list from the meal plan | Phase 7 |
| Recipe library (catalog, step-by-step, video) | NEW, Phase 7 |
| Pantry management | NEW, Phase 7 |
| Smart Import (URL → recipe/event) | Phase 7; photo → recipe in Phase 10 |
| Reminders and notifications | NEW, Phase 11 |
| Wellness reminders (hydration, mindfulness) | NEW, Phase 11 |
| Custom widgets, pages, templates, wallpaper | NEW, Phase 8 |
| Photo/video screensaver | NEW, Phase 3b |
| Sleep mode (screen schedule) | NEW, Phase 3b |
| Birthdays | NEW, Phase 8 |
| Companion phone app | ✅ PWA; offline sync in Phase 9 |
| Device syncing | ✅ server-centric |
| Weather and clock | Clock ✅; weather Phase 8 |
| AI voice agent | NEW, Phase 12 (local-first) |
| Smart home hub | NEW, Phase 12 via local Home Assistant |
| Notes (photos/stickers/sketch) | NEW, Phase 12 |
| Parental lock / screen time / app locks | Partial: viewer role limits edits; screen time is OS-level, N/A |
| App store, browser, streaming | N/A (device/OS-specific) |
| Routie kids' device, Voice Lab | N/A (hardware-specific) |

## How to port each domain
- **Backend:** rewrite on our models (`family_id`, `UTCDateTime`, Alembic, cookie auth). v0.29's backend is a spec, not code to copy.
- **Frontend:** v0.29's pages (Chores, Meals, Rewards, Books, Announcements, wall panels; about 3k lines) are reusable UI. Port them with an API adapter: axios `withCredentials`, our routes, 401 → login and 403 → message (v0.29 logs users out on 403), and `lib/dates.ts` for dates.
- **Tests:** v0.29's 65 backend tests are acceptance criteria. Re-express each one against our fixtures before writing the code it covers.

## Phase 2 — Security ✅ (shipped in 0.30)
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

## Phase 3 — iCal correctness ✅ (code complete at 0.82)
- [x] Don't duplicate the first occurrence of recurring events. Fixed in the review backlog ([#4](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/4)).
- [x] Honor EXDATE and RECURRENCE-ID (cancelled or moved instances). Also RDATE and STATUS:CANCELLED; an override keeps the UID of the instance it replaces.
- [x] Keep `all_day` on expanded recurrences. Fixed in the review backlog ([#4](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/4)).
- [x] Store a window only (about 90 days back to 365 days ahead) instead of full history. Series expand inside the window only; synced rows that leave it are deleted, not soft-deleted.
- [x] Look up existing UIDs in one batch query per sync.
- [x] Floating times (no `TZID`, no `Z`) are local wall-clock times: interpret them in the family timezone, not UTC. TZID series also keep their wall time across DST (icalendar's pytz zones are converted to zoneinfo).
- [x] All-day events without `DTEND`/`DURATION` last one day ([#3](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/3)); fixed in the review backlog.
- [x] Keep `all_day` on recurrences and drop the duplicate first occurrence ([#4](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues/4)).
- [x] `add_ical_source` downloads the feed twice (a reachability check, then the sync). Run the sync once and turn a failed first sync into the 400 response.
- Tests first: a recurring event yields each occurrence once; EXDATE removes an instance and RECURRENCE-ID moves one; all-day recurrences stay all-day; floating times land at the family's local time; events outside the window are not stored. Done: `test_ical_phase3.py`, `test_calendar_sync.py`.
- [x] **Family settings page** (admin): change the family name and timezone after setup. Done in Phase 3b: Admin › Settings (also holds the wall sleep schedule).

## Phase 3b — Wall essentials ✅ (code complete at 0.88)
Pulled forward from Phase 10: these are what make the wall worth looking at every day.
- [x] **Photo/video slideshow screensaver.** Family media library: upload from the PWA (admins and members), list, delete; the idle wall screen cycles through it (replaces `WallPhotoPlaceholder`). Store originals and thumbnails under `data/photos` (already mounted and served at `/photos`).
  - Uploads: size limit, image/video MIME allow-list, strip EXIF (location), generate a wall-sized rendition and a thumbnail; `family_id` on every media row (migration 007).
  - The wall reads media through a paired-device endpoint (`/api/wall/media`), never a user session.
  - Done (0.84–0.87): videos are converted by ffmpeg (imageio-ffmpeg's static build) to H.264 MP4 with all metadata removed; photos lose EXIF. Only renditions are stored, never the original (stricter than "store originals": no location data stays on disk). The unauthenticated `/photos` static route is gone; files are served by `/api/media` and `/api/wall/media` only. HEIC/HEIF uploads are accepted as of the follow-up below.
- [x] **Sleep schedule.** Family setting for screen off/on times (separate from the idle timeout); the wall goes dark on schedule and wakes on touch. Evaluated in the family timezone.
- [x] **Off-host backups.** Photos make the data worth more: document (and optionally script) copying `data/backups` and `data/photos` to the NAS, and include photos in the restore steps.
- Tests first: an upload with a disallowed type or size is rejected; EXIF GPS is stripped; another family's media is never listed; the slideshow uses every item before repeating; the sleep schedule respects the family timezone across DST; an unpaired wall can't read media. Done: `test_media.py`, `test_family_settings.py`, `lib/sleep.test.ts`, `lib/shuffle.test.ts`, `WallSlideshow.test.tsx`, `WallLayout.test.tsx`, `scripts/tests/backup-offhost-test.sh`.
- [x] HEIC/HEIF photo uploads (iPhone default). Done: `pillow-heif` registers HEIF support with Pillow; uploads are converted to metadata-free JPEG wall/thumb renditions and covered by `test_heic_is_accepted_and_stored_as_jpeg_renditions`.
- [x] Upload progress for large videos on the Photos page (axios `onUploadProgress`). Done at 1.15: a progress bar shows the file being sent ("2 of 3"), its percent, then "Processing…" while the server converts it. The file picker also offers HEIC/HEIF now.

## Phase 4 — Infra and cleanup ✅ (shipped in 0.30)
- [x] Run Alembic migrations on container start instead of `create_all`.
- [x] CI: set `SECRET_KEY` for tests; add a frontend lint + build job.
- [x] Move CI to Forgejo Actions once a runner exists. Done: `.gitea/workflows/ci.yml` runs on a Gitea Actions runner on the test VM and publishes + deploys on `master` (see [docs/ci.md](docs/ci.md)).
- [x] Fix the Workbox `runtimeCaching` URL patterns (they're matched against the full URL, so they never match).
- [x] `setup-wall-pi.sh`: make it idempotent and Bookworm-compatible (`chromium`, labwc/Wayland autostart).
- [x] Remove dead code and placeholders: `notifications.py`, the `/lists` nav link, the `co_admin` role checks, and `/admin/settings` rendering the Dashboard.
- [x] Deduplicate the event response builders and the user validators.
- [x] `WALL_IDLE_TIMEOUT_SECONDS` drives the wall idle screen. `FAMILY_NAME` stays accepted (an unknown key would break existing `.env` files) but is unused: the name comes from the setup wizard.
- [x] Add tests for users and permissions (`tests/test_phase2.py`).
- [x] Archive `release_checklist.json` and the sprint manifests (`docs/archive/planning/`).
- [x] `.gitignore`: add `file:*` (SQLite shared-cache files) now, before any Phase 5 dev DB.
- [x] Bump to 0.30 and add the CHANGELOG note about the retired 0.19–0.29 line.

## Phases 5–13 — Port the v0.29 feature set and Cozyla parity

`origin/main` carries a `v0.29` tag on a **divergent history** — no merge base with `master`. It is a
parallel product line (chores/rewards/meals), not 11 releases ahead of us. We port its features onto
*our* architecture, one domain at a time, and inherit our auth, `family_id` tenant scoping,
`UTCDateTime`, deploy tooling and CI rather than its code. Phases 11–13 extend past v0.29 with the Cozyla-parity items listed above.

Each phase starts with the issues check from the release plan (its first item), then writes its tests **before** the code, in the same change. Baseline (1): 290 backend tests in 22
files (`v0.29` has 65 in 13) and 174 frontend tests in 31 files (Vitest). Coverage: backend 96% (CI floor 93%), frontend 94% of statements (CI thresholds in `vitest.config.ts`).

Ordering is by dependency: rewards spends the points ledger chores introduced (Phase 5, `points_ledger`), and books awards points.

### Phase 5 — Chores ✅ (code complete at 0.94)
- [x] `chore_templates` and `chore_instances` models + the next Alembic migration (006 = single-family trigger, 007 = media, so chores get 008). `UTCDateTime` throughout, `family_id` on both.
- [x] Recurrence expansion into instances (reuse the Phase 3 iCal recurrence work where it fits).
- [x] Claim / complete lifecycle, quick-add, completion audit log.
- [x] Admin "By User" view: group by assignee with pending and completed counts.
- [x] Per-user completion stats.
- [x] `jobs/chore_generator.py` on the existing scheduler, not a second scheduler. Runs hourly and at startup instead of 06:00: it's idempotent, so each family's day rolls over within the hour in its own timezone, and a server that was down catches up.
- [x] **Fix v0.29 bugs while porting:**
  - Completing a chore never writes to the points ledger (only `points_earned` on the log), so chores earn no points. Credit the ledger in the same transaction, exactly once.
  - `every_N_days` restarts from "today" on each run, so with a daily run every day gets an instance. Anchor the interval to the template's start date.
  - Due dates use the UTC date. Use the family's timezone date.
  - Anyone can claim an *assigned* chore. Only the assignee (or an admin) can.
  - Add a unique (`template_id`, `due_date`) constraint so double generation is impossible.
- [x] **To-do list:** one-off family tasks with an optional assignee and due date; no recurrence and no points side effects. Shown beside chores.
- [x] **Routines:** ordered groups of recurring steps (morning/bedtime) with a visual countdown timer on the wall; built on chore instances. Reminders come from Phase 11.
- Tests first: recurrence expansion across DST; instance generation idempotency; claim/complete role gating; admin view counts; generator does not double-generate; to-do CRUD is family-scoped; routine step order survives edits. Done: `test_chore_schedule.py`, `test_chores_api.py`, `test_todos_routines.py`, `lib/repeat.test.ts`, `lib/routine.test.ts`, `lib/choreActions.test.ts`, `pages/chores/*.test.tsx`, `WallRoutines.test.tsx`.
- Done notes: the points ledger (`points_ledger`, append-only, unique per source) arrived here because completing must credit it; undo writes a reversal. Points go to the assignee, else whoever claimed it. Instances still open after their day are marked missed by the generator.
- [ ] Check off routine steps from the wall. The wall shows routines and the current step's countdown, but steps are ticked in the app: completing from a paired display (no user session) would credit a child's points without anyone signing in, so it needs a decision (e.g. allow it only for routine steps assigned to a child).


### Phase 6 — Rewards ✅ (code complete at 1.12)
- [x] **Before starting:** triaged 2026-10-13: 68 Trivy issues added under Open issues. The P1 python-jose swap and the P2 dependency and base-image fixes shipped in 1.08; tick those lines once the Trivy scan confirms them. check the pinned [Triage report](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues?type=all&state=open&q=Triage+report) issue (or run `python3 scripts/issues.py triage`). Schedule every issue it lists into TODO.md with a priority, and finish open **P0**/**P1** items first.
- [x] Points ledger as an append-only table (no balances stored on the user). Built in Phase 5 (`points_ledger`); rewards, refunds, badge bonuses and admin adjustments are all rows in it.
- [x] Weekly allowance distributor, Mondays 07:00, **idempotent per week**. `jobs/allowance.py` runs hourly and at startup; 07:00 is family-local time (DST-safe).
- [x] Reward catalog with both purchase and request → approve / reject flows. A request holds its points when it's made (so a pending request can't be spent twice); rejecting or cancelling refunds them once.
- [x] Streaks and badge definitions with auto-award. Badges count chores completed, a day streak, or lifetime chore points; they're checked when a chore is completed and when a badge is created or edited. Earned once; retiring a badge keeps earned copies.
- [x] Allowance is stored as integer cents (v0.29 uses strings), with a unique (`user_id`, `week_start`) key. A missed Monday is caught up on the next run (up to 8 weeks). Admins record cash payouts as negative adjustments.
- [x] **Family progress widget:** per-member stars/points on the dashboard and wall, fed by the ledger. It replaces the wall's plain member list.
- Tests first: ledger balances match the sum of entries; allowance re-run for the same week is a no-op; approve/reject adjusts the ledger exactly once; streak rollover at week boundaries; progress widget totals match the ledger. Done: `test_rewards.py` (42), `RewardsPage.test.tsx`, `FamilyProgress.test.tsx`, `lib/money.test.ts`, `lib/badges.test.ts`.
- [ ] Notify an admin when a reward request is waiting (needs Phase 11's notifications).

### Phase 7 — Meals and recipes ✅ (code complete at 1.19)
- [x] **Before starting:** triaged 2026-10-13 (report for build 1.08): no P0/P1 open; the 44 open issues are P3 Debian packages (see Open issues).
- [x] `recipes` with dietary tags, plus text and JSON-LD import. Tags are free lowercase words (JSON-LD `suitableForDiet` maps to e.g. `gluten-free`); an import is a draft the user reviews before saving.
- [x] 7-day meal-plan grid with bulk update. Four slots a day; `PUT /api/meals/plan/week/{monday}` replaces the whole week.
- [x] Shopping list tracking which recipe each item came from, regenerate, weekly reset job. Regenerating never touches bought or hand-added items; the hourly reset archives purchases at the family's Monday.
- [x] Every meals endpoint requires auth and family scope. v0.29's GETs for dietary tags, recipes, plans and the shopping list have **no auth**, and its weekly reset job is never registered.
- [x] Recipe URL import guards against SSRF: http(s) only; block private, loopback and link-local addresses after DNS resolution; size and time limits. `core/safe_fetch.py` (shared with iCal): checked and pinned on every hop, 3 MB, 20 s.
- [x] **Pantry management:** track on-hand ingredients with low-stock and expiry flags; expiry reminders come from Phase 11. Low or expired items go on the shopping list with one button, and list lines hint when the pantry covers them.
- [x] **Recipe library extras:** seed/featured catalog, step-by-step mode, per-recipe video links. 8 built-in recipes (`backend/app/data/recipe_catalog.json`).
- [x] **Smart Import:** URL → event (JSON-LD) alongside URL → recipe; photo → recipe lands in Phase 10 with the OCR work. "Fill from a link" in the calendar's New Event form.
- Tests first: import parsing for both formats; plan overwrite semantics; regenerate is idempotent; reset does not delete completed purchases; pantry flags and expiry; URL → event parsing. Done: `test_meals.py`, `test_smart_import.py`, `MealsPage.test.tsx`, `CalendarPage.test.tsx`, `lib/meals.test.ts`, `lib/dates.test.ts`.
- [x] Scale a recipe's ingredients by servings (quantities are free text today). Done at 1.25: ± servings (or ½×–3× when servings are unknown) scales the number at the start of each line (`lib/scale.ts`: fractions, mixed numbers, ½, ranges).

### Phase 8 — Books, announcements, weather ✅ (code complete at 1.24)
- [x] **Before starting:** triaged 2026-10-13: nothing new; every open issue is a P3 Debian package (see Open issues).
- [x] Books: personal lists, shared family library, status transitions, 50-point award on completion (writes to the Phase 6 ledger). Once per book and reader, ever.
- [x] Announcements: free text with pin/unpin. On the dashboard; the author or an admin edits, pins or removes.
- [x] Weather: Open-Meteo, no API key, cached ~10 minutes server-side. WMO code → emoji mapping. Location is a family setting (picked by searching a town under Admin › Settings).
- [x] Shared family library: implement `POST/PATCH/DELETE /books/shared…`. Done as library books (owner_id null) on `/api/books`. v0.29's UI calls these, but its backend only has `GET /books/shared`.
- [x] Dashboard: one `GET /api/dashboard/summary` (today's events, chore stats, points, allowance, this week's meals). v0.29's dashboard calls four `/api/dashboard/*` routes that don't exist.
- [x] **Birthdays:** per-member birthday with the next age shown; dashboard/wall card and all-day calendar entries. Calendar entries are computed (read-only), not stored.
- [x] **Dashboard customization:** widget grid (drag/resize), multiple pages, page templates, wallpaper, and a personal vs family filter for dashboard and calendar. Resize is normal or wide (two columns); saved per person in `/api/users/me/preferences`.
- [x] **Navigation layout:** let each person choose the menu across the top or down the side (requested 2026-10-13). Save it per user, keep the phone layout as it is, and test that the choice survives a reload.
- Tests first (done: `test_books_announcements.py`, `test_weather_dashboard.py`, `Dashboard.test.tsx`, `CustomizeDashboard.test.tsx`, `BooksPage.test.tsx`, `MySettings.test.tsx`, `NavShell.test.tsx`): cross-family isolation on the shared library; point award fires once; cache hit within the window; WMO mapping table has no unmapped codes; birthday age crosses the year boundary; layout persistence; filter scoping.

- [x] Members can't change their own name, color or avatar outside Admin › Users; add them to My settings. Done: a **Me** section at the top of My settings (`PATCH /users/{id}` already allowed your own profile; `test_users_api.py`, `MySettings.test.tsx`). The avatar list is shared in `lib/avatars.ts`.
- [ ] Weather and announcements panels on the wall come with Phase 10's wall panels.

### Phase 9 — Offline sync ✅ (code complete at 1.28)
- [x] **Before starting:** triaged 2026-10-13: no new P0/P1; every open issue is P3.
- [x] Add the frontend test runner and its first tests. Done early, in the review backlog (#15).
- [x] IndexedDB write queue in `frontend/src/lib/idb.ts`. Covers ticking and claiming chores, ticking and adding shopping items, and adding and ticking to-dos; each write's id is its Idempotency-Key (backend `core/idempotency.py`).
- [x] Sync orchestrator replaying the queue on reconnect and on tab visibility (`lib/offline.ts`, `hooks/useOfflineSync.ts`; also every minute while anything waits).
- [x] Conflict resolution modal: 409 detection, keep-local / keep-server / merge. Edits carry `base` (the item as last seen); `core/conflicts.check_base` answers 409 if it changed.
- [x] Offline banner and sync indicator (`OfflineStatus.tsx`). The service worker keeps the last copy of sign-in and those lists so the app opens offline; logout clears it.
- Tests first: queue survives a reload; replay is all-or-nothing per operation; a 409 surfaces the conflict modal rather than silently overwriting; a failed replay leaves the item queued. Done: `lib/offline.test.ts`, `OfflineStatus.test.tsx`, `lib/swCaching.test.ts`, `test_offline.py`.
- [x] Offline support for more writes (meal plan, pantry, announcements) if the family wants it; each needs a `base` check on its PATCH. Decided 2026-10-13: **meal plan only**; pantry and announcements stay online. Done: setting and clearing a slot queue with the slot as last seen (`_check_slot_base`; `test_offline.py::TestMealPlanOffline`, `api/meals.offline.test.tsx`), and the plan and recipes open offline.
- Note: the v0.29 version of this is broken — its `useOfflineMutations` hook is never called and its replay `fetch` sends no credentials, so every replay 401s. Design against the tests above, not against that code.

### Phase 10 — OCR and wall panels
- [x] **Before starting:** triaged 2026-10-13 (report for build 1.30): issues and TODO.md agree; no P0/P1; the 44 open issues are P3 Debian packages.
- [x] `ScanListModal` with `tesseract.js`: capture, OCR, preview, edit, then add to the shopping list. Done: **Scan a list** on the Shopping list; OCR runs on the device with assets served from `/ocr/` (no CDN); headings and debris skipped, items already on the list unticked (`lib/ocr.ts`, `lib/ocrLines.ts`, `ScanListModal.tsx`).
- [x] Wall cycling panel mode with a live countdown. Done: `WallCycle.tsx` rotates focused Calendar, Routines and Progress panels with a visible “Next in …” countdown, using `wallCycle.ts`; covered by `WallCycle.test.tsx`, `wallCycle.test.ts`, and `WallLayout.test.tsx`.
- [x] Read-only wall endpoints (`/api/wall/chores`, `/meals`, `/announcements`, `/weather`) behind the paired-device cookie. v0.29's panels need a family member's login. Done: `routers/wall_panels.py` (GET only, `get_wall_device`); `test_wall_panels.py` covers unpaired, revoked and member-cookie 401s, read-only 405s, and each panel's data.
- [x] The wall timezone is a family setting edited by an admin. v0.29 lets the wall itself write it via an admin-only call. Done: the family timezone (Admin › Settings, admin-only `PATCH /api/family`) reaches the wall in its session; a display can't change it (`test_wall_panels.py`). Fixed on the way: `WallClock` showed the display's own zone; it now uses the family's (`WallClock.test.tsx`).
- [x] `DateTimeWallPanel` with a timezone picker; reuse `frontend/src/lib/dates.ts` and the wall token flow. Decided 2026-10-14: **extra clocks**, not a panel, since the wall clock already shows the family's date and time. Done: Admin › Settings › Other clocks on the wall (label + timezone picker, up to 3, `settings_json.clocks`), sent in the wall session and shown under the clock, with the weekday when it isn't the family's day (`test_family_settings.py::TestExtraClocks`, `WallClock.test.tsx`, `FamilySettings.test.tsx`).
- Photo slideshow and sleep schedule moved to Phase 3b.
- [x] **Smart Import (photo → recipe):** reuse the OCR pipeline. Done: Import › "Or read a photo of it" fills the paste box with the OCR'd text, wrapped steps joined (`lib/ocrRecipe.ts`), for checking before the usual recipe reader.
- Tests first: OCR line parsing and classification against sample images; cycling-mode panel order and auto-advance; the wall panel renders only for a paired device. OCR done: `ocrLines.test.ts`, `ocrRecipe.test.ts`, `ocr.test.ts`, `ocr.real.test.ts` (real engine on `src/test/fixtures/ocr-*.png`), `ScanList.test.tsx`; also checked in headless Chromium loading only from `/ocr/`.

### Phase 11 — Notifications and reminders
- [ ] **Before starting:** check the pinned [Triage report](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues?type=all&state=open&q=Triage+report) issue (or run `python3 scripts/issues.py triage`). Schedule every issue it lists into TODO.md with a priority, and finish open **P0**/**P1** items first.
- [ ] Reminder engine on the existing scheduler: events, chores, to-dos, birthdays, pantry expiry, allowance payouts.
- [ ] Channels: Web Push (PWA), ntfy, and SMTP email, with per-user preferences.
- [ ] Quiet hours aware of the Phase 3b sleep schedule.
- [ ] Optional wellness reminders per user (hydration, mindfulness).
- Tests first: a reminder fires exactly once; quiet hours suppress delivery; per-user channel preference; timezone/DST correctness.

### Phase 12 — Home Assistant, AI, and notes
- [ ] **Before starting:** check the pinned [Triage report](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues?type=all&state=open&q=Triage+report) issue (or run `python3 scripts/issues.py triage`). Schedule every issue it lists into TODO.md with a priority, and finish open **P0**/**P1** items first.
- [ ] Home Assistant local integration: long-lived token, chosen entities as cards on the dashboard and wall, optional scene triggers from routines; degrades gracefully when HA is unreachable.
- [ ] Smart-home widgets for those entities (climate, lights, sensors).
- [ ] AI voice agent, local-first (local STT + LLM; cloud optional and opt-in): add/edit events, chores and to-dos conversationally.
- [ ] Notes: family note board with photos, stickers and sketching; export as an image; wall panel.
- Tests first: HA outage degrades gracefully; voice intent parsing fixtures for add/edit; notes render and export.

### Phase 13 — Two-way calendar sync
- [ ] **Before starting:** check the pinned [Triage report](https://forgejo.vernonmyers.cloud/vernon/OpenFamHub/issues?type=all&state=open&q=Triage+report) issue (or run `python3 scripts/issues.py triage`). Schedule every issue it lists into TODO.md with a priority, and finish open **P0**/**P1** items first.
- [x] **Edit calendar feeds** (requested 2026-10-13; small, can be pulled forward any time). Admin › Calendars gets an Edit form for a feed's name, color, URL, sync interval and on/off. The API already has `PATCH /api/calendar/sources/{id}`, but a changed URL isn't treated like a new one: make it accept `webcal://`, test-fetch the feed (400 if it fails, like adding one) and re-sync it right away so old events from the previous URL are replaced. Tests first: a rename/recolor shows on existing events; a bad URL is refused and the old one kept; a new URL replaces the old feed's events. Done: **Edit** on each calendar in Admin › Calendars; the PATCH test-fetches a changed link in a savepoint (`test_calendar_routes.py::TestEditingFeeds`, `CalendarSettings.test.tsx`).
- [ ] Google Calendar two-way sync: OAuth, incremental sync tokens, write-back of local edits, delete propagation.
- [ ] Outlook/Microsoft Graph two-way sync.
- [ ] CalDAV two-way sync (Apple Calendar, Nextcloud), including discovery.
- [ ] Per-account conflict policy with an audit trail; URL feeds stay read-only; source-mapping UI (direction per calendar, member mapping).
- Tests first: incremental sync is idempotent; a local edit propagates exactly once; a remote delete propagates; the conflict policy holds; a revoked token surfaces in the UI.

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
- [x] Its committed SQLite WAL (`backend/file:memdb1-wal`, 4.1 MB) contains a bcrypt hash. `.gitignore` already covers `*.db`, `*.db-wal` and `*.db-shm`, but SQLite shared-cache names (`file:memdb1-wal`) slip past them — add a pattern before Phase 5 opens a dev DB.

### Version numbering
- The merged line continued at **0.30** (see Decisions). Our 0.18 keeps its CHANGELOG entry; the 0.30 entry notes that 0.19–0.29 (and v0.29's own "0.18") belong to the retired `main` line.
- Since 2026-10-12 every commit is its own build: the `pre-commit` hook bumps `VERSION` by one and the release name comes from `scripts/release-name`: `0.<n>` up to 0.99, then 1, 1.01 … 1.99, 2 (decided 2026-10-13; build 100 is 1, not 0.100). Build numbers say *which code is deployed*; phases say *what is planned*. Don't label a phase with a future number. When a phase ships, record its build in the release plan and title its CHANGELOG entry `[<release>] - <date> — Phase N`.

## Completed
- [x] v0.30: Phases 2 and 4 (sign-in picker + PIN with admin password gate, server-side sessions, lockout, event permissions, migrations at startup, CI, cleanup). See CHANGELOG.
- [x] v0.18: the Phase 1 fixes (routing, login errors, time zones, range queries, Sync Now, source delete, source filter, wall pairing, deploy script). See CHANGELOG.
# Build 105
