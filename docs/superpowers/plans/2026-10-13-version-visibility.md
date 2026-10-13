# Version Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the deployed OpenFamHub version/build/commit reliable and visible before and after login.

**Architecture:** Keep `/api/health` as the source of truth. Stamp both build-from-source and registry Docker builds with the resolved `0.<VERSION>` release and short git commit, and reuse one small frontend build-info helper/component on setup, login, and the authenticated sidebar.

**Tech Stack:** Bash deployment scripts, Docker Compose build args, FastAPI health endpoint, React/Vite TypeScript frontend, Node `tsx --test`, pytest.

**Spec:** Conversation request: “make deployed version/commit visible and reliable; priority 1.”

## Global Constraints

- Do not edit `VERSION` by hand; release string is `0.<n>` from the root `VERSION` file.
- `/api/health` remains the API source of truth for `version`, `build`, and `commit`.
- Build-from-source deploys must not report `latest`/`unknown` when git and `VERSION` are available.
- Setup/login users must be able to see version info before authentication.
- Existing authenticated Help & About display must continue to show the same build info.

## Review Focus

- Existing `.env` contains `OPENFAMHUB_VERSION=latest`: build-from-source deploy should still stamp the `VERSION` file release, not `latest`.
- Git metadata unavailable during build: commit should fall back cleanly to `unknown`/hidden UI, not break deployment.
- `/api/health` unavailable to frontend: setup/login/sidebar should fall back to the frontend build label.
- API reports a build different from frontend fallback: UI should prefer API `build` so the running backend is authoritative.
- Commit is empty/null/`unknown`: UI should not show a misleading short hash.

---

### Task 1: Build-from-source stamping

**Files:**
- Modify: `scripts/deploy.sh`
- Modify: `docker-compose.yml`
- Test: `scripts/tests/deploy-version-test.sh`

**Interfaces:**
- Consumes: existing `app_version()` in `scripts/deploy.sh`.
- Produces: exported `OPENFAMHUB_VERSION` and `OPENFAMHUB_COMMIT` for `docker compose up --build`; compose passes `OPENFAMHUB_COMMIT` into the API image build.

- [ ] **Step 1: Write the failing test**

Create `scripts/tests/deploy-version-test.sh` that copies the repo to a temporary git repo, writes `.env` with `OPENFAMHUB_VERSION=latest`, stubs `docker compose`, runs `scripts/deploy.sh deploy`, and asserts the captured compose environment contains `OPENFAMHUB_VERSION=0.<VERSION>` and `OPENFAMHUB_COMMIT=<short git sha>`.

- [ ] **Step 2: Run test to verify it fails**

Run: `bash scripts/tests/deploy-version-test.sh`

Expected: FAIL because deploy currently honors `.env` `OPENFAMHUB_VERSION=latest` and does not export `OPENFAMHUB_COMMIT`.

- [ ] **Step 3: Implement stamping**

In `scripts/deploy.sh`, add a `git_commit()` helper returning `git rev-parse --short HEAD` or `unknown`. In `deploy_local()`, force the local build tag to `app_version()` unless `OPENFAMHUB_VERSION` is explicitly set in the caller environment to a non-`latest` value; export `OPENFAMHUB_COMMIT="$(git_commit)"` before `docker compose up`. In `docker-compose.yml`, add `OPENFAMHUB_COMMIT: ${OPENFAMHUB_COMMIT:-unknown}` to the API build args.

- [ ] **Step 4: Run test to verify it passes**

Run: `bash scripts/tests/deploy-version-test.sh`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/deploy.sh docker-compose.yml scripts/tests/deploy-version-test.sh
git commit -m "fix: stamp source deploy builds"
```

---

### Task 2: Shared frontend build label and pre-auth display

**Files:**
- Modify: `frontend/src/lib/buildInfo.ts`
- Create: `frontend/src/components/BuildInfoBadge.tsx`
- Modify: `frontend/src/components/NavShell.tsx`
- Modify: `frontend/src/pages/Login.tsx`
- Modify: `frontend/src/pages/SetupWizard.tsx`
- Test: `frontend/scripts/tests/buildInfo.test.ts`

**Interfaces:**
- Consumes: `/api/health` response shape `{ version?: string; build?: string; commit?: string | null }`.
- Produces: `visibleCommit(commit?: string | null): string | null`, `buildLabel(...)`, and `BuildInfoBadge` showing `OpenFamHub <label>` plus short commit only when meaningful.

- [ ] **Step 1: Write failing tests**

Extend `frontend/scripts/tests/buildInfo.test.ts` with tests that `visibleCommit('abcdef123') === 'abcdef1'`, `visibleCommit('unknown') === null`, `visibleCommit(null) === null`, and `buildLabel({ apiBuild: 'latest', apiVersion: '0.52', fallbackBuild: 'dev' }) === '0.52'`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npm run test:build-info`

Expected: FAIL because `visibleCommit` is missing and `buildLabel` currently accepts `latest`.

- [ ] **Step 3: Implement helper and component**

Update `buildInfo.ts` so `buildLabel` ignores empty strings, `dev`, `latest`, and `unknown` before falling through. Add `visibleCommit(commit?: string | null): string | null`. Create `BuildInfoBadge.tsx` that fetches `/api/health` with `apiClient`, uses fallback `VITE_APP_BUILD || 'dev'`, and renders the Help & About block in compact form.

- [ ] **Step 4: Wire UI**

Use `BuildInfoBadge` in `NavShell.tsx` to replace the local health/build rendering. Add the same component below the forms in `Login.tsx` and `SetupWizard.tsx` so version info is visible before authentication and setup.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd frontend && npm run test:build-info`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/buildInfo.ts frontend/src/components/BuildInfoBadge.tsx frontend/src/components/NavShell.tsx frontend/src/pages/Login.tsx frontend/src/pages/SetupWizard.tsx frontend/scripts/tests/buildInfo.test.ts
git commit -m "feat: show build info before login"
```

---

### Task 3: Verification and docs

**Files:**
- Modify: `docs/deployment.md`
- Modify if needed: `TODO.md`

**Interfaces:**
- Consumes: Task 1 deployment behavior and Task 2 UI behavior.
- Produces: documented operator check for `/api/health` and pre-auth build display.

- [ ] **Step 1: Update docs**

Document that build-from-source deploys stamp `OPENFAMHUB_VERSION` from `VERSION` and `OPENFAMHUB_COMMIT` from git, and that version info is visible on setup/login and Help & About.

- [ ] **Step 2: Run full verification**

Run:

```bash
bash scripts/tests/deploy-version-test.sh
cd backend && source .venv/bin/activate && pytest -v
cd ../frontend && npm run test:build-info && npm run lint && npm run build
```

Expected: all commands pass.

- [ ] **Step 3: Commit**

```bash
git add docs/deployment.md TODO.md
git commit -m "docs: describe build visibility checks"
```

## Self-Review

- **Spec coverage:** Reliable build/commit stamping is Task 1; pre-auth and post-auth visibility are Task 2; operator documentation is Task 3.
- **Step scan:** Each task has one failing test step, one implementation step, one passing verification step, and a commit step.
- **Type consistency:** `BuildInfoBadge`, `buildLabel`, and `visibleCommit` are named once and reused consistently.
- **Review Focus:** All five listed failure modes are covered by Task 1 or Task 2 tests.
- **Proportion:** Plan is limited to decisions and exact tests; implementation bodies are left to the executor.
