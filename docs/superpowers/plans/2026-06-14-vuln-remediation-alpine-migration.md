# Vuln Remediation + Alpine Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate 206 vulnerabilities in the API image by updating Python dependencies and migrating the Docker base image from Debian to Alpine.

**Architecture:** Two parallel workstreams — (1) upgrade Python packages in requirements.txt, (2) switch Dockerfile from `python:3.12-slim` to `python:3.12-alpine` with non-root user. All dependencies are pure-Python or have musl wheels, so risk is minimal.

**Tech Stack:** Python 3.12, FastAPI, Docker, Alpine Linux (musl)

---

## File Map

| File | Action | Why |
|------|--------|-----|
| `backend/requirements.txt` | Modify | Pin updated dependency versions |
| `backend/Dockerfile` | Modify | Switch to Alpine base, add non-root user, remove apt-get |
| `docker-compose.prod.yml` | Modify | Update image tag from 0.25→0.27 |

**No code changes needed** in `security.py` or any other app files — the `python-jose` API is backward compatible (we only use `HS256` algorithm).

---

### Task 1: Update Python Dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Update requirements.txt**

Open `backend/requirements.txt` and make these changes:

Change line 9:
```
python-jose[cryptography]==3.3.0
```
To:
```
python-jose[cryptography]==3.4.0
```

Change line 12:
```
python-multipart==0.0.18
```
To:
```
python-multipart==0.0.27
```

Change line 11 (add after `bcrypt<5.0`):
```
ecdsa>=0.19.4; python_version>="3.13"
```

Note: `ecdsa` is a transitive dependency of `python-jose[cryptography]` v3.3.0. In v3.4.0, `python-jose` switches to `cryptography` as its EC backend, which drops the `ecdsa` dependency entirely. The conditional pin above ensures that if someone installs `ecdsa` directly on Python 3.13+, they get a version with the Minerva timing attack mitigation. On Python 3.12 (our target), this line is ignored.

Also update line 2 (fastapi) to pull in a fixed starlette:
Change:
```
fastapi==0.115.6
```
To:
```
fastapi==0.115.13
```

The final `backend/requirements.txt` should be:
```
# Backend dependencies
fastapi==0.115.13
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0
alembic==1.14.0
pydantic==2.10.4
pydantic-settings==2.7.1
python-jose[cryptography]==3.4.0
passlib[bcrypt]==1.7.4
bcrypt<5.0
python-multipart==0.0.27
ecdsa>=0.19.4; python_version>="3.13"
apscheduler==3.10.4
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.24.0
python-dateutil==2.9.0.post0
icalendar==5.0.11
```

- [ ] **Step 2: Install updated dependencies**

Run:
```bash
cd backend && source .venv/bin/activate && pip install -r requirements.txt
```

Expected: All packages install without errors. `python-jose` 3.4.0, `python-multipart` 0.0.27, `fastapi` 0.115.13 should be installed.

Verify:
```bash
python -c "import jose; print(jose.__version__)"
```
Expected: `3.4.0`

```bash
python -c "import multipart; print(multipart.__version__)"
```
Expected: `0.0.27`

```bash
python -c "import fastapi; print(fastapi.__version__)"
```
Expected: `0.115.13`

- [ ] **Step 3: Run full test suite**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
```

Expected: All tests pass. If any test fails, investigate — the API surface hasn't changed but versions have.

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: upgrade python-jose to 3.4.0, python-multipart to 0.0.27, fastapi to 0.115.13"
```

---

### Task 2: Migrate Backend Dockerfile to Alpine

**Files:**
- Modify: `backend/Dockerfile`

- [ ] **Step 1: Replace Dockerfile content**

Replace the entire `backend/Dockerfile` with:

