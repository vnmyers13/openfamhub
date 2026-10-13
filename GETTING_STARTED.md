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
git config core.hooksPath .githooks    # the pre-commit hook bumps VERSION (release string <release>)
scripts/deploy.sh setup                # .env with a generated SECRET_KEY, ./data folders

# Backend
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt   # includes Pillow, pillow-heif, and static ffmpeg (imageio-ffmpeg) for media

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
cd backend && pytest -v        # add --cov for coverage (CI fails below the floor in .coveragerc)

# Frontend
cd frontend
npm test           # Vitest unit and component tests (npm run test:watch while developing)
npm run test:coverage   # same, with coverage and the CI thresholds; HTML report in coverage/
npm run lint
npm run build      # tsc -b + vite build; fails on type errors

# Release tooling (VERSION hook, release names, renumber, deploy stamping, Trivy and issue scripts)
for t in scripts/tests/*-test.sh; do bash "$t"; done
```

- **Coverage:** the backend is at 96% (CI fails below 93%), the frontend at 94% of statements (thresholds in `vitest.config.ts`). New code comes with tests; raise a threshold when coverage grows, never lower one to get a change through.
- Backend tests use an in-memory SQLite database and need `SECRET_KEY` (read from the repo-root `.env`, or export it).
- Backend: `test_phase1.py` covers time handling, range queries, calendar sources and wall pairing; `test_phase2.py` sign-in, sessions, the admin password gate and event permissions; `test_ical_recurrence.py` and `test_ical_phase3.py` the feed parser (recurrences, EXDATE/RECURRENCE-ID, floating times, DST, storage window); `test_calendar_sync.py` the sync job and adding feeds; `test_calendar_routes.py`, `test_users_api.py`, `test_wall_api.py` the remaining routes; `test_backup.py` the daily backup; `test_media.py` uploads, HEIC/HEIF support, processing (Pillow, ffmpeg), family scoping and wall access; `test_family_settings.py` settings and the sleep schedule; `test_chore_schedule.py` recurrence and the generator; `test_chores_api.py` claiming, completing, points and admin views; `test_todos_routines.py` to-dos and routines; `test_calendar_scoping.py` source and family scoping; `test_single_family.py` one family per install and sign-in scope; `test_ssrf.py` feed fetching; `test_realtime.py` live updates; `test_startup.py` boots the real app (migrations + scheduler) in a subprocess.
- Frontend tests live next to the code (`src/**/*.test.ts[x]`) and run in jsdom with `TZ=America/Detroit`, so date bugs west of UTC show up on every machine. They cover `lib/`, the wall, sign-in, the calendar page, the admin pages and app boot routing. Component tests fake the API with `mockApi()` from `src/test/api.ts` and render with `renderApp()` from `src/test/render.tsx`.
- Run `npm` commands on the Mac itself: `node_modules` contains macOS-native binaries, and a Linux container or VM can't use them.

## Conventions

- **Time:** store UTC, and treat all-day events as dates. Read the *Time handling* section of [docs/architecture.md](docs/architecture.md) before touching dates. On the frontend, use the helpers in `src/lib/dates.ts` instead of `new Date(event.start_dt)`.
- **New tables:** add the model under `backend/app/models/`, import it in `models/__init__.py` and `alembic/env.py`, and add an Alembic migration. Migrations run automatically at startup (`app/core/migrate.py`), so every model change needs one.
- **Commits:** one logical change per commit, with a message that explains *why*.

## Releasing

Every commit is a build, so there is no separate release step for the `test` VM. The full process, including the issue checks and release notes, is in [docs/releasing.md](docs/releasing.md); in short:

1. **Version numbers are automatic.** The `pre-commit` hook bumps `VERSION` (repo root) and the `README.md` badge on every commit; `scripts/release-name` turns the number into the build's name (`0.<n>` up to 0.99, then 1, 1.01, 1.02 …). Never edit `VERSION` by hand.
2. **Rebasing?** If `master` moved while you worked, rebase onto it and run `scripts/renumber origin/master`, so your commits continue the sequence instead of reusing numbers. `scripts/check-version.sh master origin/master HEAD` confirms the result.
3. **Issues.** Before starting a phase, read the pinned **Triage report** issue on Forgejo (or run `python3 scripts/issues.py triage`) and schedule what it lists in TODO.md. When you finish an item, tick its TODO line; CI closes the issue it names.
4. **CHANGELOG.** Entries are keyed by phase or work batch, not by commit. Add user-visible changes under `[Unreleased]`; a release gives the batch its build (`[<release>] - <date>`) and gets notes in `docs/releases/v<release>.md`.
5. Run the tests and checks above.
6. **Push to the primary Forgejo** (`git push forgejo master`). CI runs the checks, publishes `<release>`, tags `v<release>`, deploys to `test`, scans the images and refreshes the Triage report. Then push `master` to GitHub and the mirrors, and push the tag once CI has created it.
7. Check the build on `test` (Help & About or `/api/health`). To promote a checked build to production, use an SSH host alias such as `prod` and run `PUBLIC_URL=https://<prod-url> scripts/deploy.sh promote prod <release>`.

Without CI, publish and deploy by hand: `scripts/deploy.sh publish` (creates and pushes the `v<release>` tag), then `scripts/deploy.sh remote test`.

`release_checklist.json` and `sprint_s*.json` are the original sprint-planning manifests. They're kept for history, and some of their steps (Docker Hub, `deploy.sh staging|production`) are out of date.

## Common problems

| Problem | Fix |
|---|---|
| `pydantic ValidationError: secret_key field required` | `.env` is missing or has no `SECRET_KEY`: run `scripts/deploy.sh setup`. |
| `Cannot find native binding` (rolldown) when building the web image | An old checkout without `frontend/.dockerignore`; pull the latest code. |
| Login works but you're sent straight back to `/login` | The cookie wasn't stored: use `localhost` (not an IP) over http, or a trusted HTTPS URL. |
| Port 8000 or 5173 already in use | `lsof -i :8000` and stop the old process. |
