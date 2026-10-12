# Gitea Actions CI/CD Design

**Goal:** Run OpenFamHub CI on the self-hosted Gitea instance (`forgejo.vernonmyers.cloud`, Gitea 1.27.3) and extend it to publish multi-arch images and deploy the test VM, replacing the GitHub-Actions-only pipeline that currently cannot run on the LAN.

**Scope:** This pass covers a Gitea Actions runner on the test VM, a `.gitea/workflows/ci.yml` pipeline (checks → publish → deploy), a new local `scripts/deploy.sh server` subcommand for the registry-pull deploy, secret/one-time host setup, documentation, and retiring the GitHub Actions workflow. It does not change application code, the backend test suite, the 0.30 version, or the existing `remote` deploy path.

## Background

- The Gitea instance reports version `1.27.3` with no `+forgejo` suffix, so it is **Gitea**. Actions is enabled instance-wide by default (since 1.21), but off per repository, and **no runners are registered** (repo and instance runner lists are empty).
- `.github/workflows/build.yml` runs tests and frontend lint/build on GitHub and publishes `ghcr.io` images. It cannot run on the LAN and GitHub is a mirror only, so publishing there duplicates work and does not feed the Forgejo registry that the VM pulls from.
- The test VM `192.168.10.80` is x86_64 with Docker Compose v5.6.0 and buildx v0.37.1, **no QEMU/binfmt**, and a full checkout at `~/openfamhub` (on `master`, stale at `b3b4024`). The live stack runs published registry images `forgejo.vernonmyers.cloud/vernon/openfamhub-{api,web}:0.30` from `~/openfamhub/compose.yml` + `~/openfamhub/.env` (`REGISTRY`, `OPENFAMHUB_VERSION=0.30`).
- Today the release is manual: `scripts/deploy.sh publish` on the Mac, then `scripts/deploy.sh remote test`. The runner replaces the manual publish/remote steps with an in-LAN pipeline.
- TODO.md item "Move CI to Forgejo Actions once a runner exists (still GitHub Actions only)" tracks this work.

## Design

### Runner

Install the `gitea-runner` binary (v5.x, the former `act_runner`) on the test VM and run it as a systemd service, because the `host` executor runs steps on the machine where the runner process lives. Running the runner itself in a container would make "host" mean the container, not the VM, so it must run natively.

- Runs as user `vernon` (member of the `docker` group) with access to `~/openfamhub` and `.env`.
- Registered at **repository level** with three labels that select the executor per job:
  - `openfamhub:host` — publish and deploy, using native VM Docker paths and the existing tooling.
  - `openfamhub-python:docker://python:3.12-slim` — backend tests in a container.
  - `openfamhub-node:docker://node:22` — frontend lint/build in a container.
- Registration is non-interactive:

  ```bash
  gitea-runner register --no-interactive \
    --instance https://forgejo.vernonmyers.cloud \
    --token <repo runner token> \
    --name openfamhub-vm \
    --labels 'openfamhub:host,openfamhub-python:docker://python:3.12-slim,openfamhub-node:docker://node:22'
  ```

  The registration token comes from the repo's `Settings → Actions → Runners`. The resulting `.runner` file is mode `600` and is not committed.
- Labels are set at registration; a `runner.labels` entry in `config.yaml` would override the `--labels` flag, so only one is used. A `config.yaml` sets `container.sweep: false` and enables a local cache; the systemd unit runs `gitea-runner -c <config> daemon`.
- Because `openfamhub:host` jobs run with the VM's real Docker access (not through the runner's Docker proxy), the deploy job's `docker compose up` is **not** swept. `container.sweep: false` is set as a belt-and-braces guard.

### One-time host and repo setup

Documented in `docs/ci.md`, performed once by hand:

1. Enable Actions in the repository settings.
2. Ensure `git ≥ 2.34.1` on the VM; install the `gitea-runner` binary (e.g. `/usr/local/bin/gitea-runner`) and register it as above.
3. Create the systemd unit `gitea-runner.service` (`User=vernon`, `Restart=always`).
4. Register QEMU binfmt once for arm64 builds: `docker run --privileged --rm tonistiigi/binfmt --install arm64`.
5. Create the repository secret `REGISTRY_TOKEN`: a Gitea token with **package: read,write** scope, sourced from the 1Password Development item `forgejo.vernonmyers.cloud` and never printed.
6. Confirm `docker login forgejo.vernonmyers.cloud` works on the VM for pulls (already required today).

