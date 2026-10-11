# Infra Docs Hardening Design

**Goal:** Make the deployment path match the operational reality discovered during the 2026-10-11 deploy, and fix the small infrastructure defects that block repeatable releases.

**Scope:** This pass covers deployment docs, deploy script safety, CI publishing behavior, frontend static-cache headers, and manual backup guidance. It does not include the larger production startup/migration smoke test; that remains a separate review-backlog item.

## Background

The deploy to `192.168.10.80` exposed three operational gaps:

- Existing remote `.env` files can miss `REGISTRY` or `OPENFAMHUB_VERSION`; `scripts/deploy.sh remote` only replaces `OPENFAMHUB_VERSION` when present.
- The VM needed to resolve `forgejo.vernonmyers.cloud` to the LAN Forgejo host before pulling images.
- Publishing required the Development vault item `forgejo.vernonmyers.cloud` from 1Password and a Forgejo token with package write access.

The review backlog also identified related infra issues: GitHub Actions publishes `latest` from both `main` and `master`, service-worker files may be cached immutable for a year, and manual backup docs copy only the SQLite main database while WAL mode is active.

## Design

### Deploy Script

Modify `scripts/deploy.sh remote` so existing remote `.env` files are updated safely instead of assuming required image variables already exist.

- Upsert `REGISTRY=$REGISTRY` in `~/openfamhub/.env`.
- Upsert `OPENFAMHUB_VERSION=$VERSION` in `~/openfamhub/.env`.
- Preserve all existing secrets and local settings, including `SECRET_KEY`, `ALLOWED_ORIGINS`, ports, timezone, and backup settings.
- Run `docker compose config >/dev/null` on the remote after copying files and updating `.env`, before `docker compose pull`, so invalid image references fail early.

The helper can stay inside `deploy_remote()` to keep the script small. Use POSIX shell on the remote side and avoid printing secrets.

### GitHub Actions

Change `.github/workflows/build.yml` so CI validates pull requests without publishing images, and image publishing no longer lets the retired `main` line overwrite `latest`.

- Add a `pull_request` trigger for `master`.
- Keep backend tests and frontend lint/build running for pushes and PRs.
- Gate the Docker image build/push job with `if: github.event_name == 'push' && github.ref == 'refs/heads/master'`.
- Keep `latest` tags only on canonical `master` pushes.

This keeps GitHub Actions useful while Forgejo Actions has no runner yet.

### Frontend Static Cache Headers

Update `frontend/nginx.conf` so PWA control files are not served with one-year immutable caching.

- Add exact no-cache locations for `/sw.js`, `/registerSW.js`, and `/manifest.webmanifest`.
- Add a Workbox no-cache rule for `/workbox-*.js`.
- Restrict immutable caching to hashed assets under `/assets/` and static image/font extensions outside PWA control files.

This keeps app-shell updates reliable for wall displays and phone installs.

### Documentation

Update docs to reflect the current deployment workflow.

- `docs/deployment.md`: document using the 1Password Development item `forgejo.vernonmyers.cloud` for Docker login without exposing the token.
- `docs/deployment.md`: add a LAN DNS/hosts note for `forgejo.vernonmyers.cloud` resolving to the Forgejo host, currently `192.168.10.2`, when a VM cannot resolve it.
- `docs/deployment.md`: replace the manual pre-upgrade backup command with a WAL-safe method: stop the API before copying the main database, or use SQLite online backup from inside the API container.
- `docs/deployment.md`: update troubleshooting for missing `REGISTRY` or `OPENFAMHUB_VERSION` to point at the new upsert behavior and `docker compose config` validation.
- `README.md`: keep high-level instructions concise and point to deployment docs for 1Password, registry login, and VM DNS details.
- `TODO.md`: mark the completed infra review backlog items after implementation passes verification.

### Verification

Run these checks before claiming the pass is complete:

- `cd backend && source .venv/bin/activate && pytest -v`
- `cd frontend && npm run build`
- `ssh 192.168.10.80 'cd ~/openfamhub && docker compose config >/dev/null'` if the VM is reachable
- Inspect `git diff` to confirm no secrets or generated files are included

Do not commit untracked `graphify-out/` or `Claude outputs/`.

## Out Of Scope

- Production startup/migration smoke test.
- Forgejo Actions migration.
- Backend security, iCal correctness, and frontend wall/auth backlog items outside infra.
- Version bump beyond `0.30`.

## Acceptance Criteria

- Repeat remote deploys work when an existing remote `.env` lacks image variables.
- PRs to `master` run validation but do not publish images.
- GHCR `latest` is not published from `main`.
- Service worker, Workbox, and manifest files are served with no-cache headers.
- Manual backup docs are safe for SQLite WAL mode.
- Documentation describes the 1Password-backed registry login and LAN DNS requirement without revealing credentials.
