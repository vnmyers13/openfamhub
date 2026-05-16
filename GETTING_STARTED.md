# OpenFamHub — Getting Started Guide
**Project:** vnmyers13/openfamhub
**Version:** 0.10
**Last Updated:** 2026-05-03

This document is the single entry point for starting development. Read it completely before running any command.

---

## 1. What You're Building

OpenFamHub is a self-hosted family calendar and organisation hub. It runs on a Linux server/NAS at `openfamhub.local` on your home network. A Raspberry Pi runs Chromium in kiosk mode pointing at the wall display (`/wall`). Family members install it as a PWA on their phones.

**MVP scope:** Shared family calendar + ICS feed imports (sports, school) + wall 7-day display + mobile PWA. No Google/Apple OAuth — external calendars import via ICS URL.

---

## 2. Decisions Already Made

| Decision | Value |
|---|---|
| GitHub repo | `vnmyers13/openfamhub` |
| Docker Hub | `vnmyers13/openfamhub-api`, `vnmyers13/openfamhub-web` |
| Starting version | `0.01` |
| Production server | `openfamhub.local` (deploy user: `deploy`) |
| Staging server | `homehub-staging.local` |
| Wall display | 1920×1080, Raspberry Pi, Chromium kiosk |
| Calendar sync | ICS feed URLs only (no OAuth) |
| Data storage | NAS share (NFS or SMB, both documented) |
| Theme default | Dark mode |
| Notifications | Email (SMTP) + Discord webhook |
| Language | English only |
| User switching | Quick-switch on shared devices (wall, kitchen tablet) |
| Dev machine | Mac Intel + Docker Desktop |

---

## 3. Prerequisites — Install These First

### On your Mac (development machine)

```bash
# Homebrew (if not installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Core tools
brew install git python@3.12 node@20 docker gh

# Docker Desktop (UI + daemon)
# Download from: https://www.docker.com/products/docker-desktop/
# Start Docker Desktop before running any docker commands

# Verify
git --version        # 2.x
python3.12 --version # 3.12.x
node --version       # 20.x
docker --version     # 24.x+
gh --version         # 2.x
```

### GitHub CLI Authentication

```bash
gh auth login
# Choose: GitHub.com → HTTPS → Yes (authenticate Git) → Login with browser
gh auth status  # Should show: Logged in to github.com as vnmyers13
```

### Docker Hub Login

```bash
docker login --username vnmyers13
# Enter your Docker Hub password or access token when prompted
# Generate an access token at: https://hub.docker.com/settings/security
```

---

## 4. Create the GitHub Repository

```bash
# Create the public repo
gh repo create vnmyers13/openfamhub --public --description "Self-hosted family calendar and organisation hub"

# Clone it
git clone https://github.com/vnmyers13/openfamhub.git
cd OpenFamHub
```

---

## 5. Project Setup — Day One Commands

Run these in order exactly once:

```bash
# --- Backend venv (REQUIRED before any Python work) ---
cd OpenFamHub
python3.12 -m venv backend/.venv
source backend/.venv/bin/activate
# Your prompt should now show (.venv)
# Verify:
which python | grep .venv && echo "venv OK"

# --- Copy environment file ---
cp .env.example .env
# Open .env and fill in:
#   FAMILY_NAME=       (your family name)
#   TIMEZONE=          (e.g. America/Chicago)
#   SECRET_KEY=        (run: openssl rand -hex 32)
# Leave all other fields as-is for now

# --- Trust the Caddy self-signed cert on your Mac ---
# After first docker compose up, run:
docker compose exec caddy cat /data/caddy/pki/authorities/local/root.crt > caddy-root.crt
# Double-click caddy-root.crt → Keychain Access → Trust → Always Trust
# See docs/cert-trust.md for full instructions including iPhone/iPad

# --- Boot the stack ---
docker compose up -d --build
docker compose ps        # All three services should show "running"
docker compose logs api  # Watch for "Application startup complete"

# --- Verify ---
curl -sk https://openfamhub.local/api/health
# Expected: {"status":"ok","version":"0.01"}
```

---

## 6. Development Workflow

### Always activate the venv first

```bash
cd OpenFamHub
source backend/.venv/bin/activate
# Every terminal session that touches Python needs this
```

### Hot reload during development

```bash
# Backend (hot reload, runs outside Docker)
source backend/.venv/bin/activate
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend (Vite dev server with HMR)
cd frontend && npm run dev
# Access at https://openfamhub.local (proxied through Caddy)
# Or directly at http://localhost:5173 (Vite, no HTTPS)
```

### Run tests

```bash
source backend/.venv/bin/activate
cd backend && pytest tests/ -v
```

### Check code before committing

```bash
source backend/.venv/bin/activate
# Python linting
pip install ruff  # one-time
ruff check backend/

# Frontend type check
cd frontend && npm run build  # fails on TypeScript errors
```

---

## 7. Sprint Execution Order

Work through the sprint JSON files in order. Each is self-contained with context, tasks, shell commands, and acceptance checks.

| File | Sprint | Duration | Goal |
|---|---|---|---|
| `sprint_s1.json` | S1 — Infrastructure | Week 1 | Stack boots at openfamhub.local |
| `sprint_s2.json` | S2 — Auth & Profiles | Week 2 | Family can log in |
| `sprint_s3.json` | S3 — Internal Calendar | Week 3 | Events visible in all views |
| `sprint_s4.json` | S4 — ICS Feed Sync | Week 4 | Sports/school feeds working |
| `sprint_s5.json` | S5 — Wall + PWA | Weeks 5–6 | Wall display live, PWA installed |
| `sprint_s6.json` | S6 — Hardening | Week 7 | Tests pass, deploy script works |

**Rule:** Do not start a sprint until the previous sprint's exit goal is verified passing on actual hardware.

