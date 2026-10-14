# CI/CD (Gitea Actions)

CI runs on the self-hosted Gitea instance (`https://forgejo.vernonmyers.cloud`).
Workflows live in `.gitea/workflows/` and execute on a runner installed on the
test VM (`192.168.10.80`). The runner is registered with the primary instance
only, so pushes to the mirrors (`192.168.10.101:3002`, `192.168.10.102:3002`)
or GitHub don't run CI.

## Pipeline

`.gitea/workflows/ci.yml` has seven jobs:

| Job | Runs on | Trigger |
|---|---|---|
| `backend` | `openfamhub-python` (container `python:3.12`) | every push and PR |
| `frontend` | `openfamhub-node` (container `node:22`) | every push and PR |
| `version` | `openfamhub` (host) | push to `master` or PR to `master` |
| `publish` | `openfamhub` (host) | push to `master` only |
| `deploy` | `openfamhub` (host) | push to `master` only |
| `trivy` | `openfamhub` (host) | push to `master` only, after `publish`; never blocks |
| `issues` | `openfamhub` (host) | push to `master` only, after `deploy`; never blocks |

`backend` runs `pytest --cov` from `backend/` (unit, API and a startup test that
boots the app to check migrations and scheduled jobs) and fails below the coverage
floor in `backend/.coveragerc`. `frontend` runs `npm run lint`, `npm run test:coverage`
(Vitest; fails below the thresholds in `vitest.config.ts`), the build-info tests and
`npm run build`. The runner's `node:22` image satisfies `engines` in `frontend/package.json` (`^22.22.2 || >=24.15.0`, set by jsdom and Vitest); locally use Node 24 (`frontend/.nvmrc`). `version` checks the
`VERSION` sequence and runs the script test harnesses in `scripts/tests/`. One of them, `exec-bits-test.sh`, fails if a script under `scripts/` or `.githooks/` is committed without its executable bit (that broke `publish` for build 1).

`publish` builds `linux/amd64` and `linux/arm64` images for `openfamhub-api` and
`openfamhub-web` and pushes them to the Forgejo registry. `deploy` then runs
`scripts/deploy.sh server "$HOME/openfamhub" <release>`, where `<release>` is the
exact release string computed by the `version` job and used by `publish`. Passing
it explicitly prevents the deploy from reusing an older `OPENFAMHUB_VERSION` from
the runner environment or the server's `.env`. The server command copies the
compose bundle into `~/openfamhub`, pins `REGISTRY`/`OPENFAMHUB_VERSION`, and
pulls + restarts the stack.

**Version numbering.** `VERSION` (repo root) holds a single integer; the `pre-commit`
hook bumps it per commit; `scripts/check-version.sh` enforces `+1` on `master`'s
first-parent chain and "greater than base" on branches; the release name comes from `scripts/release-name` (`0.<n>` below 100; then 1, 1.01 … 1.99, 2, 2.01);
tags are `v<release>` pushed to `forgejo`. `deploy` pins that exact tag in
`~/openfamhub/.env`. To see what's running, check **Help & About** (login page or sidebar) or
`curl -s https://openfamhub.vernonmyers.cloud/api/health` (`build` and `commit` fields). On the LAN/Twingate path, that hostname should resolve to the upstream Caddy host at `192.168.10.2`; if DNS points somewhere else, the browser may be looking at a stale host even when `192.168.10.80:8080` is already updated.
To roll the test VM back to an earlier build, run `scripts/deploy.sh server "$HOME/openfamhub" <release>`
on the VM (or `scripts/deploy.sh remote test <release>` from the Mac).

Production is not automatic. After a build is checked on `test`, promote that exact
release with an SSH host alias such as `prod`:

```bash
PUBLIC_URL=https://<prod-url> scripts/deploy.sh promote prod <release>
```

`promote` requires the release argument so production never silently takes whatever
build happens to be current in the checkout.

Pull requests run the checks only; they never publish or deploy.

## Trivy scan

