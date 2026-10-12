# Gitea Actions CI/CD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run OpenFamHub CI on the self-hosted Gitea instance and extend it to publish multi-arch images and deploy the test VM, replacing the GitHub-Actions-only pipeline.

**Architecture:** A single `gitea-runner` process on the test VM (192.168.10.80) exposes a `host` label for publish/deploy and two container labels for checks. A new `.gitea/workflows/ci.yml` runs backend tests and frontend lint/build in containers, then on `master` publishes images via the existing `scripts/deploy.sh publish` and deploys with a new local `scripts/deploy.sh server` subcommand. GitHub Actions is retired.

**Tech Stack:** Bash, Docker Compose, Gitea Actions YAML, `gitea-runner` v5, Docker buildx + QEMU/binfmt, Markdown, FastAPI/pytest, Vite/npm.

## Global Constraints

- Version remains `0.30`; do not bump `APP_VERSION`, Docker labels, README badge, or CHANGELOG.
- Registry stays `forgejo.vernonmyers.cloud/vernon`; images are `openfamhub-api` and `openfamhub-web`.
- Never print, log, or commit secrets/tokens. `REGISTRY_TOKEN` is a repo secret sourced from 1Password.
- Do not commit `.env`, databases, `graphify-out/`, or `Claude outputs/`.
- The runner runs on `192.168.10.80`; Gitea is `https://forgejo.vernonmyers.cloud` (Gitea 1.27.3).
- Checkout uses `builtin:checkout` (no `actions/checkout`, no Node on the host).
- Work happens on the current branch (`feat/0.30-security`); do not merge or touch `origin/main`.
- Run verification before claiming completion; do not push without being asked.

---

## File Structure

- Modify `scripts/deploy.sh`: add a `server()` function (local, no-SSH registry-pull deploy) plus `usage` text and a `server)` dispatch case.
- Create `.gitea/workflows/ci.yml`: the pipeline (backend, frontend, publish, deploy).
- Delete `.github/workflows/build.yml`: GitHub Actions retires.
- Create `docs/ci.md`: one-time runner/secret setup and how the pipeline works.
- Modify `docs/deployment.md`: rewrite the CI section.
- Modify `AGENTS.md`: replace the stale CI gotcha.
- Modify `TODO.md`: check off the "Move CI to Forgejo Actions" item.

---

### Task 1: `scripts/deploy.sh server` local deploy subcommand

**Files:**
- Modify: `scripts/deploy.sh` (add `server()` after `remote()` around line 197; add `server)` case near line 225; add usage lines in `usage()` around line 41-50)

**Interfaces:**
- Consumes: `resolve_registry()` sets global `REGISTRY`; `resolve_version()` sets global `VERSION`; globals `HEALTH_WAIT`, `PUBLIC_URL`, `REMOTE_DIR`; files `deploy/compose.yml`, `deploy/env.template`, `config/{Caddyfile,Caddyfile.proxy,routes.caddy}`.
- Produces: `scripts/deploy.sh server [dir]` installs the deploy bundle into `[dir]` (default `${REMOTE_DIR:-openfamhub}`), upserts `REGISTRY` and `OPENFAMHUB_VERSION` in `[dir]/.env`, validates compose, then `docker compose pull && up -d` and waits for health. Consumed by Task 2's `deploy` job.

- [ ] **Step 1: Write the failing test**

Run this from the repo root. It stubs `docker` on `PATH` so nothing is pulled, then invokes the not-yet-existing subcommand.

```bash
tmp="$(mktemp -d)"
mkdir -p "$tmp/bin"
cat > "$tmp/bin/docker" <<'FAKE'
#!/bin/sh
case "$*" in
  *"compose ps"*) echo healthy ;;
  *) exit 0 ;;
esac
FAKE
chmod +x "$tmp/bin/docker"
PATH="$tmp/bin:$PATH" scripts/deploy.sh server "$tmp/remote"
echo "exit=$?"
grep -q '^REGISTRY=forgejo.vernonmyers.cloud/vernon$' "$tmp/remote/.env" && echo "registry ok"
grep -q '^OPENFAMHUB_VERSION=0.30$' "$tmp/remote/.env" && echo "version ok"
ls "$tmp/remote/compose.yml" "$tmp/remote/config/Caddyfile"
rm -rf "$tmp"
```

