## [Unreleased]

### Added
- **Event details:** tap an event on Home or in the Calendar to see when and where it is (the place opens in your maps app), its notes with clickable links, its link, organizer and attendees (from calendar feeds), and who added it. Home and the wall now show each event's location. New events can carry a link.
- **This week on Home:** a new card lists the events for today and the next six days, day by day. Add it with Customize; it's on the default page and the Parents template.
- **Richer Smart home card** (Phase 12): dim lights with a slider, switch a thermostat between its modes (heat, cool, off…), and see a 24-hour trend line with the low and high under each numeric sensor, on Home and the wall.
- **Home Assistant** (Phase 12): set `HA_URL` and `HA_TOKEN` (a long-lived access token) in `.env`, then pick entities under **Admin › Settings › Home Assistant**. They show on a new **Smart home** card on Home and the wall: members and parents can switch lights, run scenes and scripts and nudge the thermostat; viewers and the wall only look. A timed routine can start a scene or script at its start time. If Home Assistant is down the card says so.
- **Notifications on your phone** (Phase 11): turn them on in **My settings › Notifications** and choose reminders before events (events you added, or all family events; off until you choose), a morning list of your chores and to-dos, and, for parents, reward requests waiting for a yes. Nothing is sent during the wall's sleep hours. They use Web Push, with no account to set up; on iPhone and iPad, add OpenFamHub to the Home Screen first (iOS 16.4+).
- **Wellness reminders** (Phase 11): in **My settings › Notifications › Wellness**, anyone can turn on drink-water reminders (every 1 to 3 hours between two times) and a daily breathing pause. Off until you turn them on; they go to your devices and ntfy, never by email.
- **Chores up for grabs on Home:** a new dashboard card lists today's family chores anyone can claim, with a **Claim** button (not for viewers). It's on the default page and the Kids template; add it to your own pages with Customize.
- **Reminders by ntfy and email** (Phase 11): when the server has an ntfy server (`NTFY_URL`) or an SMTP account (`SMTP_*`) set up, each person can add their own ntfy topic (**Make one** suggests a hard-to-guess topic) and/or email address in **My settings › Notifications**. Reminders go to every channel they set up, with or without a phone; **Send a test** checks them all.
- **More reminders** (Phase 11): the morning before someone's birthday (everyone but them), pantry food reaching its use-by date today or tomorrow (one list, members and parents), and a note when your weekly allowance is paid. Each has its own switch in **My settings › Notifications**, on by default; birthdays and pantry come at your morning list time.
- **A wall dashboard the family arranges (#87):** the wall shows pages of cards (today's events, chores, routines, meals, weather, announcements, family progress, birthdays) that turn every so often. Anyone signed in can change the pages, cards, sizes and timing from the Dashboard; every wall follows the same layout.
- **Tick off routine steps on the wall:** the current step has a **Done** button. It counts for whoever the routine is assigned to, so kids can work through their morning routine at the wall without signing in. Undo stays in the app.
- **The time is always on the wall:** a header bar shows the family's time and date, with any extra clocks, above every page. A **Clock** card puts a big clock on a page too.

### Fixed
- **Menu position is easy to find again:** "Down the side" or "Across the top" is back near the top of My settings (it had ended up below the long Notifications section) and is also in Home › Customize.
- **Offline banner:** after resolving one offline change, a background sync finishing late could bring back a change that was just discarded ("1 needs a decision") until the next refresh. Only the latest refresh of the waiting list now updates the screen.
- **CI:** the wall's sleep-schedule test touched the black screen before the wall was listening for touches, so on a slow runner the touch was lost and the test failed (build 1.55). It now keeps touching until the screen wakes.
- **CI:** a test compared preferences without the new notification settings, and two frontend tests depended on how fast a cold runner compiles lazy-loaded pages; both fixed.
- The wall redrew every card on the page each second to tick its countdown, heavy on a Raspberry Pi; now only the countdown does.
- The Routines card was blank when no routine was on; it says "No routine right now."

### Developers
- New Python packages `http-ece` 1.2.1 and `py-vapid` 1.9.4 for Web Push (they need only `cryptography`; `pywebpush` would add `aiohttp` and `requests`). Migration 012. The API needs HTTPS egress to the browsers' push services (see deployment.md).
- The README has a Raspberry Pi wall setup section and an up-to-date feature list.

---

## [1.41] - 2026-10-14 — Phase 10

Reading photos (shopping lists and recipes), the wall's cycling panels and extra clocks, plus everything from builds 1.29 to 1.41: editing calendar feeds, editing your own profile, the meal plan offline, and security and offline fixes. Release notes and upgrade steps: [docs/releases/v1.41.md](docs/releases/v1.41.md).

### Added
- **Other clocks on the wall:** in Admin › Settings, add up to three more clocks (say, "Grandma" in London). The wall shows them under its clock, with the day when it's already tomorrow (or still yesterday) there.
- **The wall cycles its right side** between the week's calendar, routines, and family progress with birthdays, 20 seconds each, with a countdown to the next. Routines is skipped when none is on.
- **Scan a list** on the Shopping list: take a photo of a paper list and its items appear, with quantities, ready to check and add. Headings and smudges are skipped, and things already on the list start unticked. The photo is read on your phone and never uploaded; the reader is served by OpenFamHub itself, so it works without internet and, after the first scan, offline.
- **Recipe from a photo:** in Recipes › Import, "Or read a photo of it" turns a photo of a recipe card or cookbook page into text to check, then reads it like pasted text.
- **The meal plan works offline:** plan or clear a meal without a connection and it syncs when you're back; if someone else changed that meal meanwhile, you choose whose to keep. The week and your recipes open offline too.
- **Edit calendar feeds** in **Admin › Calendars**: rename, recolor, change the sync interval, pause, or paste a new link. A new link (`webcal://` works) is checked before it's saved and its events replace the old ones; one that doesn't work is refused with the reason and nothing changes. Walls repaint with the new name and color straight away.
- **Change your own name, color and avatar** under **My settings › Me**, without an admin. The new look shows straight away across the app; a name someone else in the family already has is refused.

### Security
- Frontend dependencies updated for published advisories: axios 1.20.0 (prototype pollution), react-router 7.18.4 (open redirect, XSS), form-data 4.0.6 (CRLF injection) and moment 2.31.0 (path traversal). `npm audit` now finds nothing in what the app ships.

### Fixed
- **Wall clock:** the time and date on the wall (and over the slideshow) now follow the family's timezone, like the rest of the wall, instead of the display's own setting. A Pi left on UTC showed the wrong time.
- **Offline conflicts:** choosing "Keep mine" or "Merge" now goes through. Before, the resolved change was re-sent with the same Idempotency-Key, so the server answered with the remembered 409 every time and the change stayed stuck.
- **Rewards:** two redeems at the same moment (say, from two devices) can no longer spend more points than someone has; the later one is refused.

### Developers
- Paired walls can read today's chores (`/api/wall/chores`), the week's meals (`/api/wall/meals`), announcements (`/api/wall/announcements`) and the weather (`/api/wall/weather`) with their display cookie, read-only. The wall panels that use them come next.
- New dependencies `tesseract.js` 7.0.0 and `@tesseract.js-data/eng` 1.0.0 (run `npm install`). `npm run dev` and `npm run build` copy the OCR engine into `frontend/public/ocr/` first (`scripts/ocr-assets.mjs`; not committed). The web image is about 15 MB larger.
- Frontend work needs Node 24 (or 22.22+); Node 20 can't run the tests (jsdom 30, Vitest 5). `frontend/.nvmrc` pins 24 and `package.json` declares `engines`. The web image builds on `node:24-alpine`.

---

## [1.28] - 2026-10-14 — Phases 6–9

Rewards, meals, family info with your own layout, and offline sync: everything from builds 1.02 to 1.28, grouped by phase. Closes the 24 Trivy issues fixed in 1.08: #17, #18, #19, #26, #27, #28, #29, #30, #31, #32, #33, #34, #35, #36, #37, #38, #39, #41, #42, #43, #44, #45, #46, #47. Release notes and upgrade steps: [docs/releases/v1.28.md](docs/releases/v1.28.md).

### Phase 9: Offline (builds 1.26–1.28)

#### Added
- **Works offline:** ticking and claiming chores, ticking and adding shopping items, and adding and ticking to-dos all work without a connection. The change shows at once and syncs when you're back, even if you closed the app in between.
- **Offline banner and sync indicator:** "You're offline", "2 changes waiting", "Syncing…".
- **Conflict choices:** if someone changed the same item while you were offline, you choose: keep mine, keep theirs, or merge (each person's change where they don't overlap).
- **Opens offline:** the app starts without a connection and shows the last copy of your chores, to-dos, shopping list and Home.
- **No duplicates:** replayed changes are never applied twice, even if the first reply was lost (Idempotency-Key).

#### Developers
- `npm install` after pulling: adds `fake-indexeddb` (dev only).

### Recipes (build 1.25)
- Scale a recipe: change the servings (or pick ½×, 2×, 3× when it doesn't say) and the amounts at the start of each ingredient line follow, written as kitchen fractions.

### Phase 8: Family info and your own layout (builds 1.20–1.24)

#### Added
- **Books** (`/books`): everyone's reading lists and a family library. Finishing a book earns its reader 50 points, once per book.
- **Announcements** on the dashboard: post, pin and remove.
- **Weather** from Open-Meteo (no API key, cached 10 minutes). Pick your town under Admin › Settings.
- **Birthdays**: they show on the calendar, the dashboard and the wall, with the age the person is turning. Admins set them under Users, and members set their own in My settings.
- **Home** gets a one-call summary: today's events, "My day", today's meals, birthdays and announcements.
- **Your own layout**, saved to your account and the same on every device:
  - Dashboard pages built from templates, with cards you add, remove, drag into place and make wide.
  - A gradient or a family photo as the Home wallpaper.
  - The menu across the top or down the side.
  - "Everyone" or "Just me" on the calendar and Home.
  - All of it under **My settings** (tap your avatar).
- On phones the bottom bar shows four items and the rest are under **More**.
- Migration 011: `books`, `announcements`, `users.birthday`.

### Phase 7: Meals (builds 1.17–1.19)

#### Added
- **Meals page** (`/meals`):
  - **This week:** a weekly plan with breakfast, lunch, dinner and snack. Pick a recipe or type something.
  - **Recipes:** search and tag filters, a "Cook step by step" mode, and video links.
  - **Shopping list:** built from the plan, with each line labelled with its recipe.
  - **Pantry:** low-stock and use-by flags.
- **Recipe import** from a link or pasted text, using the page's schema.org data. You review the recipe before it's saved. There are also 8 built-in recipe ideas to start from.
- **Fill from a link** in the calendar's New Event form, for school, club and ticket pages.
- The shopping list resets itself each Monday: bought items move to a purchase history, and unbought lines from past weeks' meals go away. Items you added yourself stay.
- Migration 010: `recipes`, `meal_plan_entries`, `shopping_items`, `pantry_items`.

#### Security
- Every meals endpoint needs a signed-in family member (v0.29's didn't). Links are fetched through `core/safe_fetch.py`, the SSRF-safe fetcher now shared with calendar feeds.

### Phase 6: Rewards (builds 1.10–1.12)

#### Added
- **Rewards page** (`/rewards`). Members spend points on rewards. A reward can be instant, or need a yes from an admin; a request takes the points straight away, and rejecting or cancelling it gives them back. Admins edit and retire rewards and badges, and give or take points with a reason.
- **Badges** for chores completed, day streaks or lifetime chore points, with optional bonus points. They're awarded automatically, once per person, including to anyone who already qualifies when a badge is created.
- **Weekly allowance** in whole cents. It's paid Monday 07:00 family time, once per week, and catches up after downtime (up to 8 weeks). Admins set each amount and record cash they hand over.
- **Family progress** on the dashboard and the wall: each member's points, points earned this week, streak and badges. On the wall it replaces the plain member list and updates live.
- Migration 009: `rewards`, `reward_redemptions`, `badge_definitions`, `user_badges`, `allowance_plans`, `allowance_ledger`.

### Photos (build 1.15)
- The Photos page shows upload progress: which file is being sent ("2 of 3"), how much of it, then "Processing…" while the server converts it.
- The file picker now offers HEIC/HEIF photos, which the server has accepted since 1.05.

### Security (build 1.08)
- Replaced `python-jose` with PyJWT (CVE-2026-85394, and drops its `ecdsa` dependency). Existing sign-ins stay valid.
- Bumped FastAPI (Starlette 1.8), python-multipart and Pillow, and both images now install OS security updates at build time; `deploy.sh publish` pulls fresh base images. This targets the 67 other Trivy findings.

### Added
- Production promotion path: `scripts/deploy.sh promote <prod-host> <checked-build>` deploys a deliberately selected, already-checked build to the production SSH host, and docs now keep CI's automatic deploy scoped to `test`.
- HEIC/HEIF photo uploads: iPhone default photos now upload and are converted to metadata-free JPEG wall/thumb renditions.

### Fixed
- CI deploy now passes the exact release computed by the `version` job into publish/deploy/Trivy, preventing the test VM from staying on an older `OPENFAMHUB_VERSION` after a newer build publishes.

---

## [1.01] - 2026-10-13

The first 1.x build, and the first release since 0.30: everything from builds 0.31 to 1.01, grouped by phase. Release notes and upgrade steps: [docs/releases/v1.01.md](docs/releases/v1.01.md).

### Build fix (1.01)

#### Fixed
- Build 1 didn't publish: an edit dropped the executable bit from `scripts/deploy.sh`, so CI's `publish` step failed with "Permission denied". Every script under `scripts/` and `.githooks/` is executable again, and the new `scripts/tests/exec-bits-test.sh` (run in the `version` job, before `publish`) fails the build if one loses it. Build 1 has no images or tag; 1.01 is the first 1.x build published.

> Entries are keyed by roadmap phase or work batch, not by commit. Every commit is its own build (`VERSION` in the repo root; named by `scripts/release-name`: 0.99, then 1, 1.01 …). New work goes under `[Unreleased]`; a release gives the batch the build that shipped it (`[<release>] - <date>`). The phases below are code complete and pass CI; TODO.md records each one's build once it's checked on the `test` VM.

### Release names past 0.99 (builds 1–1.01)

#### Changed
- **Release names after 0.99**: build 100 is **1**, not 0.100, followed by 1.01, 1.02 … 1.99, then 2, 2.01. Builds below 100 keep their names (0.5, 0.99), so no published tag or image changes. Tags follow the name (`v1`, `v1.01`). The rule lives in `scripts/release-name`, which the pre-commit hook (README badge), `renumber`, `deploy.sh`, the Trivy scan and CI use; the backend (`/api/health`, Help & About) and `scripts/issues.py` mirror it.
- TODO.md: every phase from 6 on starts with a "Before starting" item to check the Triage report issue.

### Release process: issues and TODO.md (builds 0.98–0.99)

#### Added
- **Issues close when their work is done**: when every TODO.md line naming an issue is ticked, the new `issues` CI job closes it after the build deploys to `test`, with a comment naming the build. `Fixes #N` in a commit message works too.
- **Trivy issues close themselves** once a scan of a newer build no longer finds the vulnerability.
- **Triage against TODO.md**: `scripts/issues.py triage` ranks open issues by priority (P0–P3, from TODO.md, else a `priority/…` label or the Trivy severity) and lists issues TODO.md doesn't mention, done-but-open issues, closed issues still unticked, and priority mismatches. `--strict` makes it a release gate. The CI job prints the report on every build.
- **Pinned Triage report issue**: the `issues` job writes the triage report to a pinned "Triage report" issue on every build and comments on it when new items need attention, so Forgejo notifies you without anyone reading CI logs.
- `docs/releasing.md`: the release steps, and the rules for keeping issues and TODO.md in step. TODO.md has a new **Open issues** section for issues not yet scheduled into a phase.

#### Changed
- The issue token secret is now `ISSUES_TOKEN`; `TRIVY_ISSUE_TOKEN` still works.

### CI: Trivy image scan (builds 0.96–0.97)

#### Added
- **Trivy scan in CI**: after each publish to `master`, the new `trivy` job scans the exact `openfamhub-api` and `openfamhub-web` images just pushed, prints a HIGH/CRITICAL table in the log and keeps the JSON reports as a CI artifact for 30 days. It never fails the pipeline or delays the deploy.
- **Backlog issues from findings** (optional): with the `TRIVY_ISSUE_TOKEN` secret set, each HIGH/CRITICAL finding gets one Forgejo issue. Findings already tracked, including closed issues, aren't opened again, and at most 20 are opened per run.
- `scripts/trivy-scan.sh` to scan any published build by hand, and `scripts/tests/trivy-test.sh` covering both scripts.

#### Fixed (in 0.96's first version of the job)
- The issue step would have crashed (`${secrets…}` isn't shell syntax), and it put the token on the command line; the token now comes from the environment.
- The step condition read `secrets` in `if:`, which isn't allowed there.
- The scan always checked `latest` instead of the build that was just published.
- Every push would have reopened an issue for every finding; issues are now deduplicated against existing ones.
- API calls had no timeout, and a report with `"Vulnerabilities": null` crashed the script.

#### Security
- The scanner runs from a pinned `aquasec/trivy:0.69.3` image instead of `aquasecurity/trivy-action`, whose tags (and Trivy 0.69.4) were hijacked in March 2026 (CVE-2026-33634).

### Phase 5: chores, routines and to-dos (builds 0.90–0.94)

#### Added
- **Chores**: admins set up chores that repeat every few days, on chosen weekdays or monthly, either assigned to someone or up for grabs. Family members see today's chores, claim open ones, mark them done (or undo) and earn points.
- **Points**: every completed chore adds to a points balance kept in an append-only ledger, ready for rewards. Each person sees their points, streak and week; everyone sees the family table.
- **Routines**: ordered steps such as a morning or bedtime routine, each with a few minutes; the wall shows the current step with a countdown.
- **To-dos**: a shared list of one-off tasks with an optional person and due date.
- Admins see today's chores counted by person, and a history of who did what.

#### Fixed (compared with the retired 0.29 line)
- Chores earn points: they're credited exactly once when completed.
- "Every 3 days" chores stay every 3 days instead of appearing daily.
- Due dates follow the family's timezone, not UTC.
- Only the person a chore is assigned to (or an admin) can claim it.
- The same chore can't be created twice for one day.

### Phase 3b: wall essentials (builds 0.84–0.88)

#### Added
- **Photos & videos**: family members add photos and videos on the new Photos page, and the wall shows them full screen when it's idle, each one before any repeats. Photos lose their location data and are resized for the wall; videos are converted so a Raspberry Pi plays them smoothly, with all their metadata removed. The original upload isn't kept.
- **Sleep schedule**: wall screens can go dark overnight, at times set in the family's timezone; a touch lights them for a few minutes.
- **Family settings** (Admin › Settings): change the family name, timezone and sleep schedule after setup.
- **Off-host backups**: `backup-offhost.sh` copies the daily database snapshots and the photos to a NAS or another disk, and the restore steps now include photos.

#### Security
- The family's photo folder was readable without signing in at `/photos/…`. That route is gone: photos and videos are served only to signed-in family members and paired wall displays.

#### Changed
- The API image is about 70 MB larger (ffmpeg and Pillow).

### Phase 3: iCal correctness (builds 0.75–0.82)

#### Fixed
- Subscribed calendars honour cancelled and moved instances of repeating events (EXDATE, RECURRENCE-ID, and cancelled events), and extra dates (RDATE). A moved instance no longer appears twice.
- Repeating events keep their local time across daylight-saving changes (a 9:00 meeting stays at 9:00 in November).
- Times without a timezone in a feed are read in the family's timezone instead of UTC. New installs default the family timezone to the device's zone (it used to default to UTC) and can pick any zone.
- Adding a calendar downloads it once and refuses it, with the reason, if the first sync fails (for example a URL that returns a login page).
- Editing a calendar source through the API no longer fails with a server error.
- If the password prompt is closed unexpectedly, later admin actions no longer hang.

#### Changed
- Only events from 90 days ago to a year ahead are stored for subscribed calendars; long-running series no longer generate every instance since they began, and each sync looks up existing events in one query.

#### Added
- Test coverage: backend 96% and frontend 93% of statements, measured in CI, which now fails below set thresholds. New tests cover backups, sign-in, the calendar and admin pages, wall pairing and app boot.

### Review fixes (builds 0.31–0.73)

#### Changed
- Every commit now carries its own version, `0.<n>`, incremented by one per commit by a `pre-commit` hook and enforced in CI. The CI run-number suffix (`0.30.17`) is gone; images are tagged `0.<n>` with a matching `v0.<n>` release tag.
- Pages load on demand, so the first download is about 45% smaller (351 KB, down from 626 KB).

#### Fixed
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

#### Added
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
