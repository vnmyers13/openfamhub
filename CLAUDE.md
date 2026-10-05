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

## Roadmap status

The detail is in [TODO.md](TODO.md).

| Phase | Scope | Status |
|---|---|---|
| 1 | Routing, login errors, time zones, ranges, Sync Now/Delete, source filter, wall pairing, `deploy.sh` | Done, v0.18 |
| 2 | Security: event roles, login hardening, remove `/users/switch`, session revocation | Open |
| 3 | iCal correctness: duplicate first occurrence, EXDATE/RECURRENCE-ID, all-day recurrences, storage window, batch UID lookup | Open |
| 4 | Infra/cleanup: Alembic on start, CI, Workbox patterns, Pi script, dead code, settings | Open |
| 5 | Port chores (templates, instances, claim/complete, generator at 06:00) | Open |
| 6 | Port rewards (append-only points ledger, idempotent weekly allowance, catalog, badges/streaks) | Open; needs 5 |
| 7 | Port meals and recipes (import, 7-day plan, shopping list, weekly reset) | Open |
| 8 | Port books (awards points via 6), announcements, weather (Open-Meteo, cached) | Open; needs 6 |
| 9 | Offline sync (frontend test runner, IndexedDB queue, conflict modal) | Open |
| 10 | OCR shopping-list scan, wall cycling panels, timezone picker | Open; needs 7 |

### Open decisions and prerequisites

- **Version numbering:** both lines shipped a "0.18". Decide which keeps that number before Phase 5 ships, and record the decision in `CHANGELOG.md`.
- **Before Phase 5 opens a dev DB:** add a `.gitignore` pattern for SQLite shared-cache files (for example `file:*`). `*.db-wal` doesn't match names like `file:memdb1-wal`.

## Deploying

```bash
scripts/deploy.sh publish                                                   # build + push images to Forgejo
PUBLIC_URL=https://openfamhub.vernonmyers.cloud scripts/deploy.sh remote test # deploy to the test VM
```

The `test` VM runs behind the existing Caddy at `openfamhub.vernonmyers.cloud`, which forwards to VM port 8080 (see [docs/deployment.md](docs/deployment.md)). Claude sessions in Cowork can't reach the LAN, Forgejo or GitHub, so Vern runs pushes and deploys.