Expected: FAIL — the script prints its usage and exits non-zero because `server` is not a known command (no `registry ok`/`version ok` output).

- [ ] **Step 2: Add the `server()` function**

Insert immediately after the closing brace of `remote()` in `scripts/deploy.sh`:

```bash
server() {
    local dir="${1:-${REMOTE_DIR:-openfamhub}}"
    resolve_registry
    resolve_version "${2:-}"
    [ -d "$dir" ] || error "Deploy directory '$dir' does not exist."

    log "Installing deploy bundle into $dir ..."
    mkdir -p "$dir/config" "$dir/data/db" "$dir/data/photos" "$dir/data/backups"
    cp deploy/compose.yml "$dir/compose.yml"
    cp config/Caddyfile config/Caddyfile.proxy config/routes.caddy "$dir/config/"

    if [ -f "$dir/.env" ]; then
        log "Pinning REGISTRY=$REGISTRY and OPENFAMHUB_VERSION=$VERSION in $dir/.env"
        REGISTRY="$REGISTRY" VERSION="$VERSION" ENV_FILE="$dir/.env" sh -s <<'LOCAL_ENV'
set -eu
upsert_env() {
    key="$1"
    value="$2"
    file="$3"
    if grep -q "^${key}=" "$file"; then
        sed -i.bak "s|^${key}=.*|${key}=${value}|" "$file" && rm -f "$file.bak"
    else
        printf '%s=%s\n' "$key" "$value" >> "$file"
    fi
}
upsert_env REGISTRY "$REGISTRY" "$ENV_FILE"
upsert_env OPENFAMHUB_VERSION "$VERSION" "$ENV_FILE"
LOCAL_ENV
    else
        command -v openssl >/dev/null || error "openssl is needed to generate SECRET_KEY"
        local key public_url
        key=$(openssl rand -hex 32)
        public_url="${PUBLIC_URL:-https://openfamhub.local}"
        sed -e "s|__REGISTRY__|$REGISTRY|" \
            -e "s|__VERSION__|$VERSION|" \
            -e "s|__PUBLIC_URL__|$public_url|" \
            -e "s|__SECRET_KEY__|$key|" \
            deploy/env.template > "$dir/.env"
        chmod 600 "$dir/.env"
        log "Created $dir/.env with a generated SECRET_KEY (back it up)."
    fi

    log "Validating compose config in $dir..."
    ( cd "$dir" && docker compose config >/dev/null )

    log "Pulling images and starting services in $dir..."
    ( cd "$dir" && docker compose pull && docker compose up -d --remove-orphans )
    log "Waiting for the API to become healthy..."
    ( cd "$dir" && bash -c "$HEALTH_WAIT" )
    ( cd "$dir" && docker compose ps )
    log "Deployed $VERSION to $dir."
}
```

- [ ] **Step 3: Wire the dispatch case and usage text**

In the `case "${1:-help}" in` block, add after the `remote)` line:

```bash
    server)  server "${2:-}" ;;
```

In `usage()`, add under the "Registry workflow:" section (after the `remote <host> [ver]` line):

```bash
  server [dir]          Install the deploy bundle into [dir] (default: openfamhub)
                        and pull + restart the stack locally (no SSH)
```

- [ ] **Step 4: Run the test to verify it passes**

Re-run the Step 1 block. Expected: `exit=0`, then `registry ok`, `version ok`, and both `compose.yml` and `config/Caddyfile` listed.

- [ ] **Step 5: Syntax-check and confirm usage**

```bash
bash -n scripts/deploy.sh && echo "syntax ok"
scripts/deploy.sh help | grep -A1 'server \[dir\]'
```

Expected: `syntax ok` and the two usage lines.

- [ ] **Step 6: Commit**

```bash
git add scripts/deploy.sh
git commit -m "feat(deploy): add local server deploy subcommand"
```

---

### Task 2: Gitea Actions workflow (and retire GitHub Actions)

**Files:**
- Create: `.gitea/workflows/ci.yml`
- Delete: `.github/workflows/build.yml`

