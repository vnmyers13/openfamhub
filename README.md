# OpenFamHub

![Version](https://img.shields.io/badge/version-0.80-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A self-hosted family calendar and organizer, a home version of a Skylight-style wall calendar. It runs in Docker on a small Linux server, VM or NAS. The family uses it from their phones (it installs as an app), and a Raspberry Pi drives a wall display.

## Features

- **Shared family calendar**: month, week, day and agenda views, with color-coded sources and filters.
- **Calendar subscriptions**: import Google, iCloud, school and sports calendars through their ICS or `webcal://` links. Feeds re-sync on a schedule, and you can trigger a sync from the settings page.
- **Family members**: tap-your-avatar sign-in with a PIN; admin, member and read-only viewer roles; admin changes need a password, and admin pages are hidden from everyone else.
- **Wall display**: a full-screen kiosk view (`/wall`) with a clock, a 7-day strip that rolls over at midnight, and the family list. Each display is paired once with a revocable device link and stays signed in after that.
- **Live updates**: wall displays refresh as soon as events change, over a WebSocket.
- **Installable app (PWA)**: works on iOS and Android phones and can show cached data offline.
- **Automatic backups**: a daily SQLite backup with configurable retention.

## Quick start (single machine)

Requirements: Docker with Compose, `git` and `openssl`.

```bash
git clone http://192.168.10.2:3002/vernon/OpenFamHub.git openfamhub
cd openfamhub
scripts/deploy.sh setup     # creates .env with a generated SECRET_KEY
scripts/deploy.sh deploy    # builds the images and starts the stack
```

Open `https://openfamhub.local` (point that name at the machine in DNS or `/etc/hosts`) and finish the setup wizard to create the admin account. In this LAN mode Caddy issues its own certificate, so each device has to trust Caddy's root certificate. See [docs/cert-trust.md](docs/cert-trust.md).

## Deploying to a server

The recommended setup is to build images once and publish them to the Forgejo container registry. Servers then only pull and run them.

**Normally CI does this for you:** every push to `master` on the primary Forgejo (`192.168.10.2:3002`) runs the tests, publishes the images as `0.<n>` and deploys them to the `test` VM ([docs/ci.md](docs/ci.md)). The manual commands are:

```bash
scripts/deploy.sh publish                                     # build + push v0.<n> (amd64 + arm64)
PUBLIC_URL=https://openfamhub.vernonmyers.cloud \
  scripts/deploy.sh remote test                               # install/upgrade the "test" VM over SSH
```

Registry login can use the 1Password Development item `forgejo.vernonmyers.cloud`; the full guide also covers LAN DNS for the registry hostname and server-side pull credentials.

[docs/deployment.md](docs/deployment.md) covers:

- registry login
- running behind an existing reverse proxy
- LAN-only mode
- upgrades and rollback
- backups and restore
- troubleshooting

## Upgrading

Back up first ([backups](docs/deployment.md#7-backups-and-restore)), then use the path that matches how you installed:

| Installed with | Upgrade with |
|---|---|
| CI (the `test` VM) | Push to `master` on the primary Forgejo; CI publishes and deploys. |
| `deploy.sh remote` (registry) | `scripts/deploy.sh publish`, then `scripts/deploy.sh remote <host>`. Add a version to roll back: `scripts/deploy.sh remote <host> 0.<n>`. |
| `deploy.sh deploy` (build from source) | `scripts/deploy.sh update` (`git pull --ff-only`, then rebuild and restart). |

Database migrations run automatically when the API starts, and `.env` settings are kept. Afterwards, check the build number under **Help & About** (on the login page or in the sidebar) or at `/api/health`, and reload wall displays so they pick up the new web app. Version-specific notes are in [docs/deployment.md](docs/deployment.md#5-upgrade-and-roll-back) and [CHANGELOG.md](CHANGELOG.md).

## Documentation

| Topic | Where |
|---|---|
| Deploying, upgrading, backups | [docs/deployment.md](docs/deployment.md) |
| CI: tests, publish and deploy on `master` | [docs/ci.md](docs/ci.md) |
| How it works (components, data, auth, time zones) | [docs/architecture.md](docs/architecture.md) |
| Developing and testing | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Raspberry Pi wall display | [docs/wall-screen-setup.md](docs/wall-screen-setup.md) |
| Trusting the LAN certificate | [docs/cert-trust.md](docs/cert-trust.md) |
| Security notes (feed fetching, live updates) | [docs/security-notes.md](docs/security-notes.md) |
| Roadmap and task list | [TODO.md](TODO.md) |
| Older idea list (superseded by TODO.md) | [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) |
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

PWA PNG icons (180/192/512, maskable) are generated from the source SVGs in `frontend/public/icons/` with `npm run icons` (from `frontend/`).

## License

MIT
