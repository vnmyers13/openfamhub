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
