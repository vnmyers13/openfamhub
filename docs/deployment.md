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
          │  https://openfamhub.vernonmyers.cloud (DNS → upstream Caddy at 192.168.10.2)
          ▼
 ┌──────────────────────┐   your existing Caddy: real certificate, TLS ends here
 │  upstream Caddy      │
 └──────────┬───────────┘
            │  http://192.168.10.80:8080
            ▼
 ┌──────────────────────────── test VM: ~/openfamhub ───────────────────────────┐
 │  caddy (Caddyfile.proxy, plain HTTP :80→8080)                                 │
 │     ├── /api/* (incl. /api/wall/ws), /photos/* → api (openfamhub-api)         │
 │     └── everything else             → web  (openfamhub-web:<version>, nginx)  │
 │  ./data/db  ./data/backups  ./data/photos   (bind mounts = all app state)     │
 └───────────────────────────────────────────────────────────────────────────────┘
```

The upstream Caddy host is `192.168.10.2`, and it forwards `openfamhub.vernonmyers.cloud` to the `test` VM at `192.168.10.80:8080`. Clients must resolve `openfamhub.vernonmyers.cloud` to the upstream Caddy host, not directly to the test VM or any retired app host. Images come from the Forgejo container registry (`forgejo.vernonmyers.cloud/vernon/openfamhub-{api,web}`).

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

This builds `linux/amd64` and `linux/arm64` images for the API and web app and pushes each one as `:<version>` and `:latest`. Images are tagged `<release>` with a matching `v<release>` release tag; see [ci.md](ci.md). The build is baked into the images: `/api/health` reports `build` and `commit`, and the setup page, login page, and app sidebar show the same Help & About build info.

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
3. Add the route to your upstream Caddy on `192.168.10.2` and reload it:

   ```caddy
   openfamhub.vernonmyers.cloud {
       reverse_proxy <test-vm-ip>:8080
   }
   ```

   No extra configuration is needed: Caddy passes WebSockets (`/api/wall/ws`) through, and it forwards the `X-Forwarded-*` headers. Local DNS or Twingate resource aliases should point `openfamhub.vernonmyers.cloud` at `192.168.10.2`; stale DNS pointing at any other LAN host can serve an older build or fail TLS before traffic reaches the test VM.
4. Open `https://openfamhub.vernonmyers.cloud`, complete the setup wizard, and add your calendars.
5. Pair any wall displays under **Admin › Wall displays** (see [wall-screen-setup.md](wall-screen-setup.md)).

> The site must be reached over **HTTPS**. Login cookies are marked `Secure`, so they aren't kept over plain `http://` (except on `localhost`). If logging in "does nothing", check the URL scheme first.

### Production promotion

CI deploys only to the `test` VM. Production is a deliberate promotion of a build
you have already checked on `test`. Create an SSH host alias such as `prod` for the
production server, make sure that server can pull from the Forgejo registry, then run:

```bash
PUBLIC_URL=https://<prod-url> scripts/deploy.sh promote prod <release>
```

`promote` uses the same deploy bundle and health checks as `remote`, but it requires
the `<release>` argument and rejects `latest`. That keeps production pinned to a
specific checked build instead of whatever build the local checkout would resolve by
default. To re-promote or roll back, run the same command with another published
release.

When the production server is stood up, update these operator-owned values:

1. **SSH config:** add a `Host prod` entry in `~/.ssh/config` with the production
   server's real IP/DNS name and deploy user.
2. **Upstream reverse proxy:** add the production public hostname and point it at
   the production server's `:8080` port, the same way `test` points at
   `192.168.10.80:8080`.
3. **Promotion command:** replace `<prod-url>` in the examples with the production
   HTTPS URL, then run `PUBLIC_URL=https://<prod-url> scripts/deploy.sh promote prod <release>`.
4. **Docs after the first successful deploy:** replace the placeholders in this
   section (and the short examples in `README.md` and `GETTING_STARTED.md`) with the
   production hostname if you want the repo to carry the real prod URL.

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
| CI (the `test` VM) | Push to `master` on the primary Forgejo. CI runs the tests, publishes `<release>` and deploys it. |
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
scripts/deploy.sh remote test <release>                 # from the Mac: any published version
scripts/deploy.sh server "$HOME/openfamhub" <release>   # on the VM itself
```

Rolling back across a schema change isn't supported: restore the backup taken before the upgrade instead (section 7).

### Version notes

Release notes for each release are in [docs/releases/](releases/) (latest: [Release 1.01](releases/v1.01.md)). Per-build notes:

- **0.95–1.01 (CI and release process).** No app or configuration changes. Build 1 failed to publish (no images or tag); 1.01 is the first 1.x build. Build 100 is named **1** (then 1.01, 1.02 …), so image tags and git tags go `0.99`, `1`, `1.01`; update anything that pins `OPENFAMHUB_VERSION` or matches `v0.*`. CI scans each build with Trivy and keeps Forgejo issues in step with TODO.md (optional `ISSUES_TOKEN` secret; see [ci.md](ci.md)).
- **0.90–0.94 (Phase 5, chores).** Migration 008 (chores, routines, to-dos, points ledger) runs at startup; no configuration changes. New: **Chores** in the menu (today's chores, to-dos, routines, points; admins set chores and routines up under Manage). A new hourly job creates chore instances. Reload wall displays once to get routine countdowns.
- **0.84–0.88 (Phase 3b, wall essentials).** Migration 007 (media) runs at startup. The API image is about 70 MB larger (ffmpeg and Pillow, for photos and videos). New: **Photos** (members upload photos and videos; the idle wall shows them), **Admin › Settings** (family name, timezone, wall sleep schedule) and `backup-offhost.sh` (put in `~/openfamhub` by `deploy.sh remote`; set up the [off-host copy](#off-host-copies-nas)). The unauthenticated `/photos/…` route is gone: media is served only to signed-in members and paired walls. If a reverse proxy in front of OpenFamHub limits request size (nginx's default is 1 MB), raise it for video uploads (e.g. `client_max_body_size 500m`); Caddy has no limit. Reload wall displays once.
- **0.75–0.82 (Phase 3, iCal correctness).** No configuration changes. Calendar subscriptions now honour cancelled and moved instances, keep wall-clock times across DST changes, and store only 90 days back to a year ahead (older synced events are removed at the next sync). Times without a timezone in a feed are read in the **family timezone**. Installs set up before 0.78 defaulted that to UTC: check it under **Admin › Settings** (from 0.87), then press **Sync Now** on each calendar. On 0.82–0.86, before that page existed, check and set it from the server:

  ```bash
  ssh test 'cd ~/openfamhub && docker compose exec api python -c "import sqlite3; c = sqlite3.connect(\"/data/db/homehub.db\"); print(c.execute(\"SELECT name, timezone FROM families\").fetchall())"'
  ssh test 'cd ~/openfamhub && docker compose exec api python -c "import sqlite3; c = sqlite3.connect(\"/data/db/homehub.db\"); c.execute(\"UPDATE families SET timezone = ?\", (\"America/Detroit\",)); c.commit()"'
  ```

  Adding a calendar now fails straight away (with the reason) if its first sync fails, instead of adding a calendar that shows an error later.
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
- All app state is in `data/` plus your `.env`: `db` (the live database), `backups` (daily snapshots) and `photos` (the family's photos and videos, under `photos/media/`). The daily job only covers the database; photos exist only in `data/photos`, so copy both off the server (next section).
- **Before an upgrade**, take a manual backup. Because SQLite runs in WAL mode, do not copy only `homehub.db` while the API is writing. Prefer the app's backup directory, or stop the API before copying the database files:

  ```bash
  ssh test 'cd ~/openfamhub && sh -c '\''set -eu; docker compose stop api; trap "docker compose start api" EXIT; ts=$(date +%F_%H%M); cp data/db/homehub.db data/backups/manual_${ts}.db; [ ! -f data/db/homehub.db-wal ] || cp data/db/homehub.db-wal data/backups/manual_${ts}.db-wal; [ ! -f data/db/homehub.db-shm ] || cp data/db/homehub.db-shm data/backups/manual_${ts}.db-shm'\'''
  ```

  The scheduled backup job uses SQLite's online-backup API and is safe while the app is running.

### Off-host copies (NAS)

A backup on the same disk doesn't survive that disk. `backup-offhost.sh` copies `data/backups` and `data/photos` to a mounted folder or, over SSH, to another machine. It never deletes anything at the destination (a photo removed in the app stays in the backup), skips the live database (it changes while being read; the daily snapshots are the consistent copies) and skips uploads still in progress. `deploy.sh remote` puts the script in `~/openfamhub`; in a checkout it's `scripts/backup-offhost.sh`.

```bash
cd ~/openfamhub
./backup-offhost.sh --dry-run backup@nas:/volume1/openfamhub   # see what would be copied
./backup-offhost.sh backup@nas:/volume1/openfamhub             # over SSH (needs rsync on both ends)
./backup-offhost.sh /mnt/nas/openfamhub                        # or to a mounted share (rsync, or plain cp without it)
./backup-offhost.sh --with-env /mnt/nas/openfamhub             # also .env, saved as "env", mode 600
```

- Run it daily after `BACKUP_TIME`, for example from the server's crontab (`crontab -e`): `30 4 * * * cd ~/openfamhub && ./backup-offhost.sh backup@nas:/volume1/openfamhub >> backup-offhost.log 2>&1`. For SSH targets, give the server a key the NAS accepts without a password.
- `.env` holds `SECRET_KEY`; restoring without it signs everyone out (wall displays stay paired). Copy it with `--with-env` to a share only you can read, or keep it in your password manager.
- The destination keeps every daily snapshot the server ever sent; prune old ones on the NAS if space matters.

### Restore

1. **Database:** stop the API and put a snapshot in place.

   ```bash
   ssh test
   cd ~/openfamhub
   docker compose stop api
   cp data/db/homehub.db data/db/homehub.db.before-restore
   cp data/backups/homehub_2026-10-01.db data/db/homehub.db      # or copy one back from the NAS first
   rm -f data/db/homehub.db-wal data/db/homehub.db-shm   # WAL files belong to the old DB
   ```

2. **Photos and videos:** copy `photos/` back from the off-host copy.

   ```bash
   rsync -a backup@nas:/volume1/openfamhub/photos/ data/photos/     # or: cp -a /mnt/nas/openfamhub/photos/. data/photos/
   ```

   The database lists the photos and the files hold them, so restore both from around the same day. A photo whose files are missing doesn't show on the wall, and you can remove it on the Photos page.
3. **Settings:** on a new server, put `.env` back (from `env` on the NAS, or recreate it with the same `SECRET_KEY`).
4. `docker compose start api`. Migrations bring an older snapshot up to date.

---

## 8. Build-from-source mode (single machine)

```bash
scripts/deploy.sh setup     # .env from .env.example with a generated SECRET_KEY; creates ./data
scripts/deploy.sh deploy    # docker compose up -d --build, then wait for healthy
scripts/deploy.sh update    # git pull --ff-only, then deploy
scripts/deploy.sh status | logs [service] | stop
```

By default this runs in **LAN mode**: Caddy listens on 80/443 and serves `https://$SITE_ADDRESS` with its internal CA, which each device must trust ([cert-trust.md](cert-trust.md)). To put it behind another proxy instead, set `CADDYFILE=Caddyfile.proxy` and `HTTP_PORT=8080` in `.env`.

Build-from-source deploys stamp images from the checkout too: `scripts/deploy.sh deploy` sets `OPENFAMHUB_VERSION` from the root `VERSION` file (`<release>`) and `OPENFAMHUB_COMMIT` from the current git commit before running `docker compose up --build`. To verify what is actually running, check either the setup/login Help & About box before signing in or the health endpoint for the mode you are running:

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
| Uploading a video fails with `413` | A proxy in front of OpenFamHub limits request size; raise it (nginx: `client_max_body_size 500m`). OpenFamHub itself allows 500 MB (photos 30 MB, videos 10 minutes). |
| A video stays on "Converting…" | Videos convert one at a time; a long clip can take a few minutes on a small server. `docker compose logs api` shows ffmpeg errors; a restart marks unfinished ones as failed so they can be uploaded again. |
| An iPhone photo fails to upload | HEIC/HEIF is supported; if it still fails, check `docker compose logs api` for image decode errors and confirm the server is running a build with `pillow-heif` installed. |
| The wall screen is black | The sleep schedule (Admin › Settings) is on; a touch lights it for a few minutes. |

---

## CI

CI runs on the self-hosted Gitea instance via Gitea Actions. `.gitea/workflows/ci.yml`
runs the backend tests and the frontend lint, unit tests and build on every push and pull request, then
publishes `forgejo.vernonmyers.cloud/vernon/openfamhub-{api,web}` (amd64 + arm64)
and deploys the test VM on pushes to `master`, then scans the published images
with Trivy (non-blocking; HIGH/CRITICAL findings can become backlog issues). The
one-time runner and secret setup is in [ci.md](ci.md).
