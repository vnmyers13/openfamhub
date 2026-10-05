# OpenFamHub

![Version](https://img.shields.io/badge/version-0.18-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A self-hosted family calendar and organizer, a home version of a Skylight-style wall calendar. It runs in Docker on a small Linux server, VM or NAS. The family uses it from their phones (it installs as an app), and a Raspberry Pi drives a wall display.

## Features

- **Shared family calendar**: month, week, day and agenda views, with color-coded sources and filters.
- **Calendar subscriptions**: import Google, iCloud, school and sports calendars through their ICS or `webcal://` links. Feeds re-sync on a schedule, and you can trigger a sync from the settings page.
- **Family members**: admin and member roles (a read-only viewer role is planned), with password or PIN login.
- **Wall display**: a full-screen kiosk view (`/wall`) with a clock, a 7-day strip and the family list. Each display is paired once with a revocable device link and stays signed in after that.
- **Live updates**: wall displays refresh as soon as events change, over a WebSocket.
- **Installable app (PWA)**: works on iOS and Android phones and can show cached data offline.
- **Automatic backups**: a daily SQLite backup with configurable retention.

## Quick start (single machine)

Requirements: Docker with Compose, and `openssl`.

```bash
git clone http://192.168.10.2:3002/vernon/OpenFamHub.git openfamhub
cd openfamhub
scripts/deploy.sh setup     # creates .env with a generated SECRET_KEY
scripts/deploy.sh deploy    # builds the images and starts the stack
```

Open `https://openfamhub.local` (point that name at the machine in DNS or `/etc/hosts`) and finish the setup wizard to create the admin account. In this LAN mode Caddy issues its own certificate, so each device has to trust Caddy's root certificate. See [docs/cert-trust.md](docs/cert-trust.md).

## Deploying to a server

The recommended setup is to build images once and publish them to the Forgejo container registry. Servers then only pull and run them:

```bash
scripts/deploy.sh publish                                     # build + push v0.18 (amd64 + arm64)
PUBLIC_URL=https://openfamhub.vernonmyers.cloud \
  scripts/deploy.sh remote test                               # install/upgrade the "test" VM over SSH
```

[docs/deployment.md](docs/deployment.md) covers:

- registry login
- running behind an existing reverse proxy
- LAN-only mode
- upgrades and rollback
- backups and restore
- troubleshooting

## Documentation

| Topic | Where |
|---|---|
| Deploying, upgrading, backups | [docs/deployment.md](docs/deployment.md) |
| How it works (components, data, auth, time zones) | [docs/architecture.md](docs/architecture.md) |
| Developing and testing | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Raspberry Pi wall display | [docs/wall-screen-setup.md](docs/wall-screen-setup.md) |
| Trusting the LAN certificate | [docs/cert-trust.md](docs/cert-trust.md) |
| Known issues / planned fixes | [TODO.md](TODO.md) |
| Feature backlog | [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) |
| Version history | [CHANGELOG.md](CHANGELOG.md) |
| Notes for AI coding agents | [AGENTS.md](AGENTS.md) |

## Adding calendar feeds

In **Admin › Calendars › Add ICS Feed**, paste a calendar's ICS (or `webcal://`) link:

- **Google Calendar**: Settings › *your calendar* › Integrate calendar › *Secret address in iCal format*.
- **iCloud**: Calendar app › Share Calendar › Public Calendar, then copy the link.
- **School and sports apps** (TeamSnap and others): look for "Subscribe" or "Export to calendar".

## Stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2 (async) + SQLite (WAL), APScheduler |
| Web | React 19, Vite, TypeScript, Tailwind CSS, TanStack Query, Zustand, served by nginx |
| Edge | Caddy 2: internal TLS on the LAN, or plain HTTP behind another proxy |
| Packaging | Docker Compose; images published to the Forgejo container registry |

## License

MIT
