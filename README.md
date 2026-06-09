# OpenFamHub

[![Version](https://img.shields.io/badge/version-0.17-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![CI](https://github.com/vnmyers13/openfamhub/actions/workflows/build.yml/badge.svg)](https://github.com/vnmyers13/openfamhub/actions)

Self-hosted family calendar and organizer with Raspberry Pi wall display support. Designed to run on a NAS or Linux server on your home network.

## Features

- **Shared Family Calendar** — Month, Week, Day, and Agenda views with color-coded sources
- **ICS Feed Integration** — Import calendars from Google, iCloud, TeamSnap, and any ICS URL
- **Family Member Profiles** — Role-based access (admin/member), password and PIN login
- **Wall Display** — Full-screen 1920×1080 kiosk mode on a Raspberry Pi with live clock and 7-day calendar strip
- **PWA Support** — Install on Android/iOS phones as a native app with offline read capability
- **Dashboard** — Time-based greeting, today's events, sync status
- **Real-Time Updates** — WebSocket push to wall displays when events change
- **Automated Backups** — Daily SQLite backup with configurable retention

## Quick Start

### Requirements
- Docker + Docker Compose
- A Linux server or NAS on your local network

### Setup

```bash
git clone https://github.com/vnmyers13/openfamhub.git
cd openfamhub
cp .env.example .env
# Edit .env — set a unique SECRET_KEY, FAMILY_NAME, and TIMEZONE
docker compose up -d
```

Navigate to `https://openfamhub.local` and complete the setup wizard to create your admin account.

### Trust the Certificate

Caddy generates a self-signed CA cert for local HTTPS. Trust it on each device:
- [macOS / Windows / Linux / iOS / Android / Pi OS](./docs/cert-trust.md)

## Wall Display

Set up a dedicated wall display on a Raspberry Pi:

```bash
# On the Pi
curl -fsSL https://raw.githubusercontent.com/vnmyers13/openfamhub/main/scripts/setup-wall-pi.sh | bash
# Reboot — the Pi boots directly to the wall display
```

See the [Wall Screen Setup Guide](./docs/wall-screen-setup.md).

## Adding Calendar Feeds

OpenFamHub imports external calendars via ICS URLs. Supported sources:
- **Google Calendar** — Settings → Integrate Calendar → Export to ICS
- **iCloud** — Use a calendar's public/private ICS link
- **Sports Apps** (TeamSnap, etc.) — ICS export links from the app

## Updates

```bash
git pull origin master
docker compose pull
docker compose up -d
```

## Architecture

```
openfamhub.local
      │
  ┌───┴───┐
  │ Caddy │  (reverse proxy, internal TLS)
  └───┬───┘
      │
  ┌───┴───┐
  │  API  │  Python/FastAPI async, SQLAlchemy 2.0 + aiosqlite
  └───────┘
      │
  ┌───┴───┐
  │  Web  │  React 19 / Vite / TypeScript (served via nginx)
  └───────┘
```

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2.0 async, APScheduler, JWT auth
- **Frontend**: React 19, Vite 8, TypeScript 6, Tailwind CSS 3, Zustand, TanStack Query
- **Database**: SQLite with WAL mode, foreign keys on, Alembic migrations
- **Infra**: Docker Compose, Caddy 2 with internal TLS, GitHub Actions CI

## Docker Images

Images are published to both GitHub Container Registry and Docker Hub:

| Component | Image |
|---|---|
| API | `ghcr.io/vnmyers13/openfamhub/openfamhub-api` / `vnmyers13/openfamhub-api` |
| Web | `ghcr.io/vnmyers13/openfamhub/openfamhub-web` / `vnmyers13/openfamhub-web` |

## Backups

Daily backups are stored in `./data/backups`. To manually restore:

```bash
sqlite3 ./data/db/homehub.db ".restore './data/backups/homehub_YYYY-MM-DD.db'"
```

## Contributing

Report issues or suggest features at [GitHub Issues](https://github.com/vnmyers13/openfamhub/issues).

## License

MIT
