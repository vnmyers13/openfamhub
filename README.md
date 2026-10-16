# OpenFamHub

![Version](https://img.shields.io/badge/version-1.62-blue)
![License](https://img.shields.io/badge/license-MIT-green)

A self-hosted family calendar and organizer, a home version of a Skylight-style wall calendar. It runs in Docker on a small Linux server, VM or NAS. The family uses it from their phones (it installs as an app), and a Raspberry Pi drives a wall display.

## Features

- **Shared family calendar**: month, week, day and agenda views, with color-coded sources and filters, birthdays, and "everyone" or "just me".
- **Calendar subscriptions**: Google, iCloud, school and sports calendars through their ICS or `webcal://` links, re-synced on a schedule. Admins can rename, recolor, pause or change a feed's link.
- **Family members**: tap-your-avatar sign-in with a PIN; admin, member and read-only viewer roles; admin changes need a password. Everyone can change their own name, color and avatar.
- **Wall display**: a full-screen kiosk (`/wall`) on a Raspberry Pi or tablet, paired once with a revocable link. It shows the family's own dashboard pages (events, chores, routines, meals, weather, announcements, progress, birthdays, a clock), turning every so often under a header with the time and any extra clocks. Kids can tick off routine steps on it. See [Setting up a wall display](#setting-up-a-wall-display-raspberry-pi).
- **Chores, routines and to-dos**: repeating chores assigned to someone or up for grabs, points for finishing them, morning and bedtime routines with a countdown, and a shared to-do list.
- **Rewards**: spend points on rewards (instantly, or with a parent's yes), badges and streaks, and a weekly allowance.
- **Meals**: a weekly meal plan, recipes (import from a link, paste, or a photo of the recipe), a shopping list built from the plan (or scanned from a photo of a paper list), and a pantry.
- **Notifications**: reminders on your phone, by ntfy or by email: before events, a morning list of your chores and to-dos, birthdays, pantry use-by dates, allowance paid, and reward requests for parents (see [Notifications](#notifications)).
- **Books, announcements and weather** on Home and the wall.
- **Works offline**: the app (a PWA, installable on iOS and Android) opens without a connection, and chores, to-dos, the shopping list and the meal plan can be changed offline and sync later.
- **Photo and video slideshow**: the wall shows family photos and videos when nobody is using it. Location data is removed on upload.
- **Sleep schedule**: wall screens go dark overnight (in the family's timezone) and wake on touch; no notifications are sent then.
- **Live updates** over a WebSocket, and **backups**: a daily SQLite snapshot plus `backup-offhost.sh` to copy snapshots and photos to a NAS.

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

**Normally CI does this for you:** every push to `master` on the primary Forgejo (`192.168.10.2:3002`) runs the tests, publishes the images as `<release>` and deploys them to the `test` VM ([docs/ci.md](docs/ci.md)). The manual commands are:

```bash
scripts/deploy.sh publish                                     # build + push v<release> (amd64 + arm64)
PUBLIC_URL=https://openfamhub.vernonmyers.cloud \
  scripts/deploy.sh remote test                               # install/upgrade the "test" VM over SSH
```

Production is a manual promotion after checking a build on `test`:

```bash
PUBLIC_URL=https://<prod-url> scripts/deploy.sh promote prod <release>
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
| Production promotion | Check the build on `test`, then `PUBLIC_URL=https://<prod-url> scripts/deploy.sh promote prod <release>`. |
| `deploy.sh remote` (registry) | `scripts/deploy.sh publish`, then `scripts/deploy.sh remote <host>`. Add a version to roll back: `scripts/deploy.sh remote <host> <release>`. |
| `deploy.sh deploy` (build from source) | `scripts/deploy.sh update` (`git pull --ff-only`, then rebuild and restart). |

Database migrations run automatically when the API starts, and `.env` settings are kept. Afterwards, check the build number under **Help & About** (on the login page or in the sidebar) or at `/api/health`, and reload wall displays so they pick up the new web app. Version-specific notes are in the [release notes](docs/releases/) (upgrading from 0.30: [Release 1.01](docs/releases/v1.01.md#upgrading-from-030)), [docs/deployment.md](docs/deployment.md#version-notes) and [CHANGELOG.md](CHANGELOG.md). Builds are named `0.<n>` up to 0.99, then 1, 1.01, 1.02 …

## Documentation

| Topic | Where |
|---|---|
| Deploying, upgrading, backups | [docs/deployment.md](docs/deployment.md) |
| CI: tests, publish, deploy, Trivy scan and issue sync on `master` | [docs/ci.md](docs/ci.md) |
| Releasing: phases, issues and TODO.md, release names | [docs/releasing.md](docs/releasing.md) |
| Release notes (latest: [Release 1.41](docs/releases/v1.41.md)) and change log | [docs/releases/](docs/releases/), [CHANGELOG.md](CHANGELOG.md) |
| How it works (components, data, auth, time zones) | [docs/architecture.md](docs/architecture.md) |
| Developing and testing | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Raspberry Pi wall display | [docs/wall-screen-setup.md](docs/wall-screen-setup.md) |
| Trusting the LAN certificate | [docs/cert-trust.md](docs/cert-trust.md) |
| Security notes (feed fetching, live updates) | [docs/security-notes.md](docs/security-notes.md) |
| Roadmap and task list | [TODO.md](TODO.md) |
| Older idea list (superseded by TODO.md) | [FUTURE_ENHANCEMENTS.md](FUTURE_ENHANCEMENTS.md) |
| Version history | [CHANGELOG.md](CHANGELOG.md) |
| Notes for AI coding agents | [AGENTS.md](AGENTS.md) |

## Setting up a wall display (Raspberry Pi)

Any Raspberry Pi with HDMI (a Pi 4 or 5 is smoothest) and a screen, ideally a touch screen, makes a wall display. The short version (the full guide, with troubleshooting, is [docs/wall-screen-setup.md](docs/wall-screen-setup.md)):

1. **Install Raspberry Pi OS (64-bit) with desktop** using [Raspberry Pi Imager](https://www.raspberrypi.com/software/). Set Wi-Fi, a user and SSH in the Imager's settings.
2. **Create a pairing link.** On a phone or computer, sign in as an admin, open **Admin › Wall displays**, enter a name ("Kitchen") and press **Create pairing link**. The link is shown once, so copy it.
3. **Run the kiosk setup on the Pi** with that link. It installs Chromium, opens the wall full screen at every boot, hides the cursor and keeps the screen from blanking:
   ```bash
   scp scripts/setup-wall-pi.sh <user>@<pi-address>:
   ssh <user>@<pi-address>
   chmod +x setup-wall-pi.sh
   sudo ./setup-wall-pi.sh "https://openfamhub.example/wall?token=..."
   sudo reboot
   ```
   It works on Bookworm (Wayland) and Bullseye, and is safe to run again (for example with a new link).
4. **LAN mode only** (`https://openfamhub.local` with Caddy's own certificate): make the Pi trust Caddy's root certificate first ([docs/cert-trust.md](docs/cert-trust.md)), or Chromium shows a certificate warning. Skip this behind a reverse proxy with a real certificate.
5. **Arrange what it shows** from any phone: **Home › Customize › Edit family wall** sets the pages, their cards and how long each stays up. Every wall follows the same layout. The time, the sleep schedule and **Other clocks on the wall** are in **Admin › Settings**.

To retire a display, press **Unpair** under **Admin › Wall displays**; it goes back to the pairing screen at its next refresh.

## Home Assistant

To show your Home Assistant on Home and the wall, make a long-lived access token in Home Assistant (your profile › Security › Long-lived access tokens), then enter its address and the token under **Admin › Settings › Home Assistant** and press **Test connection**. Or put them in `.env` (a value there wins and locks the field in the app):

```
HA_URL=http://homeassistant.local:8123
HA_TOKEN=<the token>
```

Then, on the same page, pick up to 24 entities (lights, switches, fans, toggles, scenes, scripts, thermostats, sensors) and, if you like, a scene or script for each routine with a start time. Add the **Smart home** card to a Home page (Customize) or a wall page. Members and admins can switch things from Home (on/off, brightness, run a scene, thermostat temperature and mode); viewers and the wall only see them. Numeric sensors show a 24-hour trend line. The API container must be able to reach `HA_URL`.

## Notifications

Each person turns notifications on in **My settings › Notifications** on each phone or computer they want them on, and chooses which reminders they get: before calendar events (off until chosen: events they added, or all family events, 5 to 60 minutes before), a morning list of their chores and to-dos, the morning before someone's birthday, pantry food reaching its use-by date, their weekly allowance being paid, and, for admins, reward requests waiting for a yes. Wellness reminders (drink water every few hours, a daily breathing pause) are off until someone turns them on, and never go by email. Nothing is sent during the wall's sleep hours.

- **ntfy and email, too:** set them up under **Admin › Settings › Notifications** (with **Send me a test**), or set `NTFY_URL` (e.g. `https://ntfy.sh` or your own ntfy server, plus `NTFY_TOKEN` if it needs one) and/or `SMTP_HOST`, `SMTP_PORT`, `SMTP_SECURITY`, `SMTP_USERNAME`, `SMTP_PASSWORD` and `SMTP_FROM` in `.env`, then restart. Each person then adds their own ntfy topic or email address in My settings › Notifications; they don't need a phone with notifications turned on.
- Web Push needs no account: the server makes its own keys. The server must be able to reach the browsers' push services over HTTPS (`fcm.googleapis.com`, `updates.push.services.mozilla.com`, `*.notify.windows.com`, `web.push.apple.com`).
- The app must be opened over HTTPS (it always is through Caddy).
- **iPhone and iPad**: iOS 16.4 or later, and only once OpenFamHub is on the Home Screen (Safari › Share › Add to Home Screen) and opened from there.

## Adding calendar feeds

In **Admin › Calendars › Add ICS Feed**, paste a calendar's ICS (or `webcal://`) link:

- **Google Calendar**: Settings › *your calendar* › Integrate calendar › *Secret address in iCal format*.
- **iCloud**: Calendar app › Share Calendar › Public Calendar, then copy the link.
- **School and sports apps** (TeamSnap and others): look for "Subscribe" or "Export to calendar".

To change a feed later, press **Edit** on it: rename it, recolor it, change how often it syncs, pause it, or paste a new link. A new link is checked first and only saved if it works; its events then replace the old link's.

## Stack

| Layer | Technology |
|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2 (async) + SQLite (WAL), APScheduler |
| Web | React 19, Vite, TypeScript, Tailwind CSS, TanStack Query, Zustand, served by nginx |
| Edge | Caddy 2: internal TLS on the LAN, or plain HTTP behind another proxy |
| Packaging | Docker Compose; images published to the Forgejo container registry |

Frontend development needs **Node 24** (or 22.22+): jsdom and Vitest refuse Node 20, so `npm test` fails on it. `frontend/.nvmrc` pins 24 (`nvm use` in `frontend/`); `package.json` `engines` states the range.

PWA PNG icons (180/192/512, maskable) are generated from the source SVGs in `frontend/public/icons/` with `npm run icons` (from `frontend/`).

## License

MIT
