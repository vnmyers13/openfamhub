# Agent Context

Start with [CLAUDE.md](CLAUDE.md) (canonical line, rules, roadmap status), then [docs/architecture.md](docs/architecture.md). Deployment is in [docs/deployment.md](docs/deployment.md), and dev and test commands are in [GETTING_STARTED.md](GETTING_STARTED.md).

## Version and branches
- Current version: the integer in `VERSION` (repo root). The release name comes from `scripts/release-name`: `0.<n>` below 100, then 1, then 1.01 … 1.99, 2, 2.01 (two digits after the dot, none on a round hundred). `backend/app/core/config.py` and `scripts/issues.py` mirror it; change all three together. The `pre-commit` hook bumps `VERSION` by one on every commit. `scripts/check-version.sh` enforces `+1` on `master`'s first-parent chain and "greater than base" on branches. Tags are `v<release>`. Do not edit `VERSION` by hand.
- Default branch: `master`. Remotes: `forgejo` (`http://192.168.10.2:3002/vernon/OpenFamHub.git`, primary; CI runs here) and `origin` (GitHub). Mirrors: `192.168.10.101:3002` and `192.168.10.102:3002` (same `vernon/OpenFamHub.git` path). Push to the primary first, then the others.
- After rebasing onto a moved `master`, run `scripts/renumber origin/master` so commits continue the `VERSION` sequence.
- Work on a branch with one commit per logical change.
- When a change completes a Forgejo issue, tick its TODO.md line (which names the issue as `#N` or its link) in the same commit, and add `Fixes #N` to the commit message. See `docs/releasing.md`.
- After cloning, run `git config core.hooksPath .githooks`. The next commit will be `0.(current+1)`.

## Registries
- Primary: Forgejo container registry, `forgejo.vernonmyers.cloud/vernon/openfamhub-{api,web}`, pushed by `scripts/deploy.sh publish`.
- Legacy: GitHub Actions used to push `ghcr.io/<repo>/openfamhub-*`, retired in 0.30 when CI moved to Gitea; the Docker Hub user is `vnmyers13`. Tokens come from the password manager. Never commit them.

## Layout
```
backend/app/        FastAPI app: core/ models/ schemas/ routers/ services/ integrations/ jobs/
backend/scripts/    one-off maintenance (fix_event_timezones.py)
backend/tests/      pytest (phase1/2, auth, ssrf, realtime, ical_recurrence, ical_phase3, calendar_sync, calendar_scoping, calendar_routes, single_family, family_settings, media, chore_schedule, chores_api, todos_routines, users_api, wall_api, ws_manager, backup, startup, version)
backend/alembic/    migrations 001–008 (004 = wall_devices, 005 = session auth_method, 006 = one family per install, 007 = media, 008 = chores); run at startup
frontend/src/       React app: api/ lib/ (dates, permissions) hooks/ pages/ (lazy-loaded) wall/ components/; tests are *.test.ts[x] beside the code
config/             Caddyfile (LAN TLS), Caddyfile.proxy (behind proxy), routes.caddy (shared)
deploy/             compose.yml + env.template, copied to servers by deploy.sh remote
scripts/            deploy.sh (setup/deploy/update/publish/remote/…), release-name, renumber, check-version.sh, backup-offhost.sh, setup-wall-pi.sh, trivy-scan.sh, create_trivy_issues.py, issues.py (+ forgejo_api.py); tests/ holds the shell harnesses and a fake Forgejo
docker-compose.yml  build-from-source stack; image names match published ones
```