**Interfaces:**
- Consumes: `scripts/deploy.sh publish` (existing) and `scripts/deploy.sh server` (Task 1). Runner labels `openfamhub`, `openfamhub-python`, `openfamhub-node` (Task 4 registers them). Repo secret `REGISTRY_TOKEN` (Task 4).
- Produces: jobs `backend`, `frontend`, `publish`, `deploy`; the `deploy` job runs `scripts/deploy.sh server "$HOME/openfamhub"`.

- [ ] **Step 1: Write the workflow file**

Create `.gitea/workflows/ci.yml`:

```yaml
name: CI

on:
  push:
  pull_request:
  workflow_dispatch:

env:
  SECRET_KEY: ci-only-not-a-real-secret-0123456789abcdef

jobs:
  backend:
    runs-on: openfamhub-python
    steps:
      - uses: builtin:checkout
      - name: Install dependencies
        run: pip install -r backend/requirements.txt pytest pytest-asyncio httpx
      - name: Run backend tests
        run: pytest backend/tests -v

  frontend:
    runs-on: openfamhub-node
    defaults:
      run:
        working-directory: frontend
    steps:
      - uses: builtin:checkout
      - name: Install dependencies
        run: npm ci
      - name: Lint
        run: npm run lint
      - name: Build
        run: npm run build

  publish:
    needs: [backend, frontend]
    if: gitea.event_name == 'push' && gitea.ref == 'refs/heads/master'
    runs-on: openfamhub
    steps:
      - uses: builtin:checkout
      - name: Log in to the Forgejo registry
        run: echo "${{ secrets.REGISTRY_TOKEN }}" | docker login forgejo.vernonmyers.cloud --username vernon --password-stdin
      - name: Build and push images
        run: scripts/deploy.sh publish

  deploy:
    needs: [publish]
    if: gitea.event_name == 'push' && gitea.ref == 'refs/heads/master'
    runs-on: openfamhub
    steps:
      - uses: builtin:checkout
      - name: Install bundle and restart the stack
        run: scripts/deploy.sh server "$HOME/openfamhub"
```

- [ ] **Step 2: Validate the YAML and structure**

```bash
source backend/.venv/bin/activate
python - <<'PY'
import pathlib, yaml
wf = yaml.safe_load(pathlib.Path(".gitea/workflows/ci.yml").read_text())
assert set(wf["jobs"]) == {"backend", "frontend", "publish", "deploy"}, wf["jobs"].keys()
assert wf["jobs"]["backend"]["runs-on"] == "openfamhub-python"
assert wf["jobs"]["frontend"]["runs-on"] == "openfamhub-node"
assert wf["jobs"]["publish"]["runs-on"] == "openfamhub"
assert wf["jobs"]["deploy"]["needs"] == ["publish"]
assert wf["jobs"]["publish"]["if"] == "gitea.event_name == 'push' && gitea.ref == 'refs/heads/master'"
assert all("builtin:checkout" in str(s.get("uses")) for j in wf["jobs"].values() for s in j["steps"])
assert set(wf[True]) == {"push", "pull_request", "workflow_dispatch"}  # YAML parses bare `on` as True
print("ci.yml OK")
PY
```

Expected: `ci.yml OK`. (If `yaml` is missing, `pip install pyyaml` into the venv first.)

- [ ] **Step 3: Retire the GitHub Actions workflow**

```bash
git rm .github/workflows/build.yml
```

- [ ] **Step 4: Confirm no remaining active references**

```bash
grep -rn "workflows/build.yml" AGENTS.md docs/ TODO.md CLAUDE.md || echo "no stale references"
```

Expected: the only remaining hit, if any, is inside `docs/superpowers/` history files (acceptable). `docs/deployment.md`, `AGENTS.md`, and `TODO.md` are updated in Task 3, so re-run this check after Task 3 if it reported hits there.

- [ ] **Step 5: Commit**

```bash
git add .gitea/workflows/ci.yml
git commit -m "ci: add Gitea Actions pipeline and retire GitHub Actions"
```

---

### Task 3: Documentation and TODO