Workflows use `builtin:checkout` instead of `actions/checkout`, so the runner does not need Node or outbound GitHub access to download actions.

### Pipeline: `.gitea/workflows/ci.yml`

- Triggers: `push` (all branches), `pull_request`, `workflow_dispatch`.
- Workflow-level `env.SECRET_KEY` supplies the throwaway value the backend tests need.
- Jobs:
  - `backend` (`runs-on: openfamhub-python`): `builtin:checkout`, then `pip install -r backend/requirements.txt pytest pytest-asyncio httpx` and `pytest backend/tests -v`.
  - `frontend` (`runs-on: openfamhub-node`, `working-directory: frontend`): `builtin:checkout`, then `npm ci`, `npm run lint`, `npm run build`.
  - `publish` (`runs-on: openfamhub`, `needs: [backend, frontend]`, `if: gitea.event_name == 'push' && gitea.ref == 'refs/heads/master'`): `builtin:checkout`, `docker login` with `secrets.REGISTRY_TOKEN`, then `scripts/deploy.sh publish` (amd64+arm64, reusing existing tooling).
  - `deploy` (`runs-on: openfamhub`, `needs: [publish]`, same `if`): `builtin:checkout`, then `scripts/deploy.sh server "$HOME/openfamhub"`.
- Pull requests run `backend` and `frontend` only; `publish` and `deploy` are gated to master pushes.

### `scripts/deploy.sh server [dir]`

Add a local, no-SSH counterpart to `remote` for the registry-pull deploy. It mirrors the existing `remote` steps without `ssh`/`scp`:

- Copy `deploy/compose.yml` → `<dir>/compose.yml` and `config/{Caddyfile,Caddyfile.proxy,routes.caddy}` → `<dir>/config/`.
- Upsert `REGISTRY` and `OPENFAMHUB_VERSION` in `<dir>/.env` using the same `upsert_env` logic as `remote`; create the file from `deploy/env.template` with a generated `SECRET_KEY` if absent.
- Validate `docker compose config >/dev/null` in `<dir>` before pulling.
- `docker compose pull && docker compose up -d --remove-orphans`, then wait for the API healthcheck (reuse `HEALTH_WAIT`).
- Extend the `usage` text and the `case` dispatch with `server)`. `remote` stays unchanged.

### Repository changes

- Add `.gitea/workflows/ci.yml`.
- Remove `.github/workflows/build.yml` (GitHub is a mirror; Gitea owns CI and publishing).
- Add `docs/ci.md` describing the one-time runner/secret setup and how the pipeline works.
- `docs/deployment.md`: rewrite the CI section to point at Gitea Actions and `docs/ci.md`.
- `AGENTS.md`: replace the "CI runs on GitHub only; Forgejo has no runner yet" gotcha with the Gitea Actions reality.
- `TODO.md`: mark "Move CI to Forgejo Actions once a runner exists" done.

### Verification

- `cd backend && source .venv/bin/activate && pytest -q` (unchanged) and `cd frontend && npm run lint && npm run build` still pass locally.
- Push a branch → `backend` and `frontend` jobs appear and pass in the Gitea Actions tab.
- Open a PR to `master` → checks run, `publish`/`deploy` do not.
- Merge to `master` → `publish` produces amd64+arm64 images in Forgejo Packages, then `deploy` runs and `docker compose ps` on the VM shows the new `OPENFAMHUB_VERSION` healthy; `https://openfamhub.vernonmyers.cloud` loads.
- `workflow_dispatch` can re-run the pipeline manually.
- Inspect `git diff` to confirm no secrets or generated files are committed (do not commit `graphify-out/` or `Claude outputs/`).

## Out Of Scope

- Application code, migrations, and the 0.30 version.
- The existing `remote` deploy path (kept working).
- Two runners or Kubernetes executors; a single host+docker runner is sufficient.
- Frontend test-runner introduction and other review-backlog items.

## Acceptance Criteria

- A Gitea Actions runner is registered to `vernon/OpenFamHub` and visible in repo settings.
- Pushes and PRs run backend tests and frontend lint/build in Gitea Actions.
- Only pushes to `master` publish `openfamhub-api`/`openfamhub-web` (amd64+arm64) to the Forgejo registry.
- After a master push, the test VM's stack runs the newly published version and reports healthy without a manual step.
- `scripts/deploy.sh server ~/openfamhub` performs the registry-pull deploy locally and is reused by the workflow.
- The GitHub Actions workflow is removed and docs describe the Gitea pipeline and one-time setup.