After `publish`, the `trivy` job runs `scripts/trivy-scan.sh`, which scans the
images it just pushed (`openfamhub-api:<release>` and `openfamhub-web:<release>`, the exact
build, not `latest`) with the pinned `aquasec/trivy` image on the runner host. It
prints a HIGH/CRITICAL table for each image in the job log and uploads the full JSON
reports as the `trivy-reports` artifact (kept 30 days). The scan, upload and issue steps are
`continue-on-error`, and `deploy` doesn't wait for it, so findings or a scanner
outage never turn CI red or hold up a release. The vulnerability database is cached
in `~/.cache/trivy` on the VM.

The scanner is pinned to a version tag rather than pulled through
`aquasecurity/trivy-action`: Trivy 0.69.4 and most `trivy-action` tags were
replaced with malicious code in March 2026 (CVE-2026-33634). Change `TRIVY_IMAGE` in
`scripts/trivy-scan.sh` deliberately, ideally to an `@sha256:` digest, and never to
`latest`.

**Backlog issues.** With `CREATE_ISSUES: "1"` in the job (the default) and the
`ISSUES_TOKEN` secret set (the older name `TRIVY_ISSUE_TOKEN` also works), `scripts/create_trivy_issues.py` opens one issue per
HIGH/CRITICAL finding, titled `[trivy] <CVE>: <package> in openfamhub-<api|web>`.
Before opening one it searches existing issues, open **and closed**, for that title,
so a finding gets a single issue across releases and closing an issue by hand (risk
accepted) stops it coming back. Open `[trivy]` issues for an image whose finding is
missing from the latest scan are closed, with a comment naming the build. At most 20 issues are opened per run
(`TRIVY_MAX_ISSUES`); the rest follow on later runs. Without the secret the step
logs that it's skipping. To set it up, create a Forgejo token with
**issue: read,write** scope on the repository and add it under **Settings → Actions →
Secrets** as `ISSUES_TOKEN`. To turn issue creation off, set `CREATE_ISSUES: "0"`.

To try it locally (needs Docker and registry access):

```bash
scripts/trivy-scan.sh 1               # writes trivy-reports/trivy-{api,web}.json
TRIVY_DRY_RUN=1 python3 scripts/create_trivy_issues.py \
  https://forgejo.vernonmyers.cloud vernon/OpenFamHub openfamhub-api trivy-reports/trivy-api.json
```

## Issues job

After `deploy`, the `issues` job runs `scripts/issues.py close-done --apply`, which
closes open issues that TODO.md marks done (every line naming the issue is ticked),
then `scripts/issues.py triage --report-issue`, which prints open issues by priority
and where they differ from TODO.md, and writes the same report to a pinned
**Triage report** issue (created on the first run). When new items need attention it
comments on that issue, so Forgejo notifies you; edits alone don't. It uses the same `ISSUES_TOKEN` secret and never fails the
pipeline. The process around it is in [releasing.md](releasing.md).

`scripts/tests/issues-test.sh` and `scripts/tests/trivy-test.sh` run against a fake
Forgejo (`scripts/tests/fake_forgejo.py`). `scripts/tests/trivy-test.sh` covers both Trivy scripts against a fake Forgejo and a fake
`docker`; it runs in the `version` job with the other harnesses (needs `python3` on
the runner host).

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
| `deploy` succeeds but the site is stale | Check `docker compose ps` in `~/openfamhub`; the API should be `healthy` and `OPENFAMHUB_VERSION` should match `$(scripts/release-name)`. |
| `Required test coverage of 93% not reached` / `ERROR: Coverage for … does not meet threshold` | New code without tests. Add tests; don't lower the floor. `pytest --cov` (backend) and `npm run test:coverage` (frontend) show the uncovered lines. |
| `trivy`: `unauthorized` or `manifest unknown` | `REGISTRY_TOKEN` can't read packages, or `publish` didn't push `<release>`. The job is non-blocking; re-run it after fixing. |
| `trivy`: upload step fails | The Forgejo instance doesn't support `actions/upload-artifact@v4`. The table in the scan step's log still shows the findings. |
| `trivy` or `issues`: `HTTP 401/403` | `ISSUES_TOKEN` is missing **issue: read,write** scope or has expired. A `404` on a private repo can mean the token also needs **repository: read**. |
| `builtin:checkout` fails with `needs git on PATH` | The job's container image has no `git` (e.g. a `-slim` image). Use an image that ships `git` (the `openfamhub-python` label maps to `python:3.12`). `git` on the runner host itself must also be ≥ 2.34.1. |