## Commands
| Action | Command |
|---|---|
| Backend tests (+ coverage, floor in `backend/.coveragerc`) | `cd backend && source .venv/bin/activate && pytest -v --cov` |
| Frontend tests (Vitest, TZ pinned to America/Detroit) | `cd frontend && npm test`; `npm run test:coverage` for coverage + thresholds (CI); `npm run test:watch` while developing |
| Frontend lint / typecheck + build | `cd frontend && npm run lint` / `npm run build` |
| Dev servers | `uvicorn app.main:app --reload --port 8000` (in backend/) + `npm run dev` (in frontend/) |
| Local container stack | `scripts/deploy.sh setup && scripts/deploy.sh deploy` |
| Publish images | `scripts/deploy.sh publish [version]` |
| Deploy to the test VM | `PUBLIC_URL=https://openfamhub.vernonmyers.cloud scripts/deploy.sh remote test` |
| Promote checked build to prod | `PUBLIC_URL=https://<prod-url> scripts/deploy.sh promote prod <release>` |
| Health | `curl http://localhost:8000/api/health` |
| Script harnesses (versioning, deploy, Trivy, issues) | `for t in scripts/tests/*-test.sh; do bash "$t"; done` |
| Issue triage against TODO.md | `ISSUES_TOKEN=… python3 scripts/issues.py triage` (CI also keeps the pinned Triage report issue current) |

## Gotchas
- **Time:** every datetime column is `UTCDateTime`. Always pass aware datetimes, or naive values meaning UTC. The API returns `+00:00`. All-day events are `00:00Z` dates with an exclusive end. Frontend code must use `src/lib/dates.ts`.
- **Range queries** use overlap, not start-in-range.
- **Schema:** startup runs Alembic (`app/core/migrate.py`; pre-0.30 databases are stamped first). Add a migration for every model change (next: 009), and import new models in `models/__init__.py` and `alembic/env.py`.
- **Auth:** every user token's `jti` is a `sessions` row (revoked on logout, password change and removal). Sessions record `auth_method` (pin|password); admin endpoints need a password session or `/auth/elevate` within 15 min, otherwise 403 `password_required`. Failed sign-ins lock out per person (`login_throttle`). Wall displays use a `wall_token` cookie scoped to `/api/wall` (SHA-256 stored). The axios 401 handler skips `/auth/*` and `/wall/*`.
- **Live updates:** never call `event_bus.emit` from request or job code; use `queue_event(db, ...)` so the notice is published after commit (`get_db` / `publish_queued`).
- **iCal parsing:** `integrations/ical_feed.parse_ics(content, family_tz, now)` is pure; test it directly with a fixed `now`. Every occurrence is a UTC instant; zoned times go through zoneinfo (icalendar returns pytz zones, which drift at DST under rrule).
- **Media uploads** are a raw request body (`X-Filename` header), not multipart, so the size limit applies while streaming. The type is sniffed from the first bytes. Background video jobs use `services/media.session_factory`; tests swap it for the test session and call `wait_for_jobs()`. Tests must point `MEDIA_ROOT` at a temp dir.
- **Chores:** `services/chores` holds scheduling (`due_dates`, `generate_instances`, idempotent; `(template_id, due_date)` is unique). Completing uses a conditional status update so only one request wins, then credits `points_ledger`. Tests that run the hourly job swap `jobs/chore_generator.session_factory`.
- **Frontend component tests:** use `src/test/api.ts` (`mockApi`, `apiError`) and `src/test/render.tsx` (`renderApp`) rather than mocking hooks.
- **Server-side fetches of user URLs:** use `resolve_public_addresses` and connect to the returned IP (see `fetch_ics_bytes`), never a plain `httpx.get(url)`.
- **Single API worker:** the scheduler, event bus, WebSocket hub and PIN rate limiter are all in-process. Don't add uvicorn workers.
- **node_modules on the Mac** holds macOS binaries. `vite build` fails in Linux containers or VMs that reuse it, so `frontend/.dockerignore` excludes it.
- **Test fixtures:** `client` overrides `get_db` with one shared session per test. Cookies are `Secure`, so tests pass them as an explicit `Cookie` header (see `_cookie()` in `test_phase1.py`).
- **CI** runs on the Gitea instance via Gitea Actions (`.gitea/workflows/ci.yml`), on a runner hosted on the test VM. It publishes the Forgejo registry and deploys on `master`; see [docs/ci.md](docs/ci.md).

## Open work
See [TODO.md](TODO.md), the source of truth: the remaining review-backlog items, then Phase 3 + 3b (iCal correctness, wall essentials) and Phases 5–13 (porting the v0.29 feature set, Cozyla parity). CLAUDE.md has a status table.
