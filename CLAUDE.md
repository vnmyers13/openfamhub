# CLAUDE.md

OpenFamHub: a self-hosted family calendar and organizer (a home version of a Skylight-style wall calendar). FastAPI + SQLite backend, React frontend, Docker/Caddy deployment, Raspberry Pi wall display. Current version: the integer in `VERSION` (repo root); its release name comes from `scripts/release-name`: `0.<n>` below 100, then 1, 1.01 … 1.99, 2, 2.01 (two digits after the dot, none on a round hundred).

Read these before changing code:

- [AGENTS.md](AGENTS.md): layout, commands, gotchas
- [docs/architecture.md](docs/architecture.md): how the app works, including time handling and auth
- [TODO.md](TODO.md): **the source of truth** for the roadmap and the task list
- [docs/deployment.md](docs/deployment.md): publish and deploy
- [docs/releasing.md](docs/releasing.md): releasing a phase, and keeping Forgejo issues in step with TODO.md

## Which code is canonical

- **`master` is the product.** Feature work branches from it. CI publishes every `master` push as its own per-commit build (`<release>`, named from the integer in `VERSION`) and deploys it to the `test` VM (see docs/ci.md).
- **`origin/main` (tagged v0.29) is a different codebase with no shared history.** Use it only as a reference for features to port (Phases 5–10). Never merge, rebase onto or cherry-pick from it. Re-implement each feature on our architecture: our auth, `family_id` scoping, `UTCDateTime`, Alembic migrations, deploy tooling and CI.
- **Remotes:** `forgejo` (`http://192.168.10.2:3002/vernon/OpenFamHub.git`, primary; CI runs here) and `origin` (GitHub). Mirrors at `192.168.10.101:3002` and `192.168.10.102:3002` (same path). Push to the primary first, then GitHub and the mirrors. After rebasing onto a moved `master`, run `scripts/renumber origin/master`.

## Rules

- **Issues:** every open Forgejo issue appears in TODO.md with a priority (**P0**–**P3**); TODO.md decides the order of work. Each phase's first TODO item is the issues check: before any other work in a phase, get the Triage report, schedule what it lists (open P0/P1 items come first) and tick that item. When you finish an item, tick its TODO line, which names the issue as `#N` or its link; CI closes the issue once the build deploys. Claude sessions can't reach Forgejo, so ask Vern to paste the pinned **Triage report** issue (CI refreshes it on every build).

- **Tests first.** Each TODO phase lists its test targets; write them before the code, in the same change. Baseline is 392 backend tests in 27 files and 252 frontend tests in 43 files (build 1.24); coverage is 96% backend (CI fails below 93%) and 94% frontend statements (thresholds in `vitest.config.ts`). Don't lower a threshold to make a change pass. Run `cd backend && source .venv/bin/activate && pytest -v --cov`, then `cd frontend && npm run test:coverage && npm run lint && npm run build`.
- **Time:**
  - Every datetime column is `UTCDateTime` (`backend/app/core/types.py`).
  - The API returns `+00:00` values.
  - All-day events are `00:00Z` dates with an exclusive end.
  - Range queries use overlap (`start < window_end AND end > window_start`), never containment.
  - Frontend date handling goes through `frontend/src/lib/dates.ts`.
- **Tenancy:** every family-owned row has `family_id`, and every query filters by it. An install holds exactly one family (trigger `families_single_row`, migration 006); public sign-in queries scope to it via `services/family.install_family_id`.
- **Auth:**
  - User sessions are an HttpOnly JWT cookie (30 days) whose `jti` is a `sessions` row, checked on every request. Admin endpoints also need a password session (or `/auth/elevate` within 15 minutes).
  - Wall displays use a paired-device cookie scoped to `/api/wall`.
  - Never trust a role claim from a token without loading the user.
- **Schema:** for a new model, add it under `backend/app/models/`, import it in `models/__init__.py` and `alembic/env.py`, and add an Alembic migration. The next migration number is **012** (006 = one family per install, 007 = media, 008 = chores, 009 = rewards, 010 = meals, 011 = books, announcements and birthdays). Migrations run automatically at startup.
- **Chores and points:** due dates are plain family-local `Date`s (`services/chores.family_today`), never UTC dates. The `points_ledger` is append-only and unique per (source_type, source_id): credit and reverse with new rows, never update or delete. Routine steps are chore templates with `routine_id`.
- **Rewards:** spending, refunds, badge bonuses and admin adjustments are all `points_ledger` rows keyed by their source. A redemption leaves `pending` only once (conditional update). Allowance is integer cents in its own append-only `allowance_ledger`, unique per (user, week). Streaks come from `services/rewards.streak_days` (shared with `/chores/stats`).
- **Preferences:** per-person choices (menu position, dashboard pages, wallpaper, calendar scope) live in `users.settings_json["prefs"]` via `/api/users/me/preferences`, never in browser storage; save changes as updaters on the latest cached prefs (see `Dashboard.tsx`).
- **Fetching URLs:** anything that fetches a user-supplied link goes through `core/safe_fetch.fetch_public` (SSRF guard and pinned connection on every hop, size and time caps). Never call httpx on a user URL directly.
- **Media:** family photos and videos live under `data/photos/media/<family>/<id>/` and are served only by `/api/media` (family members) and `/api/wall/media` (paired displays). Never add a public static route to them. Only processed renditions are stored (no EXIF/metadata). ffmpeg comes from `imageio-ffmpeg`; conversions run in the background, one at a time.
- **Single API worker:** the scheduler, event bus, WebSocket hub and rate limiter are all in-process. Add jobs to the existing scheduler (`backend/app/jobs/scheduler.py`, which runs in `TIMEZONE`); never start a second scheduler.
- **Secrets:** `SECRET_KEY` has no default on purpose. Never commit `.env`, databases or tokens.
- **Git:** branch per change, one logical change per commit, and messages that explain why.

