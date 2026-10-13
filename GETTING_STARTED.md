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
git clone http://192.168.10.2:3002/vernon/OpenFamHub.git   # primary; mirrors: 192.168.10.101:3002, 192.168.10.102:3002
cd OpenFamHub
git config core.hooksPath .githooks    # the pre-commit hook bumps VERSION (release string 0.<n>)
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
npm test           # Vitest unit tests (npm run test:watch while developing)
npm run lint
npm run build      # tsc -b + vite build; fails on type errors

# Release tooling (VERSION hook, renumber, deploy stamping)
for t in scripts/tests/*-test.sh; do bash "$t"; done
```

- Backend tests use an in-memory SQLite database and need `SECRET_KEY` (read from the repo-root `.env`, or export it).
- Backend: `test_phase1.py` covers time handling, range queries, calendar sources and wall pairing; `test_phase2.py` sign-in, sessions, the admin password gate and event permissions; `test_ical_recurrence.py` recurring feeds; `test_calendar_scoping.py` source and family scoping; `test_single_family.py` one family per install and sign-in scope; `test_ssrf.py` feed fetching; `test_realtime.py` live updates; `test_startup.py` boots the real app (migrations + scheduler) in a subprocess.
- Frontend tests live next to the code (`src/**/*.test.ts[x]`) and run in jsdom with `TZ=America/Detroit`, so date bugs west of UTC show up on every machine. The first ones cover `lib/dates.ts`, the wall (midnight rollover, WebSocket cleanup, revocation), the password prompt and the admin guard.
- Run `npm` commands on the Mac itself: `node_modules` contains macOS-native binaries, and a Linux container or VM can't use them.

## Conventions

- **Time:** store UTC, and treat all-day events as dates. Read the *Time handling* section of [docs/architecture.md](docs/architecture.md) before touching dates. On the frontend, use the helpers in `src/lib/dates.ts` instead of `new Date(event.start_dt)`.
- **New tables:** add the model under `backend/app/models/`, import it in `models/__init__.py` and `alembic/env.py`, and add an Alembic migration. Migrations run automatically at startup (`app/core/migrate.py`), so every model change needs one.
- **Commits:** one logical change per commit, with a message that explains *why*.

## Releasing

Every commit is a build, so there is no separate release step for the `test` VM:

1. **Version numbers are automatic.** The `pre-commit` hook bumps `VERSION` (repo root) and the `README.md` badge on every commit. Never edit `VERSION` by hand.
2. **Rebasing?** If `master` moved while you worked, rebase onto it and run `scripts/renumber origin/master`, so your commits continue the sequence instead of reusing numbers. `scripts/check-version.sh master origin/master HEAD` confirms the result.
3. **CHANGELOG.** Entries are keyed by phase or work batch, not by commit. Add your user-visible changes under the `[Unreleased]` entry; when the batch is confirmed on `test`, its heading gets the build number that shipped it.
4. Run the tests and checks above.
5. **Push to the primary Forgejo** (`git push forgejo master`). CI runs the checks, publishes `0.<n>`, tags `v0.<n>` and deploys to `test`. Then update the off-site copies: `git push origin master` (GitHub) and the mirrors at `192.168.10.101:3002` and `192.168.10.102:3002`.
6. Check the build on `test` (Help & About or `/api/health`). A production host is planned but not set up yet; when it is, promote a checked build with `scripts/deploy.sh remote <prod-host> 0.<n>`.

Without CI, publish and deploy by hand: `scripts/deploy.sh publish` (creates and pushes the `v0.<n>` tag), then `scripts/deploy.sh remote test`.

`release_checklist.json` and `sprint_s*.json` are the original sprint-planning manifests. They're kept for history, and some of their steps (Docker Hub, `deploy.sh staging|production`) are out of date.

## Common problems

| Problem | Fix |
|---|---|
| `pydantic ValidationError: secret_key field required` | `.env` is missing or has no `SECRET_KEY`: run `scripts/deploy.sh setup`. |
| `Cannot find native binding` (rolldown) when building the web image | An old checkout without `frontend/.dockerignore`; pull the latest code. |
| Login works but you're sent straight back to `/login` | The cookie wasn't stored: use `localhost` (not an IP) over http, or a trusted HTTPS URL. |
| Port 8000 or 5173 already in use | `lsof -i :8000` and stop the old process. |