**Files:**
- Create: `docs/ci.md`
- Modify: `docs/deployment.md` (CI section, currently lines 269-271)
- Modify: `AGENTS.md` (CI gotcha line, currently line 46)
- Modify: `TODO.md` (line 126: "Move CI to Forgejo Actions once a runner exists")

**Interfaces:**
- Consumes: the workflow from Task 2 and the `server` subcommand from Task 1.
- Produces: operator-facing instructions for the one-time runner setup performed in Task 4.

- [ ] **Step 1: Create `docs/ci.md`**

````markdown
# CI/CD (Gitea Actions)

CI runs on the self-hosted Gitea instance (`https://forgejo.vernonmyers.cloud`).
Workflows live in `.gitea/workflows/` and execute on a runner installed on the
test VM (`192.168.10.80`).

## Pipeline

`.gitea/workflows/ci.yml` has four jobs:

| Job | Runs on | Trigger |
|---|---|---|
| `backend` | `openfamhub-python` (container `python:3.12-slim`) | every push and PR |
| `frontend` | `openfamhub-node` (container `node:22`) | every push and PR |
| `publish` | `openfamhub` (host) | push to `master` only |
| `deploy` | `openfamhub` (host) | push to `master` only |

`publish` builds `linux/amd64` and `linux/arm64` images for `openfamhub-api` and
`openfamhub-web` and pushes them to the Forgejo registry. `deploy` then runs
`scripts/deploy.sh server "$HOME/openfamhub"`, which copies the compose bundle
into `~/openfamhub`, pins `REGISTRY`/`OPENFAMHUB_VERSION`, and pulls + restarts
the stack.

Pull requests run the checks only; they never publish or deploy.

## One-time setup

1. **Enable Actions** for the repository: repository **Settings → Actions**.
2. **Install the runner binary** on `192.168.10.80` (ensure `git >= 2.34.1`):

   ```bash
   curl -fL -o /tmp/gitea-runner https://dl.gitea.com/gitea-runner/5.0.0/gitea-runner-5.0.0-linux-amd64
   sudo install -m 0755 /tmp/gitea-runner /usr/local/bin/gitea-runner
   gitea-runner --version
   ```

3. **Register the runner** with a repository-level token from
   **Settings → Actions → Runners** (the token is a secret; do not paste it into
   shell history on a shared machine):

   ```bash
   gitea-runner register --no-interactive \
     --instance https://forgejo.vernonmyers.cloud \
     --token '<repo runner token>' \
     --name openfamhub-vm \
     --labels 'openfamhub:host,openfamhub-python:docker://python:3.12-slim,openfamhub-node:docker://node:22'
   ```

   This writes a `.runner` file (mode `600`) next to the runner config. Do not
   commit it.

4. **Run it as a service** so it restarts on boot. Create
   `/etc/systemd/system/gitea-runner.service`:

   ```ini
   [Unit]
   Description=Gitea Actions runner
   After=network-online.target docker.service
   Wants=network-online.target

   [Service]
   User=vernon
   WorkingDirectory=/home/vernon/gitea-runner
   ExecStart=/usr/local/bin/gitea-runner daemon
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```

   ```bash
   sudo systemctl daemon-reload && sudo systemctl enable --now gitea-runner
   systemctl status gitea-runner --no-pager
   ```

5. **Enable arm64 emulation** (once) so buildx can build the Pi's architecture:

   ```bash
   docker run --privileged --rm tonistiigi/binfmt --install arm64
   ```

6. **Create the registry secret**: repository **Settings → Actions → Secrets**,
   name `REGISTRY_TOKEN`, value = a Gitea token with **package: read,write**
   scope (from the 1Password Development item `forgejo.vernonmyers.cloud`).

7. **Registry login for pulls** on the VM (already required for the current
   deploy): `docker login forgejo.vernonmyers.cloud`.

## Running the pipeline by hand

