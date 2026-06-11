# Chores Quick-Add Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Quick Add" button on the ChoresPage that lets any logged-in user create a chore template with an immediately assigned instance, appearing in the assignee's todo list.

**Architecture:** Add a new backend endpoint `POST /chores/quick-add` that creates a template and one or more instances atomically. Frontend adds a modal form on ChoresPage that calls this endpoint via a new `choreAPI.quickAdd` method.

**Tech Stack:** FastAPI, SQLAlchemy 2.0 async, React 19, TanStack React Query 5, Axios

---

### Task 1: Add ChoreQuickAdd schema

**Files:**
- Modify: `backend/app/schemas/models.py`

- [ ] **Step 1: Add ChoreQuickAdd schema to models.py**

Add after the existing `ChoreUpdate` class (around line 170) in `backend/app/schemas/models.py`:

```python
class ChoreQuickAdd(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    point_value: int = Field(default=10, ge=1, le=1000)
    assigned_to_id: str
    recurrence_rule: str = "none"
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/models.py
git commit -m "feat: add ChoreQuickAdd schema"
```

---

### Task 2: Add POST /chores/quick-add backend endpoint

**Files:**
- Modify: `backend/app/routers/chores.py`
- Modify: `backend/app/models/__init__.py` (verify ChoreInstance import)

- [ ] **Step 1: Add ChoreQuickAdd import to chores.py**

In `backend/app/routers/chores.py`, update the imports at line 10-16 to include `ChoreQuickAdd`:

```python
from app.schemas.models import (
    ChoreCreate,
    ChoreUpdate,
    ChoreResponse,
    ChoreInstanceResponse,
    ChoreCompletionLogResponse,
    ChoreStatsResponse,
    ChoreQuickAdd,
)
```

- [ ] **Step 2: Add User import to chores.py**

Add `User` to the models import at line 18:

```python
from app.models import Chore, ChoreInstance, ChoreCompletionLog, User, UserStreak
```

- [ ] **Step 3: Add quick-add endpoint function**

Add this new function to `backend/app/routers/chores.py` after the `list_chore_instances` function (around line 203):

```python
@router.post("/quick-add", status_code=status.HTTP_201_CREATED)
async def quick_add_chore(
    req: ChoreQuickAdd,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Create a chore template and immediately assign instances to a user."""
    # Validate assigned_to_id exists
    result = await db.execute(select(User).where(User.id == req.assigned_to_id, User.is_active == True))
    target_user = result.scalar_one_or_none()
    if target_user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assigned user not found")

    # Create chore template
    template = Chore(
        title=req.title,
        description=req.description,
        assignment_mode="assigned",
        recurrence_rule=req.recurrence_rule,
        default_assigned_to_id=req.assigned_to_id,
        point_value=req.point_value,
        created_by_id=current_user["sub"],
    )
    db.add(template)
    await db.flush()
    await db.refresh(template)

    # Generate instances based on recurrence rule
    today = datetime.now(timezone.utc).date()
    instances = []

    if req.recurrence_rule == "none":
        # Create single instance due today
        instance = ChoreInstance(
            chore_template_id=template.id,
            assigned_to_id=req.assigned_to_id,
            due_date=today.isoformat(),
            status="pending",
        )
        db.add(instance)
        instances.append(instance)
    else:
        # Generate instances using existing logic, limit to 7 days
        all_dates = _parse_recurrence_rule(req.recurrence_rule)
        limit_date = today + timedelta(days=7)
        for date_str in all_dates:
            d = datetime.fromisoformat(date_str).date()
            if d <= limit_date:
                instance = ChoreInstance(
                    chore_template_id=template.id,
                    assigned_to_id=req.assigned_to_id,
                    due_date=date_str,
                    status="pending",
                )
                db.add(instance)
                instances.append(instance)

    await db.flush()

    # Build response
    template_response = ChoreResponse(
        id=template.id,
        title=template.title,
        description=template.description,
        assignment_mode=template.assignment_mode,
        recurrence_rule=template.recurrence_rule,
        default_assigned_to_id=template.default_assigned_to_id,
        point_value=template.point_value,
        is_active=template.is_active,
        created_by_id=template.created_by_id,
        created_at=str(template.created_at),
        updated_at=str(template.updated_at),
    )

    instances_response = [
        ChoreInstanceResponse(
            id=i.id,
            chore_template_id=i.chore_template_id,
            assigned_to_id=i.assigned_to_id,
            due_date=i.due_date,
            status=i.status,
            claimed_by_id=i.claimed_by_id,
            claimed_at=i.claimed_at,
            completed_by_id=i.completed_by_id,
            completed_at=i.completed_at,
            created_at=str(i.created_at),
        )
        for i in instances
    ]

    return {"template": template_response, "instances": instances_response}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/chores.py
git commit -m "feat: add POST /chores/quick-add endpoint"
```

