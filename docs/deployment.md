# Deploying OpenFamHub

There are two ways to run OpenFamHub:

| | **Registry (recommended)** | **Build from source** |
|---|---|---|
| Where images are built | Once, on your Mac | On the server itself |
| What the server needs | Docker + one compose file + `.env` | Docker + a full git checkout |
| Commands | `deploy.sh publish`, then `deploy.sh remote <host>` | `deploy.sh setup`, then `deploy.sh deploy` |
| Good for | The `test` VM, production, several servers | A single box, quick local runs |

Everything goes through `scripts/deploy.sh`. Run it from anywhere inside the repo; `scripts/deploy.sh help` lists the commands.

For the `test` VM you normally don't run these by hand: every push to `master` on the primary Forgejo runs CI, which publishes the images and deploys them (see [ci.md](ci.md)). The manual commands below are for other servers, first-time setup, and when CI is unavailable.

**Source repositories.** The primary is Forgejo at `http://192.168.10.2:3002/vernon/OpenFamHub.git` (also reachable as `https://forgejo.vernonmyers.cloud`); CI runs there. `192.168.10.101:3002` and `192.168.10.102:3002` are mirrors, and GitHub (`vnmyers13/openfamhub`) is an off-site copy. Clone or pull from any of them; push to the primary first.

---

## 1. How the test VM is set up

```
 phone / laptop / wall Pi
          │  https://openfamhub.vernonmyers.cloud
          ▼
 ┌──────────────────────┐   your existing Caddy: real certificate, TLS ends here
 │  upstream Caddy      │
 └──────────┬───────────┘
            │  http://<test-vm>:8080
            ▼
 ┌──────────────────────────── test VM: ~/openfamhub ───────────────────────────┐
 │  caddy (Caddyfile.proxy, plain HTTP :80→8080)                                 │
 │     ├── /api/* (incl. /api/wall/ws), /photos/* → api (openfamhub-api)         │
 │     └── everything else             → web  (openfamhub-web:<version>, nginx)  │
 │  ./data/db  ./data/backups  ./data/photos   (bind mounts = all app state)     │
 └───────────────────────────────────────────────────────────────────────────────┘
```

Images come from the Forgejo container registry (`forgejo.vernonmyers.cloud/vernon/openfamhub-{api,web}`).

---

## 2. One-time preparation

### On your Mac

- Install **Docker Desktop** (it includes `buildx`) and **openssl** (macOS has it).
- Set up an SSH login to the server that needs no password: `ssh test` should work. A `Host test` entry in `~/.ssh/config` is the easiest way.
- Log in to the registry with a Forgejo access token. In 1Password, use the Development vault item `forgejo.vernonmyers.cloud` and pipe the concealed password field into Docker so the token is not printed:

  ```bash
  op read 'op://Development/forgejo.vernonmyers.cloud/password' \
    | docker login forgejo.vernonmyers.cloud --username vernon --password-stdin
  ```

  If you create a new token in Forgejo, create it under Forgejo › Settings › Applications with **package: read and write** scope for publishing.

### On the server (the `test` VM)

- Install Docker Engine with the Compose plugin. `docker compose version` must work for the SSH user, so add that user to the `docker` group (`sudo usermod -aG docker $USER`, then log in again).
- If the packages are **private**, log in once so the server can pull them. A token with **package: read** is enough. Use `docker login forgejo.vernonmyers.cloud` on the server and paste the read token when prompted.

- Allow the reverse proxy to reach port **8080**. Ideally only the proxy host can reach it.

### Registry address: HTTPS name vs. LAN IP

Use the HTTPS name (`forgejo.vernonmyers.cloud`). Docker requires HTTPS for registries by default.

The server must resolve `forgejo.vernonmyers.cloud` to the Forgejo host. On the LAN this may need local DNS or an `/etc/hosts` entry; the current Forgejo host is `192.168.10.2`:

```bash
ssh 192.168.10.80 'getent hosts forgejo.vernonmyers.cloud || true'
ssh 192.168.10.80 'printf "192.168.10.2 forgejo.vernonmyers.cloud\n" | sudo tee -a /etc/hosts'
```

Only add the hosts entry if DNS does not already return the correct address.

To use `192.168.10.2:3002` (plain HTTP) instead, set `REGISTRY=192.168.10.2:3002/vernon` in `.env`, and also:

- add `"insecure-registries": ["192.168.10.2:3002"]` to Docker's `daemon.json` on **every** machine that pushes or pulls. In Docker Desktop that's Settings › Docker Engine.
- tell the buildx builder to allow plain HTTP. Remove the builder with `docker buildx rm openfamhub`, then recreate it with a BuildKit config:

  ```toml
  # buildkitd.toml
  [registry."192.168.10.2:3002"]
    http = true
  ```

  ```bash
  docker buildx create --name openfamhub --driver docker-container --config buildkitd.toml
  ```

