# Wall Routine Step Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a paired wall display check off today's routine steps without requiring a signed-in family-member session.

**Architecture:** Add one paired-display write endpoint under `/api/wall` that completes a routine step instance only when it belongs to today's routine for the paired display's family and is assigned to a family member. Reuse the chores completion transaction rules so points, badges, live updates and idempotency stay consistent, then add a wall UI button that calls the new endpoint and invalidates wall routine/progress data.

**Tech Stack:** FastAPI + SQLAlchemy async backend, existing chore/routine models, React + TanStack Query frontend, Vitest/Testing Library and pytest.

**Spec:** `TODO.md` line for Phase 5 follow-up: “Check off routine steps from the wall… allow it only for routine steps assigned to a child.” This plan makes the conservative call that wall completion is allowed only for assigned routine steps, and credits/completes as the assigned member.

## Global Constraints

- Paired wall displays authenticate only through the `wall_token` cookie and must not gain general chore/user write access.
- Wall completion must be limited to routine step instances, not standalone chores.
- Wall completion must be limited to the paired device's family and the family-local current date.
- Completing from the wall credits the assigned routine member and records `completed_by` as that same assigned member.
- Use `queue_event(db, ...)` for live updates; do not emit directly.
- Keep routine step completion idempotent for already completed steps: return the current completed step instead of double-crediting.

## Review Focus

- A wall token from one family must not complete another family's routine step: backend 404 test in Task 1.
- A paired wall must not complete a standalone chore instance: backend 404 test in Task 1.
- A paired wall must not complete an unassigned/claimable routine step: backend 403 test in Task 1.
- A repeated tap on an already completed step must not add duplicate points: backend idempotency test in Task 1.
- The wall UI must refresh routines/progress after completion and show failures without leaving the button stuck: frontend mutation test in Task 2.

---

### Task 1: Backend wall routine-step completion endpoint

**Files:**
- Modify: `backend/app/routers/chores.py`
- Modify: `backend/app/routers/wall.py`
- Test: `backend/tests/test_todos_routines.py`

**Interfaces:**
- Consumes: existing `get_wall_device(db, wall_token)` dependency, `todays_runs(db, family_id)`, chore models, `queue_event`, and reward badge awarding.
- Produces: `POST /api/wall/routines/steps/{instance_id}/complete -> ChoreInstanceResponse`.
- Produces helper: `complete_instance_for_user(db: AsyncSession, actor: User, instance_id: str) -> ChoreInstanceResponse` in `backend/app/routers/chores.py`, preserving current `/api/chores/instances/{id}/complete` behavior.
- Produces helper: `complete_routine_step_from_wall(db: AsyncSession, family_id: str, instance_id: str) -> ChoreInstanceResponse` in `backend/app/routers/wall.py`; it loads the routine step, validates family/today/routine/assigned constraints, and completes as the assigned user.

- [ ] **Step 1: Write the failing backend tests**

Add tests to `TestRoutines` in `backend/tests/test_todos_routines.py`:

```python
async def test_the_wall_completes_an_assigned_routine_step_and_credits_the_child(self, client, admin, kid):
    await make_routine(client, admin, kid)
    device = (await client.post('/api/wall/devices', json={'name': 'Kitchen'}, headers=_h(admin))).json()
    pair = await client.post('/api/wall/pair', json={'token': device['token']})
    wall = {'Cookie': _cookie(pair, 'wall_token')}
    [routine] = (await client.get('/api/wall/routines', headers=wall)).json()

    res = await client.post(f"/api/wall/routines/steps/{routine['steps'][0]['instance_id']}/complete", headers=wall)

    assert res.status_code == 200, res.text
    assert res.json()['status'] == 'completed'
    stats = (await client.get('/api/chores/stats', headers=_h(kid))).json()
    assert stats['points_balance'] == 1
    [routine] = (await client.get('/api/wall/routines', headers=wall)).json()
    assert routine['steps'][0]['status'] == 'completed'
```

Also add tests named:
- `test_wall_routine_completion_is_idempotent`
- `test_wall_cannot_complete_plain_chores_or_foreign_steps`
- `test_wall_refuses_unassigned_routine_steps`

Each test should use existing fixtures/helpers and assert HTTP status plus observable point balance or unchanged state.

- [ ] **Step 2: Run backend routine tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_todos_routines.py::TestRoutines -q`

Expected: FAIL with `404 Not Found` for the new wall endpoint.

- [ ] **Step 3: Extract chore completion helper**

In `backend/app/routers/chores.py`, move the body of `complete()` into:

```python
async def complete_instance_for_user(db: AsyncSession, user: User, instance_id: str) -> ChoreInstanceResponse:
```

Keep the existing route as a thin wrapper that calls this helper after `deny_viewers(user)`. Do not change current family/user permission behavior.

- [ ] **Step 4: Implement `POST /api/wall/routines/steps/{instance_id}/complete`**

In `backend/app/routers/wall.py`, add:

```python
@router.post('/routines/steps/{instance_id}/complete', response_model=ChoreInstanceResponse)
async def complete_wall_routine_step(instance_id: str, db: AsyncSession = Depends(get_db), device: WallDevice = Depends(get_wall_device)):
```

Validation requirements:
- Load `ChoreInstance`, joined to `ChoreTemplate`.
- Return 404 if the instance or template is missing, belongs to another family, has no `routine_id`, or is not due on `family_today(family.timezone)`.
- Return 403 if `inst.assigned_to` is missing.
- If `inst.status == 'completed'`, return `to_instance(inst, template)` without creating another completion/ledger entry.
- Load `User` by `inst.assigned_to`; return 404 if missing/deleted or outside the family.
- Call `complete_instance_for_user(db, assigned_user, instance_id)`.

- [ ] **Step 5: Run backend routine tests to verify they pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_todos_routines.py::TestRoutines -q`

