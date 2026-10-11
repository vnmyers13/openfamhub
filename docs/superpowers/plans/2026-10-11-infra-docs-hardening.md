# Infra Docs Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make OpenFamHub deployment repeatable after the 2026-10-11 deploy findings by fixing remote `.env` handling, CI publishing behavior, PWA cache headers, and deployment documentation.

**Architecture:** Keep changes small and localized. `scripts/deploy.sh` remains the single deployment entry point; GitHub Actions continues to validate code while publishing only from canonical `master`; nginx serves PWA control files with no-cache headers; documentation records the operational workflow without exposing secrets.

**Tech Stack:** Bash, Docker Compose, GitHub Actions YAML, nginx, Markdown, FastAPI backend tests, Vite frontend build.

## Global Constraints

- Preserve existing remote secrets and settings; never overwrite `SECRET_KEY`, `ALLOWED_ORIGINS`, ports, timezone, or backup settings.
- Do not commit secrets, tokens, `.env`, databases, `graphify-out/`, or `Claude outputs/`.
- Version remains `0.30`; do not bump `APP_VERSION`, Docker labels, README badge, or changelog version.
- Deployment registry remains `forgejo.vernonmyers.cloud/vernon`.
- The larger production startup/migration smoke test is out of scope for this pass.
- Run verification before claiming completion: backend tests, frontend build, remote `docker compose config` if reachable, and `git diff` inspection.

---

## File Structure

- Modify `scripts/deploy.sh`: add a small remote `.env` upsert helper inside `deploy_remote()` and validate remote compose config before pull.
- Modify `.github/workflows/build.yml`: add PR validation and restrict image publishing to pushes on `master`.
- Modify `frontend/nginx.conf`: no-cache PWA control files and retain long caching for hashed/static assets.
- Modify `docs/deployment.md`: document 1Password registry login, LAN DNS/hosts, WAL-safe manual backups, and troubleshooting.
- Modify `README.md`: point deployment readers to the detailed registry and VM DNS notes.
- Modify `TODO.md`: check off completed infra review backlog items after implementation verification.

---

### Task 1: Remote Deploy Env Upsert And Compose Validation

**Files:**
- Modify: `scripts/deploy.sh:145-174`

**Interfaces:**
- Consumes: `resolve_registry()` sets global `REGISTRY`; `resolve_version()` sets global `VERSION`; remote directory variable `dir` defaults to `openfamhub`.
- Produces: Existing remote `~/openfamhub/.env` always contains `REGISTRY=<registry>` and `OPENFAMHUB_VERSION=<version>` before `docker compose pull` runs.

- [ ] **Step 1: Reproduce current missing-line failure with a temp remote-like env file**

Run this local shell snippet from repo root. It demonstrates why simple `sed -i 's|^OPENFAMHUB_VERSION=.*|...'` is insufficient when the line is absent.

```bash
tmp="$(mktemp -d)" \
  && printf 'SECRET_KEY=keep-me\nALLOWED_ORIGINS=https://example.test\n' > "$tmp/.env" \
  && sed -i.bak 's|^OPENFAMHUB_VERSION=.*|OPENFAMHUB_VERSION=0.30|' "$tmp/.env" \
  && ! grep -q '^OPENFAMHUB_VERSION=' "$tmp/.env" \
  && rm -rf "$tmp"
```

Expected: command exits `0`, proving the current replacement-only pattern does not add a missing key.

- [ ] **Step 2: Add an upsert helper inside `deploy_remote()`**

Edit the existing `if ssh "$host" "test -f '$dir/.env'"; then` block in `scripts/deploy.sh`. Replace the current `sed`-only body with this remote script invocation:

```bash
        log "Pinning REGISTRY=$REGISTRY and OPENFAMHUB_VERSION=$VERSION in existing $dir/.env"
        ssh "$host" "REGISTRY='$REGISTRY' VERSION='$VERSION' ENV_FILE='$dir/.env' sh -s" <<'REMOTE_ENV'
set -eu
upsert_env() {
    key="$1"
    value="$2"
    file="$3"
    if grep -q "^${key}=" "$file"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "$file"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}
upsert_env REGISTRY "$REGISTRY" "$ENV_FILE"
upsert_env OPENFAMHUB_VERSION "$VERSION" "$ENV_FILE"
REMOTE_ENV
```

Keep the `else` branch that creates a new `.env` from `deploy/env.template` unchanged.

- [ ] **Step 3: Add remote compose validation before pull**

Immediately after the `if/else` block that ensures `.env`, before the existing `log "Pulling images..."`, add:

```bash
    log "Validating compose config on $host..."
    ssh "$host" "cd '$dir' && docker compose config >/dev/null"
```

