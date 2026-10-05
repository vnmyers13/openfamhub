# Developing OpenFamHub

This guide covers running the app from source, running the tests, and cutting a release. To deploy, see [docs/deployment.md](docs/deployment.md). For how the code fits together, see [docs/architecture.md](docs/architecture.md).

## Prerequisites (macOS)

```bash
brew install python@3.12 node@22 git
# Docker Desktop, for building and running the containers
```

Node 20.19+ or 22 is needed (Vite 8).

## First-time setup

```bash
git clone http://192.168.10.2:3002/vernon/OpenFamHub.git
cd OpenFamHub
scripts/deploy.sh setup                # .env with a generated SECRET_KEY, ./data folders

# Backend
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt

# Frontend
cd frontend && npm ci && cd ..
```

For local development, set the database path in `.env` to the repo's data folder:

```bash
DATABASE_URL=sqlite+aiosqlite:///./data/db/homehub.db   # relative paths resolve from the repo root
```

## Running locally

Two terminals:

```bash
# 1) API on :8000 (auto-reload)
source backend/.venv/bin/activate
cd backend && uvicorn app.main:app --reload --port 8000

# 2) Web on :5173; Vite proxies /api (including the WebSocket) and /photos to :8000
cd frontend && npm run dev
```

Open <http://localhost:5173>. Login cookies are marked `Secure`; browsers allow that on `http://localhost` (Chrome and Firefox do; if Safari drops the cookie, use one of those).

- API docs: <http://localhost:8000/api/docs>
- First run: the setup wizard creates the family and the admin.
- Wall display: create a pairing link under **Admin › Wall displays**, then open it (it points at `/wall?token=…`).

To run the full container stack instead: `scripts/deploy.sh deploy` (LAN mode, `https://openfamhub.local`).

## Tests and checks

```bash
# Backend
source backend/.venv/bin/activate
cd backend && pytest -v

# Frontend
cd frontend
npm run lint
npm run build      # tsc -b + vite build; fails on type errors
```

- Backend tests use an in-memory SQLite database and need `SECRET_KEY` (read from the repo-root `.env`, or export it).
- `tests/test_phase1.py` covers time handling, range queries, calendar sources and wall pairing. `tests/test_phase2.py` covers sign-in, sessions, the admin password gate and event permissions.
- Run `npm` commands on the Mac itself: `node_modules` contains macOS-native binaries, and a Linux container or VM can't use them.

## Conventions

- **Time:** store UTC, and treat all-day events as dates. Read the *Time handling* section of [docs/architecture.md](docs/architecture.md) before touching dates. On the frontend, use the helpers in `src/lib/dates.ts` instead of `new Date(event.start_dt)`.
- **New tables:** add the model under `backend/app/models/`, import it in `models/__init__.py` and `alembic/env.py`, and add an Alembic migration. Migrations run automatically at startup (`app/core/migrate.py`), so every model change needs one.
- **Commits:** one logical change per commit, with a message that explains *why*.

## Releasing

1. Bump `APP_VERSION` in `backend/app/core/config.py`, the label in `backend/Dockerfile` and the badge in `README.md`.
2. Add a section to `CHANGELOG.md`.
3. Run the tests and checks above.
4. Commit and tag: `git tag v0.30 && git push forgejo master --tags` (and `origin` if you mirror to GitHub).
5. `scripts/deploy.sh publish`
6. Deploy to test, check it, then deploy to production: `scripts/deploy.sh remote test`, then `scripts/deploy.sh remote <prod-host>`.

`release_checklist.json` and `sprint_s*.json` are the original sprint-planning manifests. They're kept for history, and some of their steps (Docker Hub, `deploy.sh staging|production`) are out of date.

## Common problems

| Problem | Fix |
|---|---|
| `pydantic ValidationError: secret_key field required` | `.env` is missing or has no `SECRET_KEY`: run `scripts/deploy.sh setup`. |
| `Cannot find native binding` (rolldown) when building the web image | An old checkout without `frontend/.dockerignore`; pull the latest code. |
| Login works but you're sent straight back to `/login` | The cookie wasn't stored: use `localhost` (not an IP) over http, or a trusted HTTPS URL. |
| Port 8000 or 5173 already in use | `lsof -i :8000` and stop the old process. |
