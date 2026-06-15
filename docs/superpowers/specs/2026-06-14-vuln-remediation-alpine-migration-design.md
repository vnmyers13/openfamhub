# Vulnerability Remediation + Alpine Migration Plan

**Date:** 2026-06-14
**Target Image:** `vnmyers13/openfamhub-api:0.26` → post-remediation
**Scanners:** Grype (206 vulns), Trivy (190 vulns)

---

## Executive Summary

The current API image (`python:3.12-slim`, Debian bookworm/trixie) has **206 vulnerabilities** (Grype) / **190** (Trivy):
- **Critical: 8** (python-jose, Python stdlib, libc, perl)
- **High: 35** (python-multipart, ecdsa, starlette, curl, libc, perl)
- **Medium: 79** (starlette, fastapi, libc, perl, gnutls, gssapi)
- **Low: 7**
- **Negligible: 77**

**Key insight:** The majority of vulns come from the Debian base image (libc, perl, gnutls, gssapi, krb5, curl, bash). Switching to Alpine (musl-based, ~5MB Python image) eliminates ~80% of these at the source. The remaining Python-level vulns require dependency updates.

---

## Current State

### Docker Base Images
| Service | Current Base | Alpine? |
|---------|-------------|---------|
| Backend (API) | `python:3.12-slim` (Debian) | No |
| Frontend (Web) | `node:20-alpine` + `nginx:alpine` | Yes |
| Reverse Proxy | `caddy:2-alpine` | Yes |

### Python Dependencies (from `requirements.txt`)
```
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy[asyncio]==2.0.36
aiosqlite==0.20.0
alembic==1.14.0
pydantic==2.10.4
pydantic-settings==2.7.1
python-jose[cryptography]==3.3.0        ← CRITICAL vuln
passlib[bcrypt]==1.7.4
bcrypt<5.0
python-multipart==0.0.18                ← HIGH vulns (2)
apscheduler==3.10.4
httpx==0.28.1
pytest==8.3.4
pytest-asyncio==0.24.0
python-dateutil==2.9.0.post0
icalendar==5.0.11
```

---

## Vulnerability Breakdown

### Tier 1 — Python Packages (Directly Fixable)

| Package | Current → Target | Severity | CVEs | Action |
|---------|-----------------|----------|------|--------|
| **python-jose** | 3.3.0 → **3.4.0+** | CRITICAL | GHSA-6c5p-j8vq-pqhj, CVE-2024-33663 | Algorithm confusion with OpenSSH ECDSA keys |
| **python-multipart** | 0.0.18 → **0.0.27** | HIGH | GHSA-wp53-j4wj-2cfg, GHSA-pp6c-gr5w-3c5g | Arbitrary file write + DoS via unbounded headers |
| **ecdsa** | 0.19.2 → **latest** | HIGH | GHSA-wj6h-64fc-37mp | Minerva timing attack — no fixed version yet, mitigate with constant-time usage |
| **starlette** | 0.41.3 → **0.49.1+** | HIGH | GHSA-7f5h-v6xp-fcq8 | O(n²) DoS via Range header in FileResponse |
| **fastapi** | 0.115.6 → **0.115.13+** | MEDIUM | GHSA-7f5h-v6xp-fcq8 (transitive) | Same Range header issue as starlette |

### Tier 2 — System Packages (Solved by Alpine Migration)

These are all Debian base image vulns that disappear with Alpine:

| Package Group | Vuln Count | Severity | Examples |
|--------------|-----------|----------|----------|
| **libc6 / libc-bin** | 22 | 2 critical, 2 high, 6 medium | CVE-2026-5450, CVE-2026-5928, CVE-2019-1010024 (glibc masf) |
| **perl-base** | 14 | 2 critical, 4 high, 1 medium | CVE-2026-8376 (heap overflow), CVE-2026-42496 (symlink) |
| **libcurl / curl** | 17 | 1 high, 8 medium | CVE-2026-3805, CVE-2026-5545, CVE-2026-6429 |
| **libgnutls30** | 1 | negligible | CVE-2011-3389 |
| **libgssapi / krb5** | 12 | medium | CVE-2024-26458, CVE-2024-26461 |
| **libbz2** | 1 | medium | CVE-2026-42250 |
| **bsdutils / libblkid** | 8 | medium | CVE-2022-0563 (openwall) |
| **bash** | 1 | negligible | CVE-2019-18276 |
| **login.defs / passwd** | 2 | low | CVE-2024-56433 |
| **libldap2** | 1 | negligible | CVE-2017-17740 |

**Total system vulns eliminated by Alpine: ~79 packages**

### Tier 3 — Negligible / Informational

These are low-impact or architectural:
- `apt`, `libapt-pkg7.0` — negligible, package manager internals
- `coreutils` — negligible
- Various `libstdc++`, `zlib`, `openssl` — negligible or no fix available

---

## Plan: Alpine Migration

### Why Alpine?

| Metric | `python:3.12-slim` (Debian) | `python:3.12-alpine` |
|--------|-----------|---------|
| Image size | ~200MB | ~150MB |
| Base OS | Debian (glibc) | Alpine Linux (musl) |
| CVE surface | ~80 packages with vulns | ~10-15 packages max |
| Attack surface | Larger (bash, perl, glibc) | Smaller (busybox, musl) |
| Python compatibility | Native | Needs musl-compatible wheels |

### Migration Strategy

#### Option A: Direct to `python:3.12-alpine` (Recommended)

