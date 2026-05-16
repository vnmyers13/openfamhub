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