Use **Actions → CI → Run workflow** (`workflow_dispatch`) to re-run the checks,
or push to `master` to publish and deploy.

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Jobs sit "Waiting" forever | No runner matches the `runs-on` label. Check **Settings → Actions → Runners** shows `openfamhub-vm` online with all three labels. |
| `publish`: `unauthorized` | `REGISTRY_TOKEN` is missing or lacks package write scope. |
| arm64 build fails or is extremely slow | binfmt/QEMU not installed (step 5), or the emulated `pip install` timed out. Re-run; the buildx cache speeds up later runs. |
| `deploy` succeeds but the site is stale | Check `docker compose ps` in `~/openfamhub`; the API should be `healthy` and `OPENFAMHUB_VERSION` should match `APP_VERSION`. |
| `builtin:checkout` fails | `git` on the runner host is older than 2.34.1. |
````

- [ ] **Step 2: Rewrite the `docs/deployment.md` CI section**

Replace the section at the bottom of `docs/deployment.md` (the `## CI` heading and its paragraph) with:

```markdown
## CI

CI runs on the self-hosted Gitea instance via Gitea Actions. `.gitea/workflows/ci.yml`
runs backend tests and frontend lint/build on every push and pull request, then
publishes `forgejo.vernonmyers.cloud/vernon/openfamhub-{api,web}` (amd64 + arm64)
and deploys the test VM on pushes to `master`. The one-time runner and secret
setup is in [ci.md](ci.md).
```

- [ ] **Step 3: Update the `AGENTS.md` CI gotcha**

Replace:

```markdown
- **CI** (`.github/workflows/build.yml`) runs on GitHub only. Forgejo has no runner yet.
```

with:

```markdown
- **CI** runs on the Gitea instance via Gitea Actions (`.gitea/workflows/ci.yml`), on a runner hosted on the test VM. It publishes the Forgejo registry and deploys on `master`; see [docs/ci.md](docs/ci.md).
```

- [ ] **Step 4: Check off the TODO item**

In `TODO.md`, change:

```markdown
- [ ] Move CI to Forgejo Actions once a runner exists (still GitHub Actions only).
```

to:

```markdown
- [x] Move CI to Forgejo Actions once a runner exists. Done: `.gitea/workflows/ci.yml` runs on a Gitea Actions runner on the test VM and publishes + deploys on `master` (see [docs/ci.md](docs/ci.md)).
```

- [ ] **Step 5: Verify the docs render and links resolve**

```bash
grep -n "ci.md" docs/deployment.md AGENTS.md TODO.md
grep -n "server \[dir\]" docs/ci.md || true
ls docs/ci.md
```

Expected: each reference found and `docs/ci.md` exists.

- [ ] **Step 6: Commit**

```bash
git add docs/ci.md docs/deployment.md AGENTS.md TODO.md
git commit -m "docs: document Gitea Actions CI and retire GitHub-only notes"
```

---

### Task 4: Enable Gitea Actions, register the runner, and verify end-to-end

This task is operational (it changes the VM and Gitea, not the repo). Run it from
the Mac; `ssh 192.168.10.80` is already configured with key auth.

**Files:**
- No repo files. Writes `/usr/local/bin/gitea-runner`, `~/gitea-runner/.runner`, and `/etc/systemd/system/gitea-runner.service` on `192.168.10.80`.

**Interfaces:**
- Consumes: `.gitea/workflows/ci.yml` (Task 2), `scripts/deploy.sh server` (Task 1), docs (Task 3).
- Produces: a registered runner `openfamhub-vm` with the three labels and a working end-to-end pipeline.

- [ ] **Step 1: Enable repository Actions and create the runner token**

In the Gitea web UI: **`vernon/OpenFamHub` → Settings → Actions**, enable Actions.
Then open **Settings → Actions → Runners** and copy a registration token.

- [ ] **Step 2: Verify the VM prerequisites**

```bash
ssh 192.168.10.80 'git --version; docker --version; docker buildx version | head -1; id -nG | tr " " "\n" | grep -x docker'
```

Expected: `git` ≥ 2.34.1, Docker present, buildx present, and `docker` appears in the group list.

- [ ] **Step 3: Install and register the runner**

```bash
ssh 192.168.10.80 'curl -fL -o /tmp/gitea-runner https://dl.gitea.com/gitea-runner/5.0.0/gitea-runner-5.0.0-linux-amd64 && sudo install -m 0755 /tmp/gitea-runner /usr/local/bin/gitea-runner && gitea-runner --version'
```

