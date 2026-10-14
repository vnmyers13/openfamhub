# Wall Cycling Panel Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paired wall display mode that cycles between wall panels and shows a live countdown to the next panel.

**Architecture:** Keep wall panel cycling entirely on the frontend, using existing paired-display data hooks and current wall layout. Add a small pure cycling helper for deterministic timing, then have `WallLayout` choose between the current calendar board and the new focused panel display on an interval.

**Tech Stack:** React, TanStack Query, Vitest/Testing Library, existing FastAPI wall endpoints and wall data hooks.

**Spec:** `TODO.md` Phase 10 line: “Wall cycling panel mode with a live countdown.”

## Global Constraints

- Paired displays keep using the `wall_token` cookie and existing `/api/wall/*` read flow.
- Do not add backend endpoints for this task; read-only wall endpoints are the next separate TODO.
- The existing non-idle board must remain available and must not break revocation, sleep schedule, or idle slideshow behavior.
- The countdown must be live and visible on the wall while cycling.
- Tests first: add failing Vitest coverage before production code.

## Review Focus

- Timer rollover: when one panel's duration elapses, the next panel renders and the countdown resets; Task 1 tests this in `WallCycle.test.tsx`.
- No empty panel list crash: if the panel list is empty, the helper returns no active panel and a zero countdown; Task 1 tests this in `wallCycle.test.ts`.
- Sleep schedule still wins over cycling: asleep wall remains dark; Task 2 extends `WallLayout.test.tsx`.
- Idle slideshow still wins over cycling after inactivity: Task 2 extends `WallLayout.test.tsx`.
- Revoked wall cookies still clear wall state and return to pairing: existing `WallLayout.test.tsx` remains in the focused verification command.

---

### Task 1: Pure cycling state and focused panel shell

**Files:**
- Create: `frontend/src/wall/wallCycle.ts`
- Create: `frontend/src/wall/wallCycle.test.ts`
- Create: `frontend/src/wall/WallCycle.tsx`
- Create: `frontend/src/wall/WallCycle.test.tsx`

**Interfaces:**
- Produces: `export interface CyclePanel { id: string; label: string; durationSeconds: number }`
- Produces: `export interface CycleState { panel: CyclePanel | null; index: number; secondsLeft: number; elapsedInPanel: number }`
- Produces: `export function cycleState(panels: CyclePanel[], nowMs: number, startedAtMs: number): CycleState`
- Produces: `export const WALL_CYCLE_PANELS: CyclePanel[]`
- Produces: `export default function WallCycle({ startedAt, timeZone }: { startedAt: number; timeZone: string }): JSX.Element`

- [ ] **Step 1: Write the failing pure-helper tests**

Add `frontend/src/wall/wallCycle.test.ts` with tests named:

```ts
it('selects the active panel and live countdown from elapsed time', () => {
  const panels = [
    { id: 'calendar', label: 'Calendar', durationSeconds: 20 },
    { id: 'routines', label: 'Routines', durationSeconds: 10 },
  ]
  expect(cycleState(panels, 5_000, 0)).toMatchObject({ index: 0, secondsLeft: 15, elapsedInPanel: 5 })
  expect(cycleState(panels, 21_000, 0)).toMatchObject({ index: 1, secondsLeft: 9, elapsedInPanel: 1 })
  expect(cycleState(panels, 31_000, 0)).toMatchObject({ index: 0, secondsLeft: 19, elapsedInPanel: 1 })
})

it('handles an empty panel list without crashing', () => {
  expect(cycleState([], 10_000, 0)).toEqual({ panel: null, index: -1, secondsLeft: 0, elapsedInPanel: 0 })
})
```

- [ ] **Step 2: Run helper tests to verify they fail**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/wallCycle.test.ts`

Expected: FAIL because `wallCycle.ts` does not exist.

- [ ] **Step 3: Implement `cycleState` and `WALL_CYCLE_PANELS`**

In `frontend/src/wall/wallCycle.ts`, define `calendar`, `routines`, and `progress` panels with 20-second durations, and implement `cycleState` using total duration modulo arithmetic. Clamp each panel duration to at least 1 second.

- [ ] **Step 4: Run helper tests to verify they pass**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/wallCycle.test.ts`

Expected: PASS.

- [ ] **Step 5: Write the failing component tests**

Add `frontend/src/wall/WallCycle.test.tsx` that mocks `WallSevenDayStrip`, `WallRoutines`, `WallProgress`, and `WallBirthdays`, then tests:

```tsx
it('renders the active panel with a live countdown', async () => {
  vi.useFakeTimers({ toFake: ['Date', 'setInterval', 'clearInterval'] })
  vi.setSystemTime(new Date('2026-10-20T10:00:00Z'))
  render(<WallCycle startedAt={Date.now()} timeZone="America/Detroit" />)
  expect(screen.getByText('Calendar')).toBeTruthy()
  expect(screen.getByLabelText('Next wall panel').textContent).toContain('20s')
  act(() => vi.advanceTimersByTime(21_000))
  expect(screen.getByText('Routines')).toBeTruthy()
  expect(screen.getByText('routines panel')).toBeTruthy()
})
```

Also test that the progress panel renders both progress and birthdays in the same focused view.