---

### Task 3: Add choreAPI.quickAdd to frontend client

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add quickAdd method to choreAPI**

In `frontend/src/api/client.ts`, add this method to the `choreAPI` object (after `getStats`, around line 87):

```typescript
  quickAdd: (data: { title: string; description?: string; point_value: number; assigned_to_id: string; recurrence_rule: string }) =>
    api.post('/chores/quick-add', data).then(r => r.data),
```

The full `choreAPI` object should end with:

```typescript
export const choreAPI = {
  getTemplates: () => api.get('/chores/templates').then(r => r.data),
  createTemplate: (data: { title: string; description?: string; assignment_mode: string; recurrence_rule: string; point_value: number }) =>
    api.post('/chores/templates', data).then(r => r.data),
  updateTemplate: (id: string, data: Partial<{ title: string; description?: string; assignment_mode: string; recurrence_rule: string; point_value: number; is_active: boolean }>) =>
    api.patch(`/chores/templates/${id}`, data).then(r => r.data),
  deactivateTemplate: (id: string) =>
    api.delete(`/chores/templates/${id}`).then(r => r.data),

  getInstances: (statusFilter?: string, dueDate?: string) =>
    api.get('/chores/instances', { params: { status_filter: statusFilter, due_date: dueDate } }).then(r => r.data),
  claimInstance: (id: string) =>
    api.post(`/chores/instances/${id}/claim`).then(r => r.data),
  completeInstance: (id: string) =>
    api.post(`/chores/instances/${id}/complete`).then(r => r.data),

  getCompletionLog: (limit = 50) =>
    api.get('/chores/completion-log', { params: { limit } }).then(r => r.data),

  getStats: () =>
    api.get('/chores/stats').then(r => r.data),

  quickAdd: (data: { title: string; description?: string; point_value: number; assigned_to_id: string; recurrence_rule: string }) =>
    api.post('/chores/quick-add', data).then(r => r.data),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add choreAPI.quickAdd method"
```

---

### Task 4: Add Quick Add modal to ChoresPage

**Files:**
- Modify: `frontend/src/pages/ChoresPage.tsx`

- [ ] **Step 1: Add quickAddMutation and form state**

In `frontend/src/pages/ChoresPage.tsx`, after the existing `claimMutation` (around line 101), add:

```typescript
  const [showQuickAddModal, setShowQuickAddModal] = useState(false)
  const [quickAddForm, setQuickAddForm] = useState({
    title: '',
    description: '',
    point_value: 10,
    assigned_to_id: '',
    recurrence_rule: 'none',
  })
  const [quickAddError, setQuickAddError] = useState('')

  const { data: profiles } = useQuery({
    queryKey: ['users-profiles'],
    queryFn: () => api.get('/users/profiles').then(r => r.data),
  })

  const quickAddMutation = useMutation({
    mutationFn: choreAPI.quickAdd,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chores-instances'] })
      queryClient.invalidateQueries({ queryKey: ['chores-stats'] })
      setShowQuickAddModal(false)
      setQuickAddForm({ title: '', description: '', point_value: 10, assigned_to_id: '', recurrence_rule: 'none' })
      setQuickAddError('')
    },
    onError: (err: any) => {
      const message = err.response?.data?.detail || 'Failed to add chore'
      setQuickAddError(message)
    },
  })

  const handleQuickAdd = (e: React.FormEvent) => {
    e.preventDefault()
    setQuickAddError('')
    if (!quickAddForm.title.trim()) {
      setQuickAddError('Title is required')
      return
    }
    if (!quickAddForm.assigned_to_id) {
      setQuickAddError('Please select a user')
      return
    }
    quickAddMutation.mutate(quickAddForm)
  }
```

