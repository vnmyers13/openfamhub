# Agent Context

Start with [CLAUDE.md](CLAUDE.md) (canonical line, rules, roadmap status), then [docs/architecture.md](docs/architecture.md). Deployment is in [docs/deployment.md](docs/deployment.md), and dev and test commands are in [GETTING_STARTED.md](GETTING_STARTED.md).

## Version and branches
- Current version: **0.30**. The canonical source is `APP_VERSION` in `backend/app/core/config.py`; it's also in the `backend/Dockerfile` label and the README badge.
- Default branch: `master`. Remotes: `forgejo` (`http://192.168.10.2:3002/vernon/OpenFamHub.git`, primary) and `origin` (GitHub mirror).
- Work on a branch with one commit per logical change.

## Registries
- Primary: Forgejo container registry, `forgejo.vernonmyers.cloud/vernon/openfamhub-{api,web}`, pushed by `scripts/deploy.sh publish`.
- Legacy: GitHub Actions pushes to `ghcr.io/<repo>/openfamhub-*`; the Docker Hub user is `vnmyers13`. Tokens come from the password manager. Never commit them.

## Layout
```
backend/app/        FastAPI app: core/ models/ schemas/ routers/ services/ integrations/ jobs/
backend/scripts/    one-off maintenance (fix_event_timezones.py)
backend/tests/      pytest (conftest.py, test_auth.py, test_phase1.py, test_phase2.py)
backend/alembic/    migrations 001–005 (004 = wall_devices, 005 = session auth_method); run at startup
frontend/src/       React app: api/ lib/dates.ts pages/ wall/ components/
config/             Caddyfile (LAN TLS), Caddyfile.proxy (behind proxy), routes.caddy (shared)
deploy/             compose.yml + env.template, copied to servers by deploy.sh remote
scripts/            deploy.sh (setup/deploy/update/publish/remote/…), setup-wall-pi.sh
docker-compose.yml  build-from-source stack; image names match published ones
```

## Commands
| Action | Command |
|---|---|
| Backend tests | `cd backend && source .venv/bin/activate && pytest -v` |
| Frontend lint / typecheck + build | `cd frontend && npm run lint` / `npm run build` |
| Dev servers | `uvicorn app.main:app --reload --port 8000` (in backend/) + `npm run dev` (in frontend/) |
| Local container stack | `scripts/deploy.sh setup && scripts/deploy.sh deploy` |
| Publish images | `scripts/deploy.sh publish [version]` |
| Deploy to the test VM | `PUBLIC_URL=https://openfamhub.vernonmyers.cloud scripts/deploy.sh remote test` |
| Health | `curl http://localhost:8000/api/health` |

## Gotchas
- **Time:** every datetime column is `UTCDateTime`. Always pass aware datetimes, or naive values meaning UTC. The API returns `+00:00`. All-day events are `00:00Z` dates with an exclusive end. Frontend code must use `src/lib/dates.ts`.
- **Range queries** use overlap, not start-in-range.
- **Schema:** startup runs Alembic (`app/core/migrate.py`; pre-0.30 databases are stamped first). Add a migration for every model change (next: 006), and import new models in `models/__init__.py` and `alembic/env.py`.
- **Auth:** every user token's `jti` is a `sessions` row (revoked on logout, password change and removal). Sessions record `auth_method` (pin|password); admin endpoints need a password session or `/auth/elevate` within 15 min, otherwise 403 `password_required`. Failed sign-ins lock out per person (`login_throttle`). Wall displays use a `wall_token` cookie scoped to `/api/wall` (SHA-256 stored). The axios 401 handler skips `/auth/*` and `/wall/*`.
- **Single API worker:** the scheduler, event bus, WebSocket hub and PIN rate limiter are all in-process. Don't add uvicorn workers.
- **node_modules on the Mac** holds macOS binaries. `vite build` fails in Linux containers or VMs that reuse it, so `frontend/.dockerignore` excludes it.
- **Test fixtures:** `client` overrides `get_db` with one shared session per test. Cookies are `Secure`, so tests pass them as an explicit `Cookie` header (see `_cookie()` in `test_phase1.py`).
- **CI** (`.github/workflows/build.yml`) runs on GitHub only. Forgejo has no runner yet.

## Open work
See [TODO.md](TODO.md): Phases 2–4 (review fixes) and 5–10 (porting the v0.29 feature set). CLAUDE.md has a status table.