- [ ] **Step 6: Run component tests to verify they fail**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/WallCycle.test.tsx`

Expected: FAIL because `WallCycle.tsx` does not exist or does not render the expected labels.

- [ ] **Step 7: Implement `WallCycle`**

In `frontend/src/wall/WallCycle.tsx`, use a 1-second tick, call `cycleState(WALL_CYCLE_PANELS, now.getTime(), startedAt)`, render a header with the active label and `aria-label="Next wall panel"`, and render:
- `calendar`: `WallSevenDayStrip`
- `routines`: `WallRoutines timeZone={timeZone}`
- `progress`: `WallProgress` and `WallBirthdays`

- [ ] **Step 8: Run component tests to verify they pass**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/WallCycle.test.tsx src/wall/wallCycle.test.ts`

Expected: PASS.

---

### Task 2: Integrate cycling into the paired wall board

**Files:**
- Modify: `frontend/src/wall/WallLayout.tsx`
- Modify: `frontend/src/wall/WallLayout.test.tsx`
- Modify: `TODO.md`

**Interfaces:**
- Consumes: `WallCycle({ startedAt, timeZone })` from Task 1.
- Produces: wall board renders `WallCycle` while active, without changing pairing, sleep, idle, or revocation behavior.

- [ ] **Step 1: Write the failing integration tests**

In `frontend/src/wall/WallLayout.test.tsx`, mock `./WallCycle` as a visible component and add tests named:

```tsx
it('shows cycling mode on the paired wall board', async () => {
  render(<QueryClientProvider client={new QueryClient()}><WallLayout /></QueryClientProvider>)
  expect(await screen.findByText('cycling wall panels')).toBeTruthy()
})

it('keeps the sleep screen ahead of cycling mode', async () => {
  await bootAt('2026-10-21T03:00:00Z', { enabled: true, off: '22:00', on: '06:30' }, 'America/Detroit')
  expect(await screen.findByTestId('wall-asleep')).toBeTruthy()
  expect(screen.queryByText('cycling wall panels')).toBeNull()
})

it('keeps the idle slideshow ahead of cycling mode', async () => {
  vi.mocked(getWallSessionMock()).mockResolvedValue({ ...SESSION, idle_timeout_seconds: 0.05 })
  render(<QueryClientProvider client={new QueryClient()}><WallLayout /></QueryClientProvider>)
  expect(await screen.findByText('slideshow')).toBeTruthy()
  expect(screen.queryByText('cycling wall panels')).toBeNull()
})
```

- [ ] **Step 2: Run integration tests to verify they fail**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/WallLayout.test.tsx`

Expected: FAIL because `WallLayout` does not render `WallCycle`.

- [ ] **Step 3: Render `WallCycle` from `WallLayout`**

In `WallBoard`, create `const [cycleStartedAt] = useState(() => Date.now())`. Replace the right-panel `WallSevenDayStrip` area with `<WallCycle startedAt={cycleStartedAt} timeZone={session.timezone} />`, and keep the left summary column unchanged for family clock/progress/birthdays/routines.

- [ ] **Step 4: Run integration tests to verify they pass**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/WallLayout.test.tsx src/wall/WallCycle.test.tsx src/wall/wallCycle.test.ts`

Expected: PASS.

- [ ] **Step 5: Update TODO**

Tick `TODO.md` Phase 10 “Wall cycling panel mode with a live countdown” and add a short Done note naming `WallCycle.tsx`, `wallCycle.ts`, and the tests.

- [ ] **Step 6: Run focused verification**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/WallLayout.test.tsx src/wall/WallCycle.test.tsx src/wall/wallCycle.test.ts src/wall/WallRoutines.test.tsx src/wall/WallSevenDayStrip.test.tsx`

Expected: all selected tests pass.

---

### Task 3: Branch verification

**Files:**
- No production files beyond Tasks 1-2.

**Interfaces:**
- Consumes: all tests and code from Tasks 1-2.
- Produces: verified branch state ready for review/commit.

- [ ] **Step 1: Run frontend unit suite with the repo's required Node version**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run`

Expected: PASS.

- [ ] **Step 2: Run frontend lint and build with the repo's required Node version**

Run:

```bash
cd frontend && npx -y -p node@24 node node_modules/eslint/bin/eslint.js .
cd frontend && npx -y -p node@24 node node_modules/typescript/bin/tsc -b
cd frontend && npx -y -p node@24 node node_modules/vite/bin/vite.js build
```

Expected: PASS.

- [ ] **Step 3: Run backend regression suite touched by existing branch work**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_offline.py tests/test_smart_import.py tests/test_wall_api.py -q`

Expected: PASS.

- [ ] **Step 4: Review branch diff**

Run: `git diff --stat && git status --short`

Expected: only intended Phase 10/OCR/offline/wall-cycling changes are present.

## Self-Review Notes

- Spec coverage: The plan adds a cycling wall panel mode and visible live countdown, and updates TODO when done.
- Step scan: Each task has a red/green test cycle and exact commands; implementation steps define interfaces without writing full bodies.
- Type consistency: `CyclePanel`, `CycleState`, `cycleState`, `WALL_CYCLE_PANELS`, and `WallCycle` names match across tasks.
- Review focus: Timer rollover, empty lists, sleep precedence, idle precedence, and revocation are covered.
- Proportion: The plan is longer than the TODO line because the TODO implies UI timing behavior and regression constraints, but code bodies are intentionally omitted.