## Do not bring these over from v0.29

When porting a feature, re-implement it rather than copying the file. TODO.md has the file and line references.

- `POST /auth/reset-setup`: an unauthenticated account wipe that enables a two-request takeover. Never add it in any form.
- A default `SECRET_KEY` fallback.
- Timestamps stored as `Text` / ISO strings. Use `UTCDateTime`.
- Containment range filters (`start >= a AND end <= b`).
- 365-day tokens that never re-check the database, with the role baked in.
- `allow_origins=["*"]` combined with `allow_credentials=True`.
- PIN login that loops over every user and rate-limits only after a match.
- Unauthenticated list endpoints (for example, announcements).
- A "today's chores" query that returns everything ever completed (`completed_at != None` with no date guard).
- v0.29's offline-sync code. Its mutation hook is never called and replays send no credentials. Design against the Phase 9 tests instead.
- v0.29's chore completion, which never credits points, and its `every_N_days` generator, which drifts daily.
- Unauthenticated meals GETs, and wall panels that need a family member's login.

## Roadmap status

**TODO.md is the source of truth** for tasks and ordering; the table below is a summary that can lag behind it.

| Phase | Scope | Status |
|---|---|---|
| 1 | Routing, login errors, time zones, ranges, Sync Now/Delete, source filter, wall pairing, `deploy.sh` | Done, shipped in 0.18 |
| 2 | Security: event roles, avatar + PIN sign-in with password for admins, remove `/users/switch`, session revocation | Done, shipped in 0.30 |
| 3 | iCal correctness: duplicate first occurrence, EXDATE/RECURRENCE-ID, all-day recurrences, floating times, storage window, batch UID lookup | Done, 0.82 |
| 3b | Wall essentials: photo/video slideshow (media library, EXIF stripping, wall-token reads), sleep schedule, off-host backups | Done, 0.88 |
| 4 | Infra/cleanup: Alembic on start, CI, Workbox patterns, Pi script, dead code, settings, `.gitignore` | Done, shipped in 0.30 |
| 5 | Port chores (+ to-dos, routines); fix v0.29's missing points credit, interval drift, UTC due dates | Done, 0.94 |
| 6 | Port rewards (append-only points ledger, idempotent weekly allowance in cents, catalog, badges/streaks) + progress widget | Done, 1.12 |
| 7 | Port meals and recipes (auth on every endpoint, SSRF-safe URL import, plan, pantry, shopping list, recipe catalog) | Done, 1.19 |
| 8 | Port books (+ shared-library writes), announcements, birthdays, weather, dashboard summary + customization | Done, 1.24 |
| 9 | Offline sync (IndexedDB queue, conflict modal) | Open |
| 10 | OCR shopping-list scan, wall cycling panels via read-only wall endpoints | Open; needs 7 |
| 11 | Notifications and reminders (events, chores, to-dos, birthdays, pantry; Web Push/ntfy/SMTP; quiet hours, wellness) | Open; needs 5, 7–8 |
| 12 | Home Assistant local integration, local-first AI voice agent, notes board | Open |
| 13 | Two-way calendar sync (Google OAuth, Outlook Graph, CalDAV; conflict policy, mapping UI) | Open; needs 3 |

### Decisions (2026-10-04)

- **Port, don't merge:** v0.29 features are rebuilt on this codebase. Its backend is a spec. Its frontend pages are reused through an API adapter, and its tests serve as acceptance criteria.
- **Fresh start:** there's no importer for v0.29 data.
- **Sign-in:** an avatar picker + PIN for everyone (per-user, with failed-attempt lockout), and a password session for admin actions.
- **Versioning:** the merged line continued at **0.30**. Since 2026-10-12 every commit is its own build (`<release>`), so releases are named by phase, not number; TODO.md records the build each phase shipped in.

### Prerequisites

- Done in 0.30: `file:*` is in `.gitignore` (SQLite shared-cache names like `file:memdb1-wal`).

## Deploying

```bash
scripts/deploy.sh publish                                                   # build + push images to Forgejo
PUBLIC_URL=https://openfamhub.vernonmyers.cloud scripts/deploy.sh remote test # deploy to the test VM
PUBLIC_URL=https://<prod-url> scripts/deploy.sh promote prod <release>        # promote a checked build
```

The `test` VM runs behind the existing Caddy at `openfamhub.vernonmyers.cloud`, which forwards to VM port 8080 (see [docs/deployment.md](docs/deployment.md)). Claude sessions in Cowork can't reach the LAN, Forgejo or GitHub, so Vern runs pushes and deploys.
