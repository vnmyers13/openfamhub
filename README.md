# OpenFamHub

Self-hosted family calendar and organisation hub.

**Version:** 0.12

## Quick Start

```bash
cp .env.example .env
# Edit .env with your settings
docker compose up -d
```

Visit https://homehub.local

## Features

- Shared family calendar with ICS feed subscriptions
- Wall display at /wall: full-screen 7-day calendar
- PWA support for mobile devices
- Role-based family member profiles
- Daily automated SQLite backups

## Architecture

- **Backend:** Python 3.12 + FastAPI + SQLAlchemy 2.0 async + SQLite
- **Frontend:** React 19 + TypeScript + Vite + Tailwind CSS + PWA
- **Infrastructure:** Docker Compose + Caddy 2 (TLS)

## License

MIT