If a proxy sits in front of Forgejo, make sure it doesn't cap upload size. Image layers can be hundreds of MB; on nginx, set `client_max_body_size 0`. Caddy has no limit by default.

---

## 3. Publish images

```bash
scripts/deploy.sh publish            # version = 0.<VERSION> (repo root)
scripts/deploy.sh publish 0.30-rc1   # or an explicit tag
```

This builds `linux/amd64` and `linux/arm64` images for the API and web app and pushes each one as `:<version>` and `:latest`. Images are tagged `0.<n>` with a matching `v0.<n>` release tag; see [ci.md](ci.md). The build is baked into the images: `/api/health` reports `build` and `commit`, and the setup page, login page, and app sidebar show the same Help & About build info.

- The first run creates a buildx builder named `openfamhub`.
- If the server and the Mac share an architecture, `PLATFORMS=linux/amd64 scripts/deploy.sh publish` is faster.
- The script warns when you publish with uncommitted changes.

Published images appear under Forgejo › your profile › **Packages**. You can link each one to the OpenFamHub repository there.

---

## 4. Deploy to a server

```bash
PUBLIC_URL=https://openfamhub.vernonmyers.cloud scripts/deploy.sh remote test
```

`remote` does the following over SSH:

1. Copies `deploy/compose.yml` and `config/{Caddyfile,Caddyfile.proxy,routes.caddy}` to `~/openfamhub` on the host. Set `REMOTE_DIR` to use another folder.
2. **First run:** creates `~/openfamhub/.env` from `deploy/env.template`, with a freshly generated `SECRET_KEY`, `ALLOWED_ORIGINS=$PUBLIC_URL`, behind-proxy mode on port 8080, and the file locked to mode `600`. Later runs preserve existing secrets/settings and upsert `REGISTRY` plus `OPENFAMHUB_VERSION`.
3. Validates `docker compose config` on the server before pulling images, so missing image variables fail before deployment changes containers.
4. Runs `docker compose pull` and `up -d`.
5. Waits until the API's healthcheck reports healthy.

### First deploy checklist

1. Review the generated settings (e.g. `TIMEZONE` for the backup schedule), then apply them:

   ```bash
   ssh test 'nano ~/openfamhub/.env'
   scripts/deploy.sh remote test
   ```

2. **Back up `SECRET_KEY`** from that file in your password manager.
3. Add the route to your upstream Caddy and reload it:

   ```caddy
   openfamhub.vernonmyers.cloud {
       reverse_proxy <test-vm-ip>:8080
   }
   ```

   No extra configuration is needed: Caddy passes WebSockets (`/api/wall/ws`) through, and it forwards the `X-Forwarded-*` headers.
4. Open `https://openfamhub.vernonmyers.cloud`, complete the setup wizard, and add your calendars.
5. Pair any wall displays under **Admin › Wall displays** (see [wall-screen-setup.md](wall-screen-setup.md)).

> The site must be reached over **HTTPS**. Login cookies are marked `Secure`, so they aren't kept over plain `http://` (except on `localhost`). If logging in "does nothing", check the URL scheme first.

### Useful commands on the server

```bash
cd ~/openfamhub
docker compose ps                  # status (api should be "healthy")
docker compose logs -f api         # API logs (sync errors, startup)
docker compose restart api
docker compose down                # stop (data in ./data is kept)
```

---

## 5. Upgrade and roll back

### Before you upgrade

1. **Take a backup** (section 7). Migrations only move forward, so a backup is the only way back across a schema change.
2. Read the new [CHANGELOG](../CHANGELOG.md) entries and the version notes below.

### Upgrade

| Installed with | Upgrade |
|---|---|
| CI (the `test` VM) | Push to `master` on the primary Forgejo. CI runs the tests, publishes `0.<n>` and deploys it. |
| Registry (`deploy.sh remote`) | `scripts/deploy.sh publish`, then `PUBLIC_URL=https://… scripts/deploy.sh remote <host>`. |
| Build from source (`deploy.sh deploy`) | `scripts/deploy.sh update`: `git pull --ff-only`, rebuild, restart, wait for healthy. |

Every path keeps `.env` and `data/`. A registry deploy only updates `REGISTRY` and `OPENFAMHUB_VERSION` in the server's `.env`.

### After upgrading

