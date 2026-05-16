# Agent Context

## Docker Hub
- Username: vnmyers13
- Token: set `DOCKERHUB_USERNAME=vnmyers13` and `DOCKERHUB_TOKEN=...` in env (get token from password manager)

## Version & Branch
- Current: 0.17 (canonical source: `APP_VERSION` in `backend/app/core/config.py:10`)
- Branch: `master` (not `main`). CI build.yml triggers on `main` pushes only — there's a branch/CI mismatch.

## Directory Layout
```
backend/          Python/FastAPI async backend
  app/main.py     API entrypoint (FastAPI app with lifespan)
  app/core/       config, database, security, events
  app/models/     SQLAlchemy ORM models (user, family, calendar_*)
  app/routers/    API route handlers (auth, users, calendar, integrations, ws)
  app/services/   Business logic (calendar, users, notifications)
  app/integrations/ External integrations (ical_feed)
  app/jobs/       APScheduler jobs (calendar_sync, backup, scheduler)
  app/schemas/    Pydantic request/response schemas
  tests/          pytest suite (conftest.py, test_auth.py)
  alembic/        Async Alembic migrations
  Dockerfile      CMD: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
frontend/         React/Vite/TypeScript
  src/main.tsx    Frontend entrypoint
  src/pages/      Page components (CalendarPage, Dashboard, Login, SetupWizard, ManageUsers)
  src/stores/     Zustand stores (auth.ts)
  src/api/        Axios client + calendar API module
  Dockerfile      Multi-stage: npm ci + build → nginx:alpine on port 3000
config/Caddyfile  Reverse proxy: /api/* /photos/* /ws/* → api:8000, else → web:3000
data/             SQLite DB, photos, backups (gitignored)
```

## Stack
- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 async, aiosqlite, Alembic, APScheduler, python-jose, passlib/bcrypt, pydantic-settings
- **Frontend**: React 19, Vite 8, TypeScript 6.0, Tailwind CSS 3, Zustand 5, TanStack React Query 5, react-big-calendar, react-router-dom 7, vite-plugin-pwa
- **Infra**: Docker Compose (api + web + caddy:2-alpine), Caddy internal TLS, SQLite with WAL mode + foreign_keys=ON, ghcr.io registry (CI pushes to `ghcr.io/${{ github.repository }}/openfamhub-*`)

## Commands
| Action | Command |
|---|---|
| Local dev | `docker compose up -d` |
| Backend tests | `cd backend && source .venv/bin/activate && pytest` |
| Single test | `cd backend && source .venv/bin/activate && pytest tests/test_auth.py -v` |
| Frontend build + typecheck | `cd frontend && npm run build` (runs `tsc -b && vite build`) |
| Frontend lint | `cd frontend && npm run lint` |
| Frontend dev server | `cd frontend && npm run dev` (Vite proxies /api and /photos → localhost:8000) |
| Health check | `curl -k https://openfamhub.local/api/health` or `curl http://localhost:8000/api/health` |
| Alembic migration | `cd backend && source .venv/bin/activate && alembic upgrade head` |

## Testing
- **pytest.ini**: `asyncio_mode = auto`, test paths = `tests/`
- **conftest.py**: In-memory SQLite (`sqlite+aiosqlite:///:memory:`) with per-function session + schema create/drop. Uses `httpx.AsyncClient` with `app.dependency_overrides` to inject test DB session.
- **CI**: GitHub Actions runs `pytest backend/tests/ -v` before building Docker images.

## Database
- SQLite via aiosqlite with SQLAlchemy 2.0 async
- Pragma: `foreign_keys=ON`, `journal_mode=WAL`
- Tables created automatically at startup via `Base.metadata.create_all` (Alembic migrations also exist)
- Default path: `/data/db/homehub.db` (mapped as Docker volume `./data/db:/data/db`)

## Auth
- JWT tokens in cookies (30-day expiry), HS256 with `settings.secret_key`
- Password hashing via bcrypt (passlib)
- PIN login with in-memory rate limiting (5 attempts per 60s)
- Role-based access via `require_role("admin", "member")` dependency

## Release Process
Comprehensive checklist at `release_checklist.json` (8 phases, P1–P8). Key steps:
1. Version bump: `APP_VERSION` in `backend/app/core/config.py` (also `backend/Dockerfile` LABEL, README)
2. Format: `MAJOR.MINOR` — increment MINOR by 1 per release
3. Full test suite → Frontend build → Docker build → Smoke test
4. Push to GitHub → Create release → Push to Docker Hub
5. Post-release: mark TODOs, write summary to `docs/releases/vX.XX.md`

## CI
- `.github/workflows/build.yml`: Runs tests + builds + pushes API and Web images to ghcr.io on `main` branch push
- Only AMD64 platform (no ARM builds)

## Gotchas
- CI pushes to **ghcr.io**, not Docker Hub (Docker Hub push is manual via release checklist)
- `.env` is gitignored — never commit it. Copy from `.env.example`
- `data/` directory is gitignored (except `.gitkeep` placeholders)
- Backend and frontend are separate Docker images; frontend is served by nginx, not Vite dev server, in production
- Python venv at `backend/.venv` — must activate before any Python/alembic/pytest commands