- [ ] **Step 4: Verify the upsert helper locally using the same shell logic**

Run this local equivalent from repo root:

```bash
tmp="$(mktemp -d)" \
  && printf 'SECRET_KEY=keep-me\nALLOWED_ORIGINS=https://example.test\n' > "$tmp/.env" \
  && REGISTRY='forgejo.vernonmyers.cloud/vernon' VERSION='0.30' ENV_FILE="$tmp/.env" sh -c '
set -eu
upsert_env() {
    key="$1"
    value="$2"
    file="$3"
    if grep -q "^${key}=" "$file"; then
        sed -i.bak "s|^${key}=.*|${key}=${value}|" "$file"
    else
        printf "%s=%s\n" "$key" "$value" >> "$file"
    fi
}
upsert_env REGISTRY "$REGISTRY" "$ENV_FILE"
upsert_env OPENFAMHUB_VERSION "$VERSION" "$ENV_FILE"
' \
  && grep -q '^SECRET_KEY=keep-me$' "$tmp/.env" \
  && grep -q '^REGISTRY=forgejo.vernonmyers.cloud/vernon$' "$tmp/.env" \
  && grep -q '^OPENFAMHUB_VERSION=0.30$' "$tmp/.env" \
  && rm -rf "$tmp"
```

Expected: command exits `0` and preserves `SECRET_KEY`.

- [ ] **Step 5: Verify remote compose config if the VM is reachable**

Run:

```bash
ssh 192.168.10.80 'cd ~/openfamhub && docker compose config >/dev/null'
```

Expected: command exits `0`. Warnings about multiple compose files are acceptable; invalid image references are not.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add scripts/deploy.sh && git commit -m "fix(deploy): upsert remote image settings"
```

---

### Task 2: CI Pull Request Validation And Canonical Image Publishing

**Files:**
- Modify: `.github/workflows/build.yml:3-70`

**Interfaces:**
- Consumes: existing `test`, `frontend`, and `build` jobs.
- Produces: backend/frontend validation on PRs to `master`; image publishing only on push to `master`.

- [ ] **Step 1: Inspect current workflow trigger and build job**

Run:

```bash
grep -n "^on:\|branches:\|^  build:\|push:" .github/workflows/build.yml
```

Expected before change: push branches include both `main` and `master`, no `pull_request`, and build job has no `if:` gate.

- [ ] **Step 2: Update workflow triggers**

Change the top of `.github/workflows/build.yml` to:

```yaml
on:
  push:
    branches: [master]
  pull_request:
    branches: [master]
  workflow_dispatch:
```

- [ ] **Step 3: Gate the Docker image build/push job**

Add this line under `build:` before `needs:`:

```yaml
    if: github.event_name == 'push' && github.ref == 'refs/heads/master'
```

The start of the job should become:

```yaml
  build:
    if: github.event_name == 'push' && github.ref == 'refs/heads/master'
    needs: [test, frontend]
    runs-on: ubuntu-latest
```

- [ ] **Step 4: Verify workflow intent by inspection**

Run:

```bash
```

Expected: output contains `pull_request:`, two `branches: [master]` lines, and the build job `if:` line.

- [ ] **Step 5: Commit Task 2**

Run:

```bash
git add .github/workflows/build.yml && git commit -m "ci: validate pull requests without publishing images"
```

---

### Task 3: PWA Control File Cache Headers

**Files:**
- Modify: `frontend/nginx.conf:9-16`

**Interfaces:**
- Consumes: nginx serving built Vite/PWA assets from `/usr/share/nginx/html`.
- Produces: no-cache headers for `/sw.js`, `/registerSW.js`, `/manifest.webmanifest`, and `/workbox-*.js`; immutable caching remains for regular static assets.

- [ ] **Step 1: Confirm current over-broad immutable cache rule**

Run:

```bash
grep -n "location.*js\|Cache-Control" frontend/nginx.conf
```

Expected before change: `.js` files are included in the one-year immutable rule.

- [ ] **Step 2: Replace nginx cache locations**

Change `frontend/nginx.conf` to contain these locations after the root `location /` block:

```nginx
  location = /sw.js {
    expires -1;
    add_header Cache-Control 'no-cache, no-store, must-revalidate';
  }

  location = /registerSW.js {
    expires -1;
    add_header Cache-Control 'no-cache, no-store, must-revalidate';
  }

  location = /manifest.webmanifest {
    expires -1;
    add_header Cache-Control 'no-cache, no-store, must-revalidate';
  }

  location ~* ^/workbox-.*\.js$ {
    expires -1;
    add_header Cache-Control 'no-cache, no-store, must-revalidate';
  }

  location ~* ^/assets/.*\.(js|css|png|ico|svg|woff2)$ {
    expires 1y;
    add_header Cache-Control 'public, immutable';
  }

  location ~* \.(png|ico|svg|woff2)$ {
    expires 1y;
    add_header Cache-Control 'public, immutable';
  }