- [ ] **Step 2: Add api import**

In `frontend/src/pages/ChoresPage.tsx`, update the imports at line 3 to include `api`:

```typescript
import { choreAPI, api } from '../api/client'
```

- [ ] **Step 3: Add "Quick Add" button in header**

In the JSX, after the `<h1 className="text-2xl font-bold mb-6">Chores</h1>` line (around line 134), add:

```typescript
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-2xl font-bold">Chores</h1>
          <button
            onClick={() => setShowQuickAddModal(true)}
            className="bg-blue-600 hover:bg-blue-700 px-4 py-2 rounded-lg"
          >
            Quick Add
          </button>
        </div>
```

- [ ] **Step 4: Add Quick Add modal before closing div**

Add this modal before the final `</div>` closing tag (before the last `return` block's closing `</div>`):

```typescript
        {showQuickAddModal && (
          <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={() => setShowQuickAddModal(false)}>
            <div className="bg-gray-800 rounded-lg p-6 w-full max-w-md" onClick={e => e.stopPropagation()}>
              <h2 className="text-xl font-bold mb-4">Add Chore</h2>
              {quickAddError && (
                <div className="bg-red-900/50 text-red-300 px-4 py-2 rounded-lg mb-4">
                  {quickAddError}
                </div>
              )}
              <form onSubmit={handleQuickAdd} className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Title *</label>
                  <input
                    type="text"
                    value={quickAddForm.title}
                    onChange={e => setQuickAddForm(f => ({ ...f, title: e.target.value }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    placeholder="e.g., Take out trash"
                    autoFocus
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Description</label>
                  <textarea
                    value={quickAddForm.description}
                    onChange={e => setQuickAddForm(f => ({ ...f, description: e.target.value }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    placeholder="Optional description"
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Assign to *</label>
                  <select
                    value={quickAddForm.assigned_to_id}
                    onChange={e => setQuickAddForm(f => ({ ...f, assigned_to_id: e.target.value }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="">Select a user</option>
                    {profiles?.map((p: { id: string; name: string; avatar_emoji: string }) => (
                      <option key={p.id} value={p.id}>
                        {p.avatar_emoji} {p.name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Point Value</label>
                  <input
                    type="number"
                    value={quickAddForm.point_value}
                    onChange={e => setQuickAddForm(f => ({ ...f, point_value: parseInt(e.target.value) || 10 }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                    min={1}
                    max={1000}
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Recurrence (optional)</label>
                  <select
                    value={quickAddForm.recurrence_rule}
                    onChange={e => setQuickAddForm(f => ({ ...f, recurrence_rule: e.target.value }))}
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white"
                  >
                    <option value="none">None (one-time)</option>
                    <option value="daily">Daily</option>
                    <option value="weekly_mon">Weekly - Monday</option>
                    <option value="weekly_tue">Weekly - Tuesday</option>
                    <option value="weekly_wed">Weekly - Wednesday</option>
                    <option value="weekly_thu">Weekly - Thursday</option>
                    <option value="weekly_fri">Weekly - Friday</option>
                    <option value="weekly_sat">Weekly - Saturday</option>
                    <option value="weekly_sun">Weekly - Sunday</option>
                    <option value="every_2_days">Every 2 Days</option>
                    <option value="every_3_days">Every 3 Days</option>
                    <option value="every_5_days">Every 5 Days</option>
                    <option value="monthly_1">Monthly - 1st</option>
                    <option value="monthly_15">Monthly - 15th</option>
                    <option value="monthly_28">Monthly - 28th</option>
                  </select>
                </div>
                <div className="flex gap-2 pt-2">
                  <button
                    type="submit"
                    disabled={quickAddMutation.isPending}
                    className="flex-1 bg-green-600 hover:bg-green-700 disabled:bg-gray-600 px-4 py-2 rounded-lg"
                  >
                    {quickAddMutation.isPending ? 'Adding...' : 'Add Chore'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowQuickAddModal(false); setQuickAddError('') }}
                    className="bg-gray-700 hover:bg-gray-600 px-4 py-2 rounded-lg"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/ChoresPage.tsx frontend/src/api/client.ts
git commit -m "feat: add quick add chore modal to ChoresPage"
```

---

### Task 5: Build and test frontend

**Files:**
- N/A (build command only)

- [ ] **Step 1: Build frontend and typecheck**

Run: `cd frontend && npm run build`
Expected: Success (no TypeScript errors, Vite build completes)

- [ ] **Step 2: Commit**

```bash
git add .
git commit -m "chore: verify frontend build passes"
```

---

### Task 6: Test backend endpoint manually

**Files:**
- N/A (manual test only)

- [ ] **Step 1: Start backend and test endpoint**

```bash
cd backend && source .venv/bin/activate
# Start the server in background
uvicorn app.main:app --reload --port 8000 &
sleep 3

# Login to get JWT token (use admin PIN 1137)
TOKEN=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d '{"pin":"1137"}' | jq -r '.access_token')

# Test quick-add endpoint
curl -s -X POST http://localhost:8000/api/chores/quick-add \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test chore","point_value":10,"assigned_to_id":"existing-user-id","recurrence_rule":"none"}'
```

Expected: Returns `{ template: {...}, instances: [...] }` with 201 status

- [ ] **Step 2: Test with recurrence**

```bash
curl -s -X POST http://localhost:8000/api/chores/quick-add \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Weekly chore","point_value":15,"assigned_to_id":"existing-user-id","recurrence_rule":"weekly_mon"}'
```

Expected: Returns template + multiple instances (one per week for 7 days)

- [ ] **Step 3: Test invalid assigned_to_id**

```bash
curl -s -X POST http://localhost:8000/api/chores/quick-add \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Bad chore","point_value":10,"assigned_to_id":"non-existent-id","recurrence_rule":"none"}'
```

Expected: Returns 404 with `{"detail":"Assigned user not found"}`

- [ ] **Step 4: Kill server and commit**

```bash
kill %1 2>/dev/null; true
git add .
git commit -m "chore: manual test quick-add endpoint"
```

---

### Task 7: Rebuild and deploy Docker images

**Files:**
- N/A (deploy commands only)

- [ ] **Step 1: Build and push Docker images**

```bash
cd /Users/vernon/Documents/opencode/FamHub-redo
docker compose -f docker-compose.prod.yml build --no-cache api web
docker compose -f docker-compose.prod.yml push api web
```

Expected: Both images pushed successfully to Docker Hub

- [ ] **Step 2: Deploy to production**

```bash
 scp docker-compose.prod.yml config/Caddyfile.prod vernon@192.168.10.13:/home/vernon/OpenFamHub/
 ssh vernon@192.168.10.13 "cd /home/vernon/OpenFamHub && docker compose -f docker-compose.prod.yml down && docker compose -f docker-compose.prod.yml up -d"
```

Expected: Containers restart with new images

- [ ] **Step 3: Verify deployment**

```bash
curl -k https://openfamhub.local/api/health
```

Expected: Health check returns OK

- [ ] **Step 4: Commit**

```bash
git add .
git commit -m "chore: bump version and deploy quick-add feature"
```

---

## Self-Review Checklist

**Spec coverage:**
- [x] Frontend "Quick Add" button → Task 4, Step 3
- [x] Modal form with all fields → Task 4, Step 4
- [x] choreAPI.quickAdd method → Task 3
- [x] Backend POST /chores/quick-add endpoint → Task 2
- [x] ChoreQuickAdd schema → Task 1
- [x] Recurrence "none" creates 1 instance → Task 2, Step 3
- [x] Recurrence set creates instances for 7 days → Task 2, Step 3
- [x] Error handling (404 user, 400 validation) → Task 2, Task 4 Step 1
- [x] Loading state → Task 4, Step 4
- [x] All logged-in users can use it → Task 2 uses `get_current_user` (not `require_admin`)

**Placeholder scan:** No "TBD", "TODO", "implement later", or vague requirements found.

**Type consistency:** All type names match between tasks (`ChoreQuickAdd`, `choreAPI.quickAdd`, `quickAddMutation`).

**Scope check:** Focused single feature, one implementation plan.

---

Plan complete.