Then register (replace `<repo runner token>`; keep it out of logs):

```bash
ssh -T 192.168.10.80 'mkdir -p ~/gitea-runner && cd ~/gitea-runner && gitea-runner register --no-interactive --instance https://forgejo.vernonmyers.cloud --token "<repo runner token>" --name openfamhub-vm --labels "openfamhub:host,openfamhub-python:docker://python:3.12-slim,openfamhub-node:docker://node:22"'
```

Expected: `Runner registered successfully.` and `~/gitea-runner/.runner` created. Confirm in the UI that `openfamhub-vm` is listed with all three labels.

- [ ] **Step 4: Install the systemd unit and start it**

```bash
ssh 192.168.10.80 'sudo tee /etc/systemd/system/gitea-runner.service >/dev/null <<UNIT
[Unit]
Description=Gitea Actions runner
After=network-online.target docker.service
Wants=network-online.target

[Service]
User=vernon
WorkingDirectory=/home/vernon/gitea-runner
ExecStart=/usr/local/bin/gitea-runner daemon
Restart=always

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload && sudo systemctl enable --now gitea-runner && sleep 2 && systemctl is-active gitea-runner'
```

Expected: `active`, and the runner shows **Idle** in the UI.

- [ ] **Step 5: Install QEMU/binfmt for arm64 builds**

```bash
ssh 192.168.10.80 'docker run --privileged --rm tonistiigi/binfmt --install arm64 && ls /proc/sys/fs/binfmt_misc/ | grep -i qemu'
```

Expected: binfmt registers and a `qemu-aarch64` entry is listed.

- [ ] **Step 6: Create the `REGISTRY_TOKEN` repo secret**

In **Settings → Actions → Secrets**, add `REGISTRY_TOKEN` = the Gitea token with
package read/write scope (1Password Development item `forgejo.vernonmyers.cloud`).

- [ ] **Step 7: Verify checks on a branch push**

```bash
git push forgejo feat/0.30-security
```

Expected: a CI run starts in the repo's **Actions** tab; `backend` and `frontend` pass; no `publish`/`deploy` jobs.

- [ ] **Step 8: Verify publish + deploy on master**

Merge the branch to `master` and push (or open and merge a PR), then:

```bash
# Watch the run in the Actions tab, then confirm the deployed version:
ssh 192.168.10.80 'cd ~/openfamhub && docker compose ps && grep -E "^(REGISTRY|OPENFAMHUB_VERSION)=" .env'
curl -fsS https://openfamhub.vernonmyers.cloud/api/health && echo " site ok"
```

Expected: the `publish` job pushes amd64+arm64 `openfamhub-api`/`openfamhub-web` images to Forgejo Packages; `deploy` restarts the stack; `docker compose ps` shows `api` **healthy** with the new version, and `/api/health` responds.

- [ ] **Step 9: Record the outcome**

If every check passes, no commit is needed for this task. If a step reveals a
defect (label mismatch, token scope, QEMU build failure), fix it in Tasks 1-3 and
re-run. Do not leave the runner registered with a token that has write scope
beyond packages.

---

## Self-Review

**Spec coverage:** Runner + labels → Task 4; workflow jobs/triggers → Task 2; `deploy.sh server` → Task 1; repo changes (workflow, GH removal, docs, AGENTS, TODO) → Tasks 2-3; one-time setup and secrets → Tasks 3-4; verification → Tasks 4.7-4.8. All spec sections are covered.

**Placeholder scan:** No TBD/TODO; every code step contains full code; commands include expected output.

**Type consistency:** The three labels (`openfamhub`, `openfamhub-python`, `openfamhub-node`) are identical in Task 2's `runs-on` values, Task 3's docs, and Task 4's `--labels`. The subcommand name `server` and its `[dir]` argument are consistent across Task 1, Task 2's deploy job, and Task 3's docs. `REGISTRY_TOKEN` is the single secret name everywhere.

## Execution Handoff

After Task 4, the branch contains Tasks 1-3's commits plus this plan. Push to both
remotes (manual approval), then optionally open a PR.