```

- [ ] **Step 3: Run frontend build**

Run:

```bash
npm run build
```

Working directory: `frontend/`

Expected: TypeScript and Vite build exit `0`. Chunk-size warnings are acceptable; TypeScript errors are not.

- [ ] **Step 4: Optionally validate nginx syntax with Docker**

Run from repo root if Docker is available:

```bash
docker run --rm -v "$PWD/frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro" nginx:alpine nginx -t
```

Expected: output includes `syntax is ok` and `test is successful`.

- [ ] **Step 5: Commit Task 3**

Run:

```bash
git add frontend/nginx.conf && git commit -m "fix(web): avoid immutable caching for service worker files"
```

---

### Task 4: Deployment Documentation And Backlog Updates

**Files:**
- Modify: `docs/deployment.md:41-60`, `docs/deployment.md:62-82`, `docs/deployment.md:102-114`, `docs/deployment.md:201-221`, `docs/deployment.md:238-254`, `docs/deployment.md:257-259`
- Modify: `README.md:31-48`
- Modify: `TODO.md:49-55`

**Interfaces:**
- Consumes: implementation from Tasks 1-3.
- Produces: docs that explain the repeatable registry deploy workflow and checked-off completed infra backlog items.

- [ ] **Step 1: Update registry login docs with 1Password guidance**

In `docs/deployment.md`, under `### On your Mac`, replace the registry login bullet with:

```markdown
- Log in to the registry with a Forgejo access token. In 1Password, use the Development vault item `forgejo.vernonmyers.cloud` and pipe the concealed password field into Docker so the token is not printed:

  ```bash
  op read 'op://Development/forgejo.vernonmyers.cloud/password' \
    | docker login forgejo.vernonmyers.cloud --username vernon --password-stdin
  ```

  If you create a new token in Forgejo, create it under Forgejo › Settings › Applications with **package: read and write** scope for publishing.
```

- [ ] **Step 2: Update server registry login docs**

In `docs/deployment.md`, under `### On the server`, replace the private package login bullet with:

```markdown
- If the packages are **private**, log in once so the server can pull them. A token with **package: read** is enough. Use `docker login forgejo.vernonmyers.cloud` on the server and paste the read token when prompted.
```

- [ ] **Step 3: Add LAN DNS/hosts note**

In `docs/deployment.md`, in `### Registry address: HTTPS name vs. LAN IP`, after `Use the HTTPS name...`, add:

```markdown
The server must resolve `forgejo.vernonmyers.cloud` to the Forgejo host. On the LAN this may need local DNS or an `/etc/hosts` entry; the current Forgejo host is `192.168.10.2`:

```bash
ssh 192.168.10.80 'getent hosts forgejo.vernonmyers.cloud || true'
ssh 192.168.10.80 'printf "192.168.10.2 forgejo.vernonmyers.cloud\n" | sudo tee -a /etc/hosts'
```

Only add the hosts entry if DNS does not already return the correct address.
```

- [ ] **Step 4: Update remote deploy behavior description**

In `docs/deployment.md`, update the numbered list under `remote does the following over SSH` so step 2 says:

```markdown
2. **First run:** creates `~/openfamhub/.env` from `deploy/env.template`, with a freshly generated `SECRET_KEY`, `ALLOWED_ORIGINS=$PUBLIC_URL`, behind-proxy mode on port 8080, and the file locked to mode `600`. Later runs preserve existing secrets/settings and upsert `REGISTRY` plus `OPENFAMHUB_VERSION`.
```

Add a new step after that:

```markdown
3. Validates `docker compose config` on the server before pulling images, so missing image variables fail before deployment changes containers.
```

Renumber the remaining steps accordingly.

- [ ] **Step 5: Replace unsafe manual backup command**

In `docs/deployment.md`, replace the manual backup block at lines 205-209 with:

```markdown
- **Before an upgrade**, take a manual backup. Because SQLite runs in WAL mode, do not copy only `homehub.db` while the API is writing. Prefer the app's backup directory, or stop the API before copying the database files:

  ```bash
  ssh test 'cd ~/openfamhub && sh -c '\''set -eu; docker compose stop api; trap "docker compose start api" EXIT; ts=$(date +%F_%H%M); cp data/db/homehub.db data/backups/manual_${ts}.db; [ ! -f data/db/homehub.db-wal ] || cp data/db/homehub.db-wal data/backups/manual_${ts}.db-wal; [ ! -f data/db/homehub.db-shm ] || cp data/db/homehub.db-shm data/backups/manual_${ts}.db-shm'\'''
  ```

  The scheduled backup job uses SQLite's online-backup API and is safe while the app is running.
```