- **Migrations run by themselves.** The API applies Alembic migrations at startup. Installs from before 0.30 are recognized, stamped and brought up to date. If the API doesn't become healthy, check `docker compose logs api`.
- **Check the version.** The build number appears under **Help & About** on the setup and login pages and in the sidebar, and in `/api/health` (`version`, `build`, `commit`).
- **Reload wall displays.** A kiosk keeps running the web app it loaded until the page reloads. Reboot the Pi or refresh the page; the service worker can need a second reload.
- **Phones** pick up the new app the next time it's opened.

### Roll back

```bash
scripts/deploy.sh remote test 0.<n>                 # from the Mac: any published version
scripts/deploy.sh server "$HOME/openfamhub" 0.<n>   # on the VM itself
```

Rolling back across a schema change isn't supported: restore the backup taken before the upgrade instead (section 7).

### Version notes

- **0.31–0.73 (review fixes).** No configuration changes. Migration 006 (one family per install) runs at startup. Image tags changed from `0.30.<run>` to one number per commit, `0.<n>`; the current `deploy.sh remote` writes the new tag to the server's `.env`. Repeating calendar subscriptions showed their first occurrence twice; the extra copy disappears at the next sync (or press **Sync Now** in Admin › Calendars). Reload wall displays once to get the midnight rollover and the revocation fix.
- **0.30.** Migrations run automatically at startup; older databases are stamped first. Sign-in moved to avatar + PIN, with a password for admin changes.

#### Upgrading an install from 0.17 or earlier: fix event times

Before 0.18, events created in the web app were stored as local time. Calendar-subscription events were already correct. After upgrading, preview the conversion, then apply it:

```bash
ssh test 'cd ~/openfamhub && docker compose exec api python scripts/fix_event_timezones.py /data/db/homehub.db'
ssh test 'cd ~/openfamhub && docker compose exec api python scripts/fix_event_timezones.py /data/db/homehub.db --apply'
```

The script uses the family timezone chosen in the setup wizard, and it only runs once (re-running is a no-op). A fresh install doesn't need it.

---

## 6. Configuration reference

Settings live in `.env`: in the repo root for build-from-source, or in `~/openfamhub/.env` on a server.

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | *(required)* | Signs login tokens. Generate with `openssl rand -hex 32`. Changing it signs everyone out. Wall pairings aren't affected. |
| `ALLOWED_ORIGINS` | `https://openfamhub.local` | Comma-separated origins allowed by CORS; use the exact public URL. |
| `TIMEZONE` | `UTC` | IANA zone used for `BACKUP_TIME`. Calendar times display in each viewer's browser zone; the family timezone chosen in the setup wizard is used by the 0.17→0.18 time-fix script. |
| `FAMILY_NAME` | `OpenFamHub` | Not used yet: the family name comes from the setup wizard. |
| `DATABASE_URL` | `sqlite+aiosqlite:////data/db/homehub.db` | Path inside the API container. |
| `BACKUP_RETENTION_DAYS` | `30` | Daily backups older than this are pruned. |
| `BACKUP_TIME` | `03:00` | Daily backup time (24h, in `TIMEZONE`). |
| `WALL_IDLE_TIMEOUT_SECONDS` | `300` | Seconds without a touch before the wall switches to its idle (clock) screen. |
| `CADDYFILE` | `Caddyfile` (source) / `Caddyfile.proxy` (server) | `Caddyfile` = Caddy serves HTTPS itself with its internal CA. `Caddyfile.proxy` = plain HTTP behind another proxy. |
| `SITE_ADDRESS` | `openfamhub.local` | Hostname Caddy serves in LAN mode. |
| `HTTP_PORT` / `HTTPS_PORT` | `80`/`443` (source), `8080`/`8443` (server) | Host ports for Caddy. |
| `REGISTRY` | `forgejo.vernonmyers.cloud/vernon` | Registry and owner the images are pushed to and pulled from. |
| `OPENFAMHUB_VERSION` | `0.<VERSION from VERSION>` | Image tag to build, push or run. |

These are also read from the environment of `deploy.sh`: `PLATFORMS` (publish), `PUBLIC_URL` and `REMOTE_DIR` (remote).

---

## 7. Backups and restore

- The API copies the database to `data/backups/homehub_YYYY-MM-DD.db` every day at `BACKUP_TIME`, using SQLite's online-backup API, so the copy is safe while the app is running. Copies older than `BACKUP_RETENTION_DAYS` are deleted.
- All app state is in `data/` (the `db`, `backups` and `photos` folders) plus your `.env`. Copy `data/backups` somewhere else as well, for example a NAS or cloud drive.
- **Before an upgrade**, take a manual backup. Because SQLite runs in WAL mode, do not copy only `homehub.db` while the API is writing. Prefer the app's backup directory, or stop the API before copying the database files:

  ```bash
  ssh test 'cd ~/openfamhub && sh -c '\''set -eu; docker compose stop api; trap "docker compose start api" EXIT; ts=$(date +%F_%H%M); cp data/db/homehub.db data/backups/manual_${ts}.db; [ ! -f data/db/homehub.db-wal ] || cp data/db/homehub.db-wal data/backups/manual_${ts}.db-wal; [ ! -f data/db/homehub.db-shm ] || cp data/db/homehub.db-shm data/backups/manual_${ts}.db-shm'\'''
  ```

  The scheduled backup job uses SQLite's online-backup API and is safe while the app is running.