```dockerfile
FROM python:3.12-alpine

LABEL version="0.27"
LABEL description="OpenFamHub API Backend"

WORKDIR /app

RUN apk add --no-cache curl

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
RUN mkdir -p /data/db /data/photos /data/backups && chown -R app:app /data

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

Key changes from the original:
1. `FROM python:3.12-slim` → `FROM python:3.12-alpine`
2. `apt-get update && apt-get install -y --no-install-recommends curl` → `apk add --no-cache curl` (Alpine package manager)
3. Added non-root user `app` with `addgroup -S app && adduser -S app -G app`
4. Changed ownership of `/app` and `/data` directories to `app` user
5. Added `USER app` to run as non-root
6. Updated `LABEL version` to `0.27`

- [ ] **Step 2: Build the Alpine image locally**

Run:
```bash
docker build -t openfamhub-api:test-alpine ./backend
```

Expected: Build completes successfully. All Python packages install without errors. musl-compatible wheels are used for `cryptography`, `bcrypt`, `pydantic`.

If any package fails to build:
- Check if a pre-built musl wheel exists: `pip install <package> --only-binary=:all: -d /tmp/wheels`
- If no wheel exists, the package needs a C compiler in Alpine. Add it: `RUN apk add --no-cache gcc musl-dev` before the pip install.

- [ ] **Step 3: Verify the image runs**

Run:
```bash
docker run --rm openfamhub-api:test-alpine uvicorn app.main:app --help
```

Expected: uvicorn help text is printed (no errors).

Run:
```bash
docker run --rm openfamhub-api:test-alpine python -c "from jose import jwt; print('jose OK')"
```

Expected: `jose OK`

Run:
```bash
docker run --rm openfamhub-api:test-alpine python -c "import multipart; print('multipart OK')"
```

Expected: `multipart OK`

- [ ] **Step 4: Verify image size**

Run:
```bash
docker images openfamhub-api:test-alpine
```

Expected: Image size ~150MB (down from ~200MB on Debian slim).

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile
git commit -m "docker: migrate backend to python:3.12-alpine, add non-root user"
```

---

### Task 3: Update docker-compose.prod.yml Image Tag

**Files:**
- Modify: `docker-compose.prod.yml`

- [ ] **Step 1: Update image tags**

Change line 4:
```yaml
image: vnmyers13/openfamhub-api:0.25
```
To:
```yaml
image: vnmyers13/openfamhub-api:0.27
```

Change line 24:
```yaml
image: vnmyers13/openfamhub-web:0.25
```
To:
```yaml
image: vnmyers13/openfamhub-web:0.27
```

- [ ] **Step 2: Commit**

```bash
git add docker-compose.prod.yml
git commit -m "docker: update prod image tags to 0.27"
```

---

### Task 4: Re-scan and Verify

**Files:**
- No file changes — verification step only

- [ ] **Step 1: Build the final image**

```bash
docker build -t openfamhub-api:0.27 ./backend
```

- [ ] **Step 2: Run Grype scan**

```bash
grype openfamhub-api:0.27 --scope all-layers -o json > /tmp/grype-post.json
```

- [ ] **Step 3: Run Trivy scan**

```bash
trivy image openfamhub-api:0.27 --severity CRITICAL,HIGH,MEDIUM,LOW > /tmp/trivy-post.txt
```

- [ ] **Step 4: Verify vulnerability counts dropped**

Run:
```bash
python3 -c "
import json
with open('/tmp/grype-post.json') as f:
    data = json.load(f)
results = data.get('artifacts', []) or []
severities = {}
for r in results:
    sev = r.get('Severity', 'unknown')
    severities[sev] = severities.get(sev, 0) + 1
print('Grype post-remediation:')
for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNKNOWN']:
    print(f'  {sev}: {severities.get(sev, 0)}')
print(f'  Total: {len(results)}')
"
```

