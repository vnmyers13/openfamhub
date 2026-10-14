# Wall Dashboard Configuration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a family-wide, user-editable wall dashboard configuration and make paired wall displays render configurable dashboard-style pages with read-only wall data.

**Architecture:** Store `wall_dashboard` in `families.settings_json` and expose it through authenticated family routes for editing plus `/api/wall/session` for paired displays. Add paired-device read-only endpoints for wall cards, then replace the fixed wall cycle with a dashboard-page renderer that cycles configured pages and keeps the live countdown.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, React, TypeScript, TanStack Query, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-wall-dashboard-config.md`

## Global Constraints

- Any signed-in family user may read and save the shared wall dashboard configuration.
- The paired wall remains read-only and uses only the `wall_token` cookie for wall data.
- Wall card keys are exactly `events`, `chores`, `routines`, `meals`, `weather`, `announcements`, `progress`, `birthdays`.
- Invalid saved JSON must not crash family settings or wall session reads; fall back to defaults.
- Saving wall configuration queues `settings_updated` so paired walls refetch their session.
- Sleep schedule and idle slideshow still take precedence over wall dashboard rendering.
- Do not add a database migration; `families.settings_json` already holds family settings.

## Review Focus

- Bad/old `settings_json["wall_dashboard"]` data: `wall_dashboard()` in Task 1 falls back to defaults and tests corrupted keys/sizes.
- Viewer/member edit permission: Task 1 tests a non-admin signed-in user can save config while an anonymous request cannot.
- Paired wall scoping: Task 2 tests every new `/api/wall/*` endpoint requires a valid wall cookie and returns only the paired family’s data.
- Empty dashboard pages/widgets: Task 3 tests the wall renders a friendly empty page instead of crashing.
- Sleep/idle precedence: Task 4 extends `WallLayout.test.tsx` so asleep/idle screens hide the configured dashboard.

---

### Task 1: Family wall dashboard settings API

**Files:**
- Modify: `backend/app/schemas/family.py`
- Modify: `backend/app/routers/family.py`
- Test: `backend/tests/test_family_settings.py`

**Interfaces:**
- Produces: `WallDashboardWidget`, `WallDashboardPage`, `WallDashboardConfig`, `wall_dashboard(family: Family) -> WallDashboardConfig`.
- Produces: `GET /api/family/wall-dashboard` and `PUT /api/family/wall-dashboard`, both requiring `get_current_user` only.
- Later tasks consume `wall_dashboard()` and the JSON shape `{ pages: [{ name, duration_seconds, widgets: [{ key, size }] }] }`.

- [ ] **Step 1: Write backend settings tests**

Add tests to `backend/tests/test_family_settings.py`:
- `test_any_signed_in_user_can_save_wall_dashboard`: a member `PUT /api/family/wall-dashboard` with one page containing `events` and `weather`, receives the saved JSON, then admin `GET` sees the same config.
- `test_wall_dashboard_rejects_bad_values`: invalid key, invalid size, blank page name, and `duration_seconds < 5` return 422.
- `test_wall_dashboard_falls_back_when_stored_json_is_invalid`: write bad `settings_json["wall_dashboard"]` directly in the fixture session, then `GET` returns defaults.
- `test_changing_wall_dashboard_notifies_walls`: saving queues `("settings_updated", {})`.
- `test_anonymous_cannot_read_or_save_wall_dashboard`: unauthenticated GET/PUT return 401 or 403.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_family_settings.py -q`
Expected: FAIL because routes/schemas do not exist.

- [ ] **Step 3: Implement family wall dashboard schemas**

In `backend/app/schemas/family.py`, add:
- `WallDashboardWidget` with `key: Literal["events", "chores", "routines", "meals", "weather", "announcements", "progress", "birthdays"]` and `size: Literal["normal", "wide"] = "normal"`.
- `WallDashboardPage` with `name: str`, `duration_seconds: int = 30`, `widgets: list[WallDashboardWidget]`; validate trimmed non-empty name length 1–40, duration 5–300, and at most 8 widgets.
- `WallDashboardConfig` with `pages: list[WallDashboardPage]`; validate at most 6 pages.
- `DEFAULT_WALL_DASHBOARD` with pages: `Today` (`events` wide, `weather`, `meals`), `Family` (`routines` wide, `progress` wide), and `Notes` (`announcements` wide, `birthdays`).

- [ ] **Step 4: Implement family routes**

In `backend/app/routers/family.py`, add:
- `wall_dashboard(family: Family) -> WallDashboardConfig` that reads `settings_json["wall_dashboard"]`, returns `DEFAULT_WALL_DASHBOARD` on missing/invalid values.
- `GET /wall-dashboard` returning `wall_dashboard(await _family(...))` with `get_current_user`.
- `PUT /wall-dashboard` storing `data.model_dump()` under `settings_json["wall_dashboard"]`, flushing/refreshing, queuing `settings_updated`, and returning the normalized config. Use `get_current_user`, not `require_role("admin")`.

- [ ] **Step 5: Run backend settings tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_family_settings.py -q`
Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add backend/app/schemas/family.py backend/app/routers/family.py backend/tests/test_family_settings.py docs/superpowers/specs/2026-10-14-wall-dashboard-config.md docs/superpowers/plans/2026-10-14-wall-dashboard-config.md
git commit -m "feat(wall): add family wall dashboard settings"
```

### Task 2: Read-only paired wall data endpoints

**Files:**
- Modify: `backend/app/routers/wall.py`
- Test: `backend/tests/test_wall_api.py`

**Interfaces:**
- Consumes: existing `get_wall_device()` dependency and family-scoped services.
- Produces: `GET /api/wall/chores`, `/api/wall/meals`, `/api/wall/announcements`, `/api/wall/weather`.
- Produces: `/api/wall/session` includes `dashboard: WallDashboardConfig`.

- [ ] **Step 1: Write wall endpoint tests**

Add tests to `backend/tests/test_wall_api.py`:
- `test_wall_session_includes_dashboard_config`: member saves a config, paired wall session returns it.
- `test_wall_read_only_endpoints_require_pairing`: unauthenticated calls to `/api/wall/chores`, `/meals`, `/announcements`, `/weather` return 401.
- `test_wall_meals_and_announcements_are_family_scoped`: with setup data, paired wall receives today’s meals and recent announcements.
- `test_wall_chores_returns_todays_non_routine_chores`: create due-today chore instances and verify titles/status/assignee fields.
- `test_wall_weather_uses_family_weather_settings`: configured weather endpoint returns the same shape as `/api/weather` without a user session; mock network/cache as existing weather tests do.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_wall_api.py -q`
Expected: FAIL because endpoints/session field do not exist.

- [ ] **Step 3: Add session dashboard config**

In `backend/app/routers/wall.py`, import `wall_dashboard` and include `"dashboard": wall_dashboard(family).model_dump()` in `/session`.

- [ ] **Step 4: Implement read-only endpoints**

In `backend/app/routers/wall.py`, add:
- `/chores`: non-routine chores due today in family timezone, family-scoped by device, ordered consistently.
- `/meals`: today’s meal plan slots plus the current week if useful to existing schemas; use `SLOTS` order.
- `/announcements`: recent/pinned announcements using `recent()` / `to_announcement()`.
- `/weather`: call the same service used by `backend/app/routers/weather.py` for the paired device’s family.

- [ ] **Step 5: Run wall API tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_wall_api.py tests/test_family_settings.py -q`
Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
git add backend/app/routers/wall.py backend/tests/test_wall_api.py
git commit -m "feat(wall): add read-only dashboard endpoints"
```

### Task 3: Shared wall dashboard config editor for signed-in users

**Files:**
- Modify: `frontend/src/api/wall.ts`
- Create: `frontend/src/pages/dashboard/WallDashboardEditor.tsx`
- Modify: `frontend/src/pages/Dashboard.tsx`
- Test: `frontend/src/pages/dashboard/WallDashboardEditor.test.tsx`
- Test: `frontend/src/pages/Dashboard.test.tsx`

**Interfaces:**
- Consumes: Task 1 `GET/PUT /api/family/wall-dashboard` JSON shape.
- Produces: `WallDashboardConfig`, `WallDashboardPage`, `WallDashboardWidget`, `useFamilyWallDashboardConfig()`, `useSaveFamilyWallDashboardConfig()` in `frontend/src/api/wall.ts`.
- Produces: `WallDashboardEditor` props `{ config, current, onSelect, onChange, saving }`.

- [ ] **Step 1: Write editor tests**

Create `WallDashboardEditor.test.tsx` covering:
- It renders saved family wall pages and cards.
- Any role-visible editor can add a wall card, reorder cards, toggle wide/normal, remove a card, add/delete pages, and reset to defaults.
- It calls `PUT /family/wall-dashboard` with the full updated config.
- It prevents adding duplicate cards to the same page.

- [ ] **Step 2: Write Dashboard integration test**

In `Dashboard.test.tsx`, add a test that opens Customize and sees a “Family wall dashboard” editor for a non-admin/member user.

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/pages/dashboard/WallDashboardEditor.test.tsx src/pages/Dashboard.test.tsx`
Expected: FAIL because editor/API hooks do not exist.

- [ ] **Step 4: Implement frontend API hooks**

In `frontend/src/api/wall.ts`, add wall dashboard types, `DEFAULT_WALL_DASHBOARD`, `WALL_DASHBOARD_WIDGETS`, `wallDashboardWidgetLabel()`, `useFamilyWallDashboardConfig()`, and `useSaveFamilyWallDashboardConfig()`.

- [ ] **Step 5: Implement `WallDashboardEditor`**

Create `frontend/src/pages/dashboard/WallDashboardEditor.tsx`. Reuse the interaction model from `CustomizeDashboard.tsx`, but restrict card keys to the wall list and save `duration_seconds` per page.

- [ ] **Step 6: Integrate editor in Dashboard customization**

In `frontend/src/pages/Dashboard.tsx`, when `customizing` is true, render the existing personal dashboard editor and the new `WallDashboardEditor` below it with a heading explaining this is shared by the family wall. Fetch/save via the new hooks. It is visible to any signed-in user.

- [ ] **Step 7: Run frontend editor tests**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/pages/dashboard/WallDashboardEditor.test.tsx src/pages/Dashboard.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add frontend/src/api/wall.ts frontend/src/pages/dashboard/WallDashboardEditor.tsx frontend/src/pages/dashboard/WallDashboardEditor.test.tsx frontend/src/pages/Dashboard.tsx frontend/src/pages/Dashboard.test.tsx
git commit -m "feat(wall): let users configure the family wall dashboard"
```

### Task 4: Configurable dashboard-style wall renderer

**Files:**
- Modify: `frontend/src/wall/wallCycle.ts`
- Modify: `frontend/src/wall/WallCycle.tsx`
- Create: `frontend/src/wall/WallDashboard.tsx`
- Modify: `frontend/src/wall/WallLayout.tsx`
- Test: `frontend/src/wall/wallCycle.test.ts`
- Test: `frontend/src/wall/WallCycle.test.tsx`
- Test: `frontend/src/wall/WallLayout.test.tsx`

**Interfaces:**
- Consumes: Task 3 `WallDashboardConfig` / page/widget types and Task 2 wall endpoint hooks.
- Produces: `WallCycle` props `{ startedAt: number; timeZone: string; dashboard: WallDashboardConfig }`.
- Produces: `WallDashboardPageView({ page, timeZone })` that renders card grid for configured widgets.

- [ ] **Step 1: Write wall renderer tests**

Update/add tests:
- `wallCycle.test.ts`: cycles based on configured page `duration_seconds` and handles empty page list.
- `WallCycle.test.tsx`: renders page names, dashboard cards, and “Next in …” countdown from supplied config.
- `WallCycle.test.tsx`: empty pages render “No wall dashboard pages configured.”
- `WallLayout.test.tsx`: paired board passes the session dashboard into `WallCycle`; sleep and idle states hide the configured dashboard.

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/wallCycle.test.ts src/wall/WallCycle.test.tsx src/wall/WallLayout.test.tsx`
Expected: FAIL because `WallCycle` still uses fixed panels.

- [ ] **Step 3: Update cycle helper**

In `frontend/src/wall/wallCycle.ts`, keep `cycleState()` but remove hard-coded `WALL_CYCLE_PANELS`; callers pass pages mapped to `{ id, label, durationSeconds }`.

- [ ] **Step 4: Implement wall dashboard cards**

Create `frontend/src/wall/WallDashboard.tsx` with wall-card components:
- `events`: `useWallEvents()` for today using `timeZone` and `lib/dates.ts` helpers.
- `chores`: `useWallChores()`.
- `routines`: existing `WallRoutines`.
- `meals`: `useWallMeals()`.
- `weather`: `useWallWeather()`.
- `announcements`: `useWallAnnouncements()`.
- `progress`: existing `WallProgress` plus `WallBirthdays`.
- `birthdays`: existing `WallBirthdays`.

- [ ] **Step 5: Update `WallCycle`**

In `frontend/src/wall/WallCycle.tsx`, accept `dashboard`, map pages to cycle panels by index/name/duration, render `WallDashboardPageView`, and show the page name plus countdown.

- [ ] **Step 6: Update `WallLayout`**

Pass `session.dashboard` into `WallCycle`; clear `wall-chores`, `wall-meals`, `wall-announcements`, and `wall-weather` query caches on wall unauthorized.

- [ ] **Step 7: Run wall frontend tests**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/wallCycle.test.ts src/wall/WallCycle.test.tsx src/wall/WallLayout.test.tsx`
Expected: PASS.

- [ ] **Step 8: Commit Task 4**

```bash
git add frontend/src/wall/wallCycle.ts frontend/src/wall/WallCycle.tsx frontend/src/wall/WallDashboard.tsx frontend/src/wall/wallCycle.test.ts frontend/src/wall/WallCycle.test.tsx frontend/src/wall/WallLayout.tsx frontend/src/wall/WallLayout.test.tsx frontend/src/api/wall.ts
git commit -m "feat(wall): render configurable dashboard pages"
```

### Task 5: Documentation, TODO, and branch verification

**Files:**
- Modify: `TODO.md`
- Modify: `docs/architecture.md`

**Interfaces:**
- Consumes: all previous tasks.
- Produces: verified branch ready for review/merge.

- [ ] **Step 1: Update TODO and architecture docs**

Mark TODO Phase 10 read-only wall endpoints complete with a note that they support the configurable family wall dashboard. Add an architecture note that wall dashboard config is family-wide, member-editable, and displayed read-only by paired wall devices.

- [ ] **Step 2: Run focused verification**

Run:
```bash
cd backend && source .venv/bin/activate && pytest tests/test_family_settings.py tests/test_wall_api.py -q
cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/pages/dashboard/WallDashboardEditor.test.tsx src/pages/Dashboard.test.tsx src/wall/wallCycle.test.ts src/wall/WallCycle.test.tsx src/wall/WallLayout.test.tsx
```
Expected: PASS.

- [ ] **Step 3: Run full verification**

Run:
```bash
cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run
cd frontend && npx -y -p node@24 node node_modules/eslint/bin/eslint.js .
cd frontend && npx -y -p node@24 node node_modules/typescript/bin/tsc -b
cd frontend && npx -y -p node@24 node scripts/ocr-assets.mjs && npx -y -p node@24 node node_modules/vite/bin/vite.js build
cd backend && source .venv/bin/activate && pytest -v --cov
```
Expected: PASS.

- [ ] **Step 4: Commit Task 5**

```bash
git add TODO.md docs/architecture.md
git commit -m "docs(wall): document configurable wall dashboard"
```

- [ ] **Step 5: Request final code review**

Use the requesting-code-review skill for the full branch diff.

## Self-Review

- Spec coverage: the plan covers shared family config, any-user editing, paired read-only display, wall endpoints, configurable pages/cards, defaults, and wall sleep/idle precedence.
- Step scan: each task has a failing-test step, implementation steps with exact files/interfaces, verification, and commit.
- Type consistency: backend `WallDashboardConfig.pages[].duration_seconds` maps to frontend `duration_seconds` and `cycleState(...durationSeconds)` through an explicit conversion in Task 4.
- Review Focus: the five highest-risk implied behaviors are listed and pinned to tests in Tasks 1–4.
- Proportion: plan is longer than the spec because it spans backend API, frontend editor, wall renderer, and verification; code bodies are intentionally omitted.