**Restore:**

```bash
ssh test
cd ~/openfamhub
docker compose stop api
cp data/db/homehub.db data/db/homehub.db.before-restore
cp data/backups/homehub_2026-10-01.db data/db/homehub.db
rm -f data/db/homehub.db-wal data/db/homehub.db-shm   # WAL files belong to the old DB
docker compose start api
```

---

## 8. Build-from-source mode (single machine)

```bash
scripts/deploy.sh setup     # .env from .env.example with a generated SECRET_KEY; creates ./data
scripts/deploy.sh deploy    # docker compose up -d --build, then wait for healthy
scripts/deploy.sh update    # git pull --ff-only, then deploy
scripts/deploy.sh status | logs [service] | stop
```

By default this runs in **LAN mode**: Caddy listens on 80/443 and serves `https://$SITE_ADDRESS` with its internal CA, which each device must trust ([cert-trust.md](cert-trust.md)). To put it behind another proxy instead, set `CADDYFILE=Caddyfile.proxy` and `HTTP_PORT=8080` in `.env`.

Build-from-source deploys stamp images from the checkout too: `scripts/deploy.sh deploy` sets `OPENFAMHUB_VERSION` from the root `VERSION` file (`0.<n>`) and `OPENFAMHUB_COMMIT` from the current git commit before running `docker compose up --build`. To verify what is actually running, check either the setup/login Help & About box before signing in or the health endpoint for the mode you are running:

```bash
curl -ks https://openfamhub.local/api/health        # default LAN mode, adjust SITE_ADDRESS if changed
curl -s http://localhost:8080/api/health            # proxy mode with HTTP_PORT=8080
```

The response should include matching `version`, `build`, and `commit` fields; if git metadata is unavailable, `commit` falls back to `unknown` and is hidden in the UI.

---

## 9. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `publish`: `unauthorized` / `denied` | Run `docker login forgejo.vernonmyers.cloud` with a token that has **package: write**. |
| `remote`: `pull access denied` / `unauthorized` | The packages are private: run `docker login` on the server (token with package: read), or make the packages public in Forgejo. |
| `remote`: image is `/openfamhub-api:` or compose says `REGISTRY` / `OPENFAMHUB_VERSION` is unset | Re-run the current `scripts/deploy.sh remote <host>`; it upserts both variables in the remote `.env` and validates `docker compose config` before pulling. |
| `http: server gave HTTP response to HTTPS client` | You're using the plain-HTTP registry address; see *Registry address* in section 2. |
| `413 Request Entity Too Large` while pushing | A proxy in front of Forgejo limits body size; raise or remove the limit. |
| `exec format error` on the server | The image wasn't built for the server's architecture; publish with the default `PLATFORMS` or include the server's. |
| `remote` waits, then "did not become healthy" | `ssh test 'cd ~/openfamhub && docker compose logs api'`. Usually a missing or invalid `SECRET_KEY`, or a `data/` folder that can't be written. |
| Site loads but login immediately returns to the login page | Not on HTTPS (Secure cookies), or `ALLOWED_ORIGINS` doesn't exactly match the URL. |
| Wall display doesn't update live | The proxy must pass WebSockets on `/api/wall/ws`, and the display must be paired. Caddy does by default; with nginx, add the `Upgrade`/`Connection` headers. Displays still refresh every 15 minutes. |
| A dialog asks an admin for their password | They signed in with a PIN. Admin changes need the password once; it unlocks them for 15 minutes. |
| Sign-in says "Too many attempts" | Failed PIN or password attempts lock that person out for 1, 5, then 15 minutes. Wait, or sign in another way (password vs. PIN). |
| "This display isn't paired" | Create a pairing link under Admin › Wall displays and open it on the display. |
| A calendar feed shows an error | Admin › Calendars › Log shows the message; **Sync Now** retries immediately. |

---

## CI

CI runs on the self-hosted Gitea instance via Gitea Actions. `.gitea/workflows/ci.yml`
runs the backend tests and the frontend lint, unit tests and build on every push and pull request, then
publishes `forgejo.vernonmyers.cloud/vernon/openfamhub-{api,web}` (amd64 + arm64)
and deploys the test VM on pushes to `master`. The one-time runner and secret
setup is in [ci.md](ci.md).