Expected: all `TestRoutines` tests pass.

---

### Task 2: Frontend wall routine step button

**Files:**
- Modify: `frontend/src/api/wall.ts`
- Modify: `frontend/src/wall/WallRoutines.tsx`
- Test: `frontend/src/wall/WallRoutines.test.tsx`

**Interfaces:**
- Consumes: `POST /api/wall/routines/steps/{instance_id}/complete` from Task 1.
- Produces: `completeWallRoutineStep(instanceId: string): Promise<void>` in `frontend/src/api/wall.ts`.
- Produces: a visible “Done” button for the current pending routine step on the wall.

- [ ] **Step 1: Write the failing frontend tests**

In `frontend/src/wall/WallRoutines.test.tsx`, add a test named `checks off the current step from the wall`:

```tsx
const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime })
const calls = renderAt('2026-10-20T11:06:30Z', [{ ...MORNING, steps: [step(1, 'Get dressed', 5, 'completed'), MORNING.steps[1], MORNING.steps[2]] }])
await user.click(await screen.findByRole('button', { name: 'Done with Breakfast' }))
expect(calls.some((c) => c.method === 'POST' && c.url === '/wall/routines/steps/i2/complete')).toBe(true)
```

Also add a failure-state test named `shows an error when the wall cannot complete a step` asserting that a 403 response displays its detail and the button becomes usable again.

- [ ] **Step 2: Run the frontend routine tests to verify they fail**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/WallRoutines.test.tsx`

Expected: FAIL because there is no button/API helper.

- [ ] **Step 3: Add the wall API helper**

In `frontend/src/api/wall.ts`, add:

```ts
export async function completeWallRoutineStep(instanceId: string): Promise<void> {
  await apiClient.post(`/wall/routines/steps/${instanceId}/complete`)
}
```

- [ ] **Step 4: Add the mutation and button**

In `frontend/src/wall/WallRoutines.tsx`:
- Import `useMutation` and `useQueryClient`.
- Use a mutation that calls `completeWallRoutineStep(step.instance_id)`.
- On success, invalidate `['wall-routines']` and `['wall-progress']`.
- Render a button labeled `Done with ${step.title}` only for the current pending step during the active phase.
- While pending, disable the button and show “Saving…”.
- On error, show the API detail if available, otherwise “Could not complete this step.”

- [ ] **Step 5: Run the frontend routine tests to verify they pass**

Run: `cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/WallRoutines.test.tsx`

Expected: all `WallRoutines` tests pass.

---

### Task 3: Verification, TODO, and issue sync

**Files:**
- Modify: `TODO.md`

**Interfaces:**
- Consumes: Task 1 and Task 2 passing checks.
- Produces: TODO line marked complete and issue triage agreement.

- [ ] **Step 1: Run focused backend and frontend checks**

Run:

```bash
cd backend && source .venv/bin/activate && pytest tests/test_todos_routines.py tests/test_chores_api.py -q
cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run src/wall/WallRoutines.test.tsx src/api/wall.test.ts
```

Expected: all selected tests pass.

- [ ] **Step 2: Run full verification commands**

Run:

```bash
cd backend && source .venv/bin/activate && pytest -v --cov
cd frontend && npx -y -p node@24 node node_modules/vitest/vitest.mjs run --coverage
cd frontend && npx -y -p node@24 node node_modules/eslint/bin/eslint.js .
cd frontend && npx -y -p node@24 node node_modules/typescript/bin/tsc -b
cd frontend && npx -y -p node@24 node node_modules/vite/bin/vite.js build
python3 scripts/issues.py triage
```

Expected: backend/frontend tests, lint, typecheck, build pass; issue triage has no missing issues.

- [ ] **Step 3: Tick the TODO item**

Update `TODO.md` Phase 5 follow-up line to checked with a short “Done” note naming the wall endpoint and tests.

- [ ] **Step 4: Commit and push**

Commit message:

```bash
git add backend/app/routers/chores.py backend/app/routers/wall.py backend/tests/test_todos_routines.py frontend/src/api/wall.ts frontend/src/wall/WallRoutines.tsx frontend/src/wall/WallRoutines.test.tsx TODO.md
git commit -m "feat(wall): complete routine steps from paired displays"
git push forgejo master
for r in forgejo-mirror1 forgejo-mirror2 origin; do git push $r master; done
```

Expected: push succeeds to all remotes.

## Self-Review Notes

- Spec coverage: Covers paired-display completion, assigned-child safety, points credit, current-day scoping, UI action, TODO/issue sync.
- Step scan: Steps specify exact files, endpoint, helper names, commands, and observable checks.
- Type consistency: Backend helper returns `ChoreInstanceResponse`; frontend helper returns `Promise<void>` and route path matches backend.
- Review focus: All five listed failure modes are assigned to Task 1 or Task 2 tests.
- Proportion: The plan records decisions and test shapes without writing production bodies beyond signatures and validation bullets.
