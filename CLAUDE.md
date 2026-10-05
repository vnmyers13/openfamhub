# CLAUDE.md

OpenFamHub: a self-hosted family calendar and organizer (a home version of a Skylight-style wall calendar). FastAPI + SQLite backend, React frontend, Docker/Caddy deployment, Raspberry Pi wall display. Current version: **0.18** (`APP_VERSION` in `backend/app/core/config.py`).

Read these before changing code:

- [AGENTS.md](AGENTS.md): layout, commands, gotchas
- [docs/architecture.md](docs/architecture.md): how the app works, including time handling and auth
- [TODO.md](TODO.md): the roadmap; the authoritative task list
- [docs/deployment.md](docs/deployment.md): publish and deploy

## Which code is canonical

- **`master` is the product.** Feature work branches from it. `release/0.18-deploy` carries the 0.18 deploy and docs work.
- **`origin/main` (tagged v0.29) is a different codebase with no shared history.** Use it only as a reference for features to port (Phases 5–10). Never merge, rebase onto or cherry-pick from it. Re-implement each feature on our architecture: our auth, `family_id` scoping, `UTCDateTime`, Alembic migrations, deploy tooling and CI.
- **Remotes:** `forgejo` (`http://192.168.10.2:3002/vernon/OpenFamHub.git`, primary) and `origin` (GitHub). Push to both.

## Rules

- **Tests first.** Each TODO phase lists its test targets; write them before the code, in the same change. Baseline is 17 backend tests in 2 files. Run `cd backend && source .venv/bin/activate && pytest -v`, then `cd frontend && npm run lint && npm run build`.
- **Time:**
  - Every datetime column is `UTCDateTime` (`backend/app/core/types.py`).
  - The API returns `+00:00` values.
  - All-day events are `00:00Z` dates with an exclusive end.
  - Range queries use overlap (`start < window_end AND end > window_start`), never containment.
  - Frontend date handling goes through `frontend/src/lib/dates.ts`.
- **Tenancy:** every family-owned row has `family_id`, and every query filters by it.
- **Auth:**
  - User sessions are an HttpOnly JWT cookie (30 days) that's re-checked against the DB.
  - Wall displays use a paired-device cookie scoped to `/api/wall`.
  - Never trust a role claim from a token without loading the user.
- **Schema:** for a new model, add it under `backend/app/models/`, import it in `models/__init__.py` and `alembic/env.py`, and add an Alembic migration. The next migration number is **005**. Startup `create_all` only adds new tables.
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

The detail is in [TODO.md](TODO.md).

| Phase | Scope | Status |
|---|---|---|
| 1 | Routing, login errors, time zones, ranges, Sync Now/Delete, source filter, wall pairing, `deploy.sh` | Done, v0.18 |
| 2 | Security: event roles, avatar + PIN sign-in with password for admins, remove `/users/switch`, session revocation | Open (0.30) |
| 3 | iCal correctness: duplicate first occurrence, EXDATE/RECURRENCE-ID, all-day recurrences, storage window, batch UID lookup | Open (0.31) |
| 4 | Infra/cleanup: Alembic on start, CI, Workbox patterns, Pi script, dead code, settings, `.gitignore` | Open (0.30) |
| 5 | Port chores; fix v0.29's missing points credit, interval drift, UTC due dates | Open (0.31) |
| 6 | Port rewards (append-only points ledger, idempotent weekly allowance in cents, catalog, badges/streaks) | Open (0.32); needs 5 |
| 7 | Port meals and recipes (auth on every endpoint, SSRF-safe URL import, plan, shopping list, weekly reset) | Open (0.33) |
| 8 | Port books (+ shared-library writes), announcements, weather, `/api/dashboard/summary` | Open (0.34); needs 6 |
| 9 | Offline sync (frontend test runner, IndexedDB queue, conflict modal) | Open (0.35) |
| 10 | OCR shopping-list scan, wall cycling panels via read-only wall endpoints | Open (0.36); needs 7 |

### Decisions (2026-10-04)

- **Port, don't merge:** v0.29 features are rebuilt on this codebase. Its backend is a spec. Its frontend pages are reused through an API adapter, and its tests serve as acceptance criteria.
- **Fresh start:** there's no importer for v0.29 data.
- **Sign-in:** an avatar picker + PIN for everyone (per-user, with failed-attempt lockout), and a password session for admin actions.
- **Versioning:** the merged line continues at **0.30**. TODO.md maps releases 0.30–0.36 to phases.

### Prerequisites

- **Before Phase 5 opens a dev DB:** add `file:*` to `.gitignore`. `*.db-wal` doesn't match SQLite shared-cache names like `file:memdb1-wal`.

## Deploying

```bash
scripts/deploy.sh publish                                                   # build + push images to Forgejo
PUBLIC_URL=https://openfamhub.vernonmyers.cloud scripts/deploy.sh remote test # deploy to the test VM
```

The `test` VM runs behind the existing Caddy at `openfamhub.vernonmyers.cloud`, which forwards to VM port 8080 (see [docs/deployment.md](docs/deployment.md)). Claude sessions in Cowork can't reach the LAN, Forgejo or GitHub, so Vern runs pushes and deploys.