```dockerfile
FROM python:3.12-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/db /data/photos /data/backups

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**Pros:** Smallest image, minimal CVE surface, simplest Dockerfile (remove apt-get block)
**Cons:** musl libc instead of glibc — need to verify all dependencies compile/work:
- `aiosqlite` — pure Python, fine
- `sqlalchemy` — pure Python, fine
- `cryptography` (via python-jose) — has musl wheels on PyPI, fine
- `bcrypt` — has musl wheels on PyPI, fine
- `apscheduler` — pure Python, fine
- `icalendar` — pure Python, fine
- `pydantic` — has musl wheels, fine

**Risk:** LOW. All dependencies are either pure Python or have musl wheels on PyPI. The `python:alpine` images have had first-class cryptography support for years.

#### Option B: `python:3.12-slim-bookworm` (upgrade Debian)

Stay on Debian but use latest bookworm with all security patches.

**Pros:** glibc compatibility guaranteed
**Cons:** Still ~200MB image, still has perl/bash/glibc CVE surface, incremental fixes only

#### Option C: Multi-stage with custom Alpine (minimal)

```dockerfile
FROM python:3.12-alpine AS base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN addgroup -S app && adduser -S app -G app && chown -R app:app /app
USER app
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
```

**Pros:** Non-root user, smallest image
**Cons:** Slightly more complex

**Recommendation: Option A with non-root user (Option C refinements)**

---

## Implementation Steps

### Sprint: Vuln Remediation + Alpine Migration

#### Task 1: Update Python dependencies to latest compatible versions
- Update `requirements.txt`:
  - `python-jose[cryptography]==3.3.0` → `python-jose[cryptography]>=3.4.0`
  - `python-multipart==0.0.18` → `python-multipart>=0.0.27`
  - `ecdsa==0.19.2` → `ecdsa>=0.19.4` (pin to latest stable)
  - `fastapi==0.115.6` → `fastapi>=0.115.13` (picks up fixed starlette)
  - `starlette` — no direct pin, fastapi will pull fixed version
- Verify all tests pass: `pytest`
- Verify API health + login flow works

#### Task 2: Migrate backend Dockerfile to Alpine
- Replace `FROM python:3.12-slim` with `FROM python:3.12-alpine`
- Remove `apt-get` block (curl can be installed via `apk add --no-cache curl` if needed)
- Add non-root user for defense in depth
- Update `LABEL version` in Dockerfile
- Test: `docker build -t openfamhub-api:test-alpine ./backend`
- Verify: `docker run --rm openfamhub-api:test-alpine uvicorn app.main:app --help`

#### Task 3: Re-scan and verify
- Run Grype: `grype vnmyers13/openfamhub-api:0.26 --scope all-layers`
- Run Trivy: `trivy image vnmyers13/openfamhub-api:0.26`
- Compare: critical/high should drop from 43 → 0-2 (only ecdsa timing attack may remain)
- Document results in `docs/releases/v0.27.md`

#### Task 4: Update CI pipeline
- Ensure `.github/workflows/build.yml` builds and tests Alpine image
- Add vulnerability scan step to CI (post-build)
- Verify Docker Compose works with Alpine image locally

#### Task 5: Deploy to staging, then production
- Deploy to staging host (192.168.10.13 or staging equivalent)
- Smoke test: health check, login, calendar CRUD, ICS sync
- Deploy to production
- Post-release: update `APP_VERSION` to `0.27`

---

## Risk Assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `cryptography` wheel missing for musl | Very Low | PyPI has musl wheels for cryptography >= 42.0.0 |
| `bcrypt` compilation fails on musl | Very Low | Pre-built wheels available |
| SQLite aiosqlite issues on musl | Very Low | Pure Python, no C extension |
| uvicorn/asyncio behavior difference | Low | uvicorn supports musl, tested extensively |
| Docker Compose networking change | None | No networking changes, same port/protocol |
| Existing data (DB, photos, backups) affected | None | Data volumes unchanged |

---

## Expected Post-Remediation State

| Metric | Before | After (Expected) |
|--------|--------|-----------------|
| Critical | 8 | 0 |
| High | 35 | 0-2 (ecdsa timing) |
| Medium | 79 | ~5-10 |
| Low | 7 | ~2 |
| Negligible | 77 | ~5 |
| Total | 206 | ~20-30 |
| Image size | ~200MB | ~150MB |

---

## Notes

1. **ecdsa timing attack (GHSA-wj6h-64fc-37mp):** No fixed version exists yet. This is a theoretical timing attack on P-256. Mitigation: ensure the app doesn't use ecdsa for signature verification of untrusted input. OpenFamHub uses ECDSA only for JWT with `cryptography` backend (not the raw `ecdsa` package for verification), so risk is minimal. Consider removing `ecdsa` from requirements if it's only a transitive dep.

2. **python-jose algorithm confusion:** This is the most critical fix. The app uses `python-jose` for JWT. Upgrading to 3.4.0+ restricts allowed algorithms, preventing an attacker from swapping RS256 → HS256 with a public key.

3. **python-multipart:** Used by FastAPI for form data / file uploads. The arbitrary file write vuln could allow writing to arbitrary paths. Upgrading to 0.0.27 is essential.

4. **Why not just update Debian packages?** The Debian `python:3.12-slim` image is based on an older Debian release. Backporting all fixes would require either pinning to a newer Debian base (breaking minimalism) or maintaining a custom image. Alpine gives a cleaner attack surface.

5. **Frontend already Alpine:** The frontend Dockerfile uses `node:20-alpine` and `nginx:alpine` — no changes needed there.
