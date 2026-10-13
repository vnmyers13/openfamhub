# CI/CD (Gitea Actions)

CI runs on the self-hosted Gitea instance (`https://forgejo.vernonmyers.cloud`).
Workflows live in `.gitea/workflows/` and execute on a runner installed on the
test VM (`192.168.10.80`). The runner is registered with the primary instance
only, so pushes to the mirrors (`192.168.10.101:3002`, `192.168.10.102:3002`)
or GitHub don't run CI.

## Pipeline

`.gitea/workflows/ci.yml` has five jobs:

| Job | Runs on | Trigger |
|---|---|---|
| `backend` | `openfamhub-python` (container `python:3.12`) | every push and PR |
| `frontend` | `openfamhub-node` (container `node:22`) | every push and PR |
| `version` | `openfamhub` (host) | push to `master` or PR to `master` |
| `publish` | `openfamhub` (host) | push to `master` only |
| `deploy` | `openfamhub` (host) | push to `master` only |

`backend` runs `pytest --cov` from `backend/` (unit, API and a startup test that
boots the app to check migrations and scheduled jobs) and fails below the coverage
floor in `backend/.coveragerc`. `frontend` runs `npm run lint`, `npm run test:coverage`
(Vitest; fails below the thresholds in `vitest.config.ts`), the build-info tests and
`npm run build`. `version` checks the
`VERSION` sequence and runs the script test harnesses in `scripts/tests/`.

`publish` builds `linux/amd64` and `linux/arm64` images for `openfamhub-api` and
`openfamhub-web` and pushes them to the Forgejo registry. `deploy` then runs
`scripts/deploy.sh server "$HOME/openfamhub"`, which copies the compose bundle
into `~/openfamhub`, pins `REGISTRY`/`OPENFAMHUB_VERSION`, and pulls + restarts
the stack.

**Version numbering.** `VERSION` (repo root) holds a single integer; the `pre-commit`
hook bumps it per commit; `scripts/check-version.sh` enforces `+1` on `master`'s
first-parent chain and "greater than base" on branches; the release string is `0.<n>`;
tags are `v0.<n>` pushed to `forgejo`. `deploy` pins that exact tag in
`~/openfamhub/.env`. To see what's running, check **Help & About** (login page or sidebar) or
`curl -s https://openfamhub.vernonmyers.cloud/api/health` (`build` and `commit` fields).
To roll the test VM back to an earlier build, run `scripts/deploy.sh server "$HOME/openfamhub" 0.<n>`
on the VM (or `scripts/deploy.sh remote test 0.<n>` from the Mac).

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
     --labels 'openfamhub:host,openfamhub-python:docker://python:3.12,openfamhub-node:docker://node:22'
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
| `deploy` succeeds but the site is stale | Check `docker compose ps` in `~/openfamhub`; the API should be `healthy` and `OPENFAMHUB_VERSION` should match `0.$(cat VERSION)`. |
| `Required test coverage of 93% not reached` / `ERROR: Coverage for … does not meet threshold` | New code without tests. Add tests; don't lower the floor. `pytest --cov` (backend) and `npm run test:coverage` (frontend) show the uncovered lines. |
| `builtin:checkout` fails with `needs git on PATH` | The job's container image has no `git` (e.g. a `-slim` image). Use an image that ships `git` (the `openfamhub-python` label maps to `python:3.12`). `git` on the runner host itself must also be ≥ 2.34.1. |