---

## 8. Secrets You Need Before Starting Each Sprint

### Before Sprint 1 (needed immediately)

```bash
# Generate SECRET_KEY
openssl rand -hex 32
# Paste into .env as SECRET_KEY=

# Store it in your password manager NOW
# Losing it means re-connecting all calendar sources after a restore
```

### Before Sprint 4 (ICS feeds — no credentials needed)

ICS feeds are public URLs — no registration required. Test with:
- US Holidays: `https://www.mozilla.org/media/caldata/calendars/holidays/US.ics`
- Your child's sports league export URL (usually in the team app settings)

### Before Release (Docker Hub + Discord)

```bash
# Docker Hub access token
# 1. Go to: https://hub.docker.com/settings/security
# 2. New Access Token → name: openfamhub-deploy → Read/Write scope
# 3. Add to .env: (do not commit)
#    DOCKERHUB_TOKEN=your_token_here

# Discord webhook
# 1. Go to your Discord server → channel settings → Integrations → Webhooks
# 2. New Webhook → copy URL
# 3. Add to .env:
#    DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
```

---

## 9. Server Setup (Production)

Run once on the Linux production server before first deploy:

```bash
# On the server (SSH in first)
curl -fsSL https://raw.githubusercontent.com/vnmyers13/openfamhub/main/scripts/setup-server.sh | bash

# Then from your Mac — copy your SSH key
ssh-keygen -t ed25519 -C "openfamhub-deploy"
ssh-copy-id deploy@openfamhub.local

# Test the connection
ssh deploy@openfamhub.local "echo SSH OK"

# First deploy
./scripts/deploy.sh production
```

Full server setup instructions including NAS mount (NFS and SMB): `docs/server-setup.md`

---

## 10. Wall Display Setup (Raspberry Pi)

After the server is running and accessible at `openfamhub.local`:

```bash
# SSH into the Pi
ssh pi@raspberrypi.local

# Run the kiosk setup script
curl -fsSL https://raw.githubusercontent.com/vnmyers13/openfamhub/main/scripts/setup-wall-pi.sh | bash

# Trust the cert (see docs/cert-trust.md — Pi section)
# Then reboot
sudo reboot
```

The Pi will boot directly to `https://openfamhub.local/wall`.

---

## 11. Releasing a New Version

The full release process is in `release_checklist.json`. Quick summary:

```bash
# 1. Check GitHub issues → update TODO.md
# 2. Run release checklist Phase P2 to bump version
# 3. Fill in CHANGELOG.md
# 4. Run all tests (Phase P4) — all must pass
# 5. Commit + tag (Phase P5)
# 6. Push to GitHub + wait for CI (Phase P6)
# 7. Deploy to staging: ./scripts/deploy.sh staging
# 8. Verify staging works
# 9. Deploy to production: ./scripts/deploy.sh production
# 10. Push Docker images to Docker Hub (Phase P7)
# 11. Housekeeping (Phase P8)
```

---

## 12. File Reference

```
OpenFamHub/
├── sprint_s1.json          ← Start here — agent task manifest for Sprint 1
├── sprint_s2.json          ← Sprint 2 tasks
├── sprint_s3.json          ← Sprint 3 tasks
├── sprint_s4.json          ← Sprint 4 tasks
├── sprint_s5.json          ← Sprint 5 tasks
├── sprint_s6.json          ← Sprint 6 tasks (includes deploy script + notifications)
├── release_checklist.json  ← Full release process (run after every sprint)
├── TODO.md                 ← Known bugs (auto-updated by release checklist)
├── FUTURE_ENHANCEMENTS.md  ← Feature backlog
├── CHANGELOG.md            ← Version history
├── .env.example            ← All environment variables documented
├── .env                    ← Your secrets (NEVER commit this)
├── docker-compose.yml      ← Production stack (api + web + caddy)
├── docker-compose.staging.yml ← Staging override
├── backend/
│   ├── .venv/              ← Python virtual environment (never commit)
│   ├── requirements.txt    ← Python dependencies
│   ├── Dockerfile
│   └── app/
├── frontend/
│   ├── node_modules/       ← Never commit
│   ├── package.json
│   └── src/
├── config/
│   └── Caddyfile
├── data/                   ← Runtime data (never commit)
│   ├── db/
│   ├── photos/
│   └── backups/
├── scripts/
│   ├── deploy.sh           ← Deploy to staging or production
│   ├── setup-server.sh     ← First-time server setup
│   └── setup-wall-pi.sh    ← Pi kiosk configuration
└── docs/
    ├── cert-trust.md       ← Trust Caddy cert on all devices
    ├── server-setup.md     ← NAS mount (NFS + SMB) + server config
    ├── wall-screen-setup.md ← Pi kiosk setup guide
    ├── test-history.md     ← Auto-updated test results
    ├── releases/           ← Per-release summaries
    └── mvp-hardware-checklist.md
```

---

## 13. Common Problems

| Problem | Fix |
|---|---|
| `venv not active` error | Run `source backend/.venv/bin/activate` |
| `https://openfamhub.local` cert warning | Follow `docs/cert-trust.md` for your device |
| Docker images not found | Run `docker compose build` first |
| Alembic `No such table` | Run `alembic upgrade head` with venv active |
| Port 80/443 already in use | Stop any other web server: `sudo lsof -i :80` |
| NAS mount permission denied | Check `uid=deploy,gid=deploy` in fstab entry |
| Pi shows cert error on `/wall` | Trust cert on Pi: `docs/cert-trust.md` Pi section |
| Push notifications not working | HTTPS required — check cert is trusted on device |

---

*This guide is updated automatically when all sprint files are regenerated.*
*For questions: https://github.com/vnmyers13/openfamhub/issues*