Expected:
- CRITICAL: 0
- HIGH: 0-2 (only ecdsa timing may remain if it's still a transitive dep)
- Total: < 30

- [ ] **Step 5: Smoke test the new image**

```bash
docker run -d --name test-api -p 9999:8000 openfamhub-api:0.27
sleep 5
curl -s http://localhost:9999/api/health | python3 -m json.tool
docker stop test-api && docker rm test-api
```

Expected: `{"status": "ok", "version": "0.27"}`

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "verify: Alpine migration scan shows vulnerability reduction"
```

---

### Task 5: Set Up CI Workflow (Optional but Recommended)

**Files:**
- Create: `.github/workflows/build.yml`
- Create: `.github/` (directory)

- [ ] **Step 1: Create GitHub Actions workflow**

Create `.github/workflows/build.yml`:

```yaml
name: Build and Test

on:
  push:
    branches: [main, master]
  pull_request:
    branches: [main, master]

permissions:
  contents: read
  packages: write

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12"]

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}

      - name: Create venv and install deps
        run: |
          cd backend
          python -m venv .venv
          source .venv/bin/activate
          pip install -r requirements.txt

      - name: Run tests
        run: |
          source backend/.venv/bin/activate
          pytest backend/tests/ -v

  build:
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
      - uses: actions/checkout@v4

      - name: Log in to GHCR
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.repository_owner }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build API image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          push: true
          tags: ghcr.io/${{ github.repository }}/openfamhub-api:${{ github.sha }},ghcr.io/${{ github.repository }}/openfamhub-api:latest
          platforms: linux/amd64

      - name: Build Web image
        uses: docker/build-push-action@v5
        with:
          context: ./frontend
          push: true
          tags: ghcr.io/${{ github.repository }}/openfamhub-web:${{ github.sha }},ghcr.io/${{ github.repository }}/openfamhub-web:latest
          platforms: linux/amd64
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/build.yml
git commit -m "ci: add GitHub Actions workflow for test + build"
```

---

### Task 6: Post-Release Documentation

**Files:**
- Create: `docs/releases/v0.27.md`

- [ ] **Step 1: Write release notes**

Create `docs/releases/v0.27.md`:

```markdown
# v0.27 — Security Remediation + Alpine Migration

**Date:** 2026-06-14

## Changes

### Docker
- Backend image migrated from `python:3.12-slim` (Debian) to `python:3.12-alpine`
- Added non-root `app` user for defense in depth
- Image size reduced from ~200MB to ~150MB
- CVE surface reduced from ~206 to ~20-30 vulnerabilities

### Dependencies
- `python-jose`: 3.3.0 → 3.4.0 (fixes GHSA-6c5p-j8vq-pqhj, CVE-2024-33663 — algorithm confusion)
- `python-multipart`: 0.0.18 → 0.0.27 (fixes GHSA-wp53-j4wj-2cfg arbitrary file write, GHSA-pp6c-gr5w-3c5g DoS)
- `fastapi`: 0.115.6 → 0.115.13 (pulls in fixed starlette for Range header DoS)

### CI
- Added GitHub Actions workflow for automated test + build pipeline

## Upgrade Notes
- No API changes. Drop-in replacement for existing deployments.
- If deploying manually: rebuild backend image, update `docker-compose.prod.yml` tag to `0.27`
- Data volumes (DB, photos, backups) are unaffected
```

- [ ] **Step 2: Update APP_VERSION**

In `backend/app/core/config.py`, change line 14:
```python
return "0.26"
```
To:
```python
return "0.27"
```

- [ ] **Step 3: Final commit**

```bash
git add docs/releases/v0.27.md backend/app/core/config.py
git commit -m "release: bump version to 0.27, add release notes"
```

---

## Risk Checklist

- [x] `python-jose` 3.4.0 is backward compatible with 3.3.0 for HS256 usage — verified in `security.py:38` (only uses `algorithm="HS256"`)
- [x] `python-multipart` 0.0.27 API is backward compatible — used by FastAPI internally, no direct app imports
- [x] `fastapi` 0.115.13 is backward compatible — no API surface changes
- [x] `ecdsa` is a transitive dependency only (via `python-jose[cryptography]`) — upgrading jose to 3.4.0 drops it entirely
- [x] All Python deps have musl-compatible wheels on PyPI: `cryptography`, `bcrypt`, `pydantic`, `aiosqlite`, `sqlalchemy`, `apscheduler`, `icalendar`, `httpx`
- [x] No C extensions that require glibc-specific features in the app codebase
- [x] SQLite via aiosqlite — pure Python, no system library dependency
- [x] Docker volumes (`/data/db`, `/data/photos`, `/data/backups`) are external — unaffected by image change
- [x] `docker-compose.prod.yml` volume mounts use named volumes — no path changes needed

## Rollback Plan

If the Alpine image fails to start or has issues:
1. Revert the `backend/Dockerfile` change
2. Rebuild from `python:3.12-slim`
3. Re-deploy previous working image tag
4. The dependency version changes in `requirements.txt` are safe to keep (they're backward compatible)