- [ ] **Step 6: Update troubleshooting and CI notes**

In the troubleshooting table in `docs/deployment.md`, add this row:

```markdown
| `remote`: image is `/openfamhub-api:` or compose says `REGISTRY` / `OPENFAMHUB_VERSION` is unset | Re-run the current `scripts/deploy.sh remote <host>`; it upserts both variables in the remote `.env` and validates `docker compose config` before pulling. |
```

At the bottom CI section, replace the final sentence with:

```markdown
`.github/workflows/build.yml` runs backend tests plus frontend lint/build on pushes and pull requests to `master`. It only publishes GHCR images on pushes to canonical `master`; Forgejo publishing still happens through `scripts/deploy.sh publish`. Moving CI to Forgejo Actions, once a runner exists, is tracked in [TODO.md](../TODO.md).
```

- [ ] **Step 7: Update README deploy pointer**

In `README.md`, under `Deploying to a server`, add this sentence after the command block:

```markdown
Registry login can use the 1Password Development item `forgejo.vernonmyers.cloud`; the full guide also covers LAN DNS for the registry hostname and server-side pull credentials.
```

- [ ] **Step 8: Mark completed review backlog items**

In `TODO.md`, mark these five items complete by changing `- [ ]` to `- [x]`:

```markdown
- [x] Restrict GHCR `latest` image publishing to the canonical `master` branch. The GitHub workflow currently runs on both `main` and `master`, but `main` is the retired/divergent v0.29 line (`.github/workflows/build.yml`).
- [x] Upsert `OPENFAMHUB_VERSION` during remote deploy. `scripts/deploy.sh remote` only replaces the line if it already exists, leaving older `.env` files with an unset image tag (`scripts/deploy.sh`, `deploy/compose.yml`). Validate with `docker compose config` before pull.
- [x] Stop caching service worker assets as immutable for one year. Add no-cache rules for `/sw.js`, Workbox files, and the manifest; keep immutable caching for hashed `/assets/*` (`frontend/nginx.conf`).
- [x] Fix manual backup docs for SQLite WAL mode. The deployment docs copy only `homehub.db`; document online backup, stopping the API first, or copying `homehub.db`, `homehub.db-wal`, and `homehub.db-shm` together (`docs/deployment.md`).
- [x] Run CI on pull requests without pushing images. Add a PR trigger for `master`; gate image publishing to push events (`.github/workflows/build.yml`).
```

Do not mark the production-startup/migration smoke test complete.

- [ ] **Step 9: Verify docs contain the new operational guidance**

Run:

```bash
grep -n "op://Development/forgejo.vernonmyers.cloud/password\|getent hosts forgejo.vernonmyers.cloud\|docker compose config\|WAL mode\|pull requests to master" docs/deployment.md README.md TODO.md
```

Expected: output includes the 1Password reference, LAN DNS command, compose validation text, WAL backup text, and CI pull request text.

- [ ] **Step 10: Commit Task 4**

Run:

```bash
git add docs/deployment.md README.md TODO.md && git commit -m "docs: clarify registry deploy and backup workflow"
```

---

### Task 5: Final Verification And Push

**Files:**
- Inspect only; no planned file edits.

**Interfaces:**
- Consumes: Tasks 1-4 commits.
- Produces: verified branch ready to push to Forgejo and GitHub.

- [ ] **Step 1: Run backend tests**

Run:

```bash
source .venv/bin/activate && pytest -v
```

Working directory: `backend/`

Expected: all tests pass. A pytest-asyncio deprecation warning and passlib `crypt` warning are acceptable if no tests fail.

- [ ] **Step 2: Run frontend build**

Run:

```bash
npm run build
```

Working directory: `frontend/`

Expected: TypeScript and Vite build exit `0`. Chunk-size warnings and npm audit notices are acceptable; TypeScript errors are not.

- [ ] **Step 3: Validate remote compose config if reachable**

Run:

```bash
ssh 192.168.10.80 'cd ~/openfamhub && docker compose config >/dev/null'
```

Expected: command exits `0`. Warnings about multiple compose files are acceptable.

- [ ] **Step 4: Inspect final git state**

Run:

```bash
git status --short && git diff --stat && git log --oneline -8
```

Expected: only known untracked local artifacts remain, if any: `Claude outputs/` and `graphify-out/`. No tracked modifications should remain after Task 4 commit.

- [ ] **Step 5: Push to both remotes**

Run:

```bash
git push forgejo feat/0.30-security && git push origin feat/0.30-security
```

Expected: both remotes accept the branch.
