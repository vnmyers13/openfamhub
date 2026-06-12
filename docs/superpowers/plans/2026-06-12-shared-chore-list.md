# Shared Chore List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Admin tab to ChoresPage showing all chore instances in a sortable table with status and date filtering.

**Architecture:** New backend endpoint for admin instances with filtering, new frontend Admin tab with filter bar and sortable table. Follows existing patterns in chores.py router and ChoresPage.tsx.

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic, React, TanStack Query, TypeScript

---

### Task 1: Add ChoreInstanceAdminResponse schema

**Files:**
- Modify: `backend/app/schemas/models.py:207-208` (after ChoreInstanceResponse)

- [ ] **Step 1: Add the new schema class**

Append after `ChoreInstanceResponse` class (after line 207):

```python
class ChoreInstanceAdminResponse(BaseModel):
    id: str
    chore_template_id: str
    title: str
    assigned_to_id: Optional[str] = None
    assigned_to_name: Optional[str] = None
    due_date: str
    status: str
    claimed_by_id: Optional[str] = None
    claimed_at: Optional[str] = None
    completed_by_id: Optional[str] = None
    completed_at: Optional[str] = None
    point_value: int
```

- [ ] **Step 2: Export the schema**

Verify `backend/app/schemas/__init__.py` exports `ChoreInstanceAdminResponse`. If the file re-exports from models.py, it will be auto-included. Check:
```bash
grep -q "ChoreInstanceAdminResponse" backend/app/schemas/__init__.py || echo "Need to add export"
```

If needed, add to `backend/app/schemas/__init__.py`:
```python
from app.schemas.models import ChoreInstanceAdminResponse
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/models.py backend/app/schemas/__init__.py
git commit -m "feat: add ChoreInstanceAdminResponse schema"
```

---

### Task 2: Add admin instances endpoint

**Files:**
- Modify: `backend/app/routers/chores.py`

- [ ] **Step 1: Import the new schema**

Add `ChoreInstanceAdminResponse` to the imports at line 10-18:

```python
from app.schemas.models import (
    ChoreCreate,
    ChoreUpdate,
    ChoreResponse,
    ChoreInstanceResponse,
    ChoreCompletionLogResponse,
    ChoreStatsResponse,
    ChoreQuickAdd,
    ChoreInstanceAdminResponse,
)
```

- [ ] **Step 2: Add the admin instances endpoint**

Append after the existing `list_chore_instances` function (after line 220):

```python
@router.get("/admin/instances", response_model=list[ChoreInstanceAdminResponse])
async def list_admin_chore_instances(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, claimed, completed, expired"),
    start_date: Optional[str] = Query(None, description="Filter by due date >= (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by due date <= (ISO format)"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    query = select(ChoreInstance).join(Chore, ChoreInstance.chore_template_id == Chore.id).outerjoin(User, ChoreInstance.assigned_to_id == User.id)

    if status_filter:
        query = query.where(ChoreInstance.status == status_filter)
    if start_date:
        query = query.where(ChoreInstance.due_date >= start_date)
    if end_date:
        query = query.where(ChoreInstance.due_date <= end_date)

    query = query.order_by(ChoreInstance.due_date, ChoreInstance.status)
    result = await db.execute(query)
    instances = result.scalars().all()

    return [
        ChoreInstanceAdminResponse(
            id=i.id,
            chore_template_id=i.chore_template_id,
            title=t.title,
            assigned_to_id=i.assigned_to_id,
            assigned_to_name=u.name if u else None,
            due_date=i.due_date,
            status=i.status,
            claimed_by_id=i.claimed_by_id,
            claimed_at=str(i.claimed_at) if i.claimed_at else None,
            completed_by_id=i.completed_by_id,
            completed_at=str(i.completed_at) if i.completed_at else None,
            point_value=t.point_value,
        )
        for i, t, u in [(inst, chore, usr) for inst, chore, usr in result.statement.left_join(Chore, ChoreInstance.chore_template_id == Chore.id).outerjoin(User, ChoreInstance.assigned_to_id == User.id).scalars()]
    ]
```

Wait — the above approach with the list comprehension won't work with SQLAlchemy 2.0. Let me use the correct approach:

```python
@router.get("/admin/instances", response_model=list[ChoreInstanceAdminResponse])
async def list_admin_chore_instances(
    status_filter: Optional[str] = Query(None, description="Filter by status: pending, claimed, completed, expired"),
    start_date: Optional[str] = Query(None, description="Filter by due date >= (ISO format)"),
    end_date: Optional[str] = Query(None, description="Filter by due date <= (ISO format)"),
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    query = (
        select(ChoreInstance, Chore, User)
        .join(Chore, ChoreInstance.chore_template_id == Chore.id)
        .outerjoin(User, ChoreInstance.assigned_to_id == User.id)
    )

    if status_filter:
        query = query.where(ChoreInstance.status == status_filter)
    if start_date:
        query = query.where(ChoreInstance.due_date >= start_date)
    if end_date:
        query = query.where(ChoreInstance.due_date <= end_date)

    query = query.order_by(ChoreInstance.due_date, ChoreInstance.status)
    result = await db.execute(query)
    rows = result.all()

    return [
        ChoreInstanceAdminResponse(
            id=inst.id,
            chore_template_id=inst.chore_template_id,
            title=chore.title,
            assigned_to_id=inst.assigned_to_id,
            assigned_to_name=user.name if user else None,
            due_date=inst.due_date,
            status=inst.status,
            claimed_by_id=inst.claimed_by_id,
            claimed_at=str(inst.claimed_at) if inst.claimed_at else None,
            completed_by_id=inst.completed_by_id,
            completed_at=str(inst.completed_at) if inst.completed_at else None,
            point_value=chore.point_value,
        )
        for inst, chore, user in rows
    ]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/chores.py
git commit -m "feat: add admin instances endpoint with status and date filters"
```

---

### Task 3: Add admin instances test

**Files:**
- Create: `backend/tests/test_chores_admin.py`

- [ ] **Step 1: Write the test file**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.core.database import get_db
from app.models import User, Chore, ChoreInstance


@pytest.fixture
def admin_user():
    return {
        "id": "admin-1",
        "name": "Admin User",
        "role": "admin",
    }


@pytest.fixture
def member_user():
    return {
        "id": "member-1",
        "name": "Member User",
        "role": "member",
    }


@pytest.fixture
def chore_template(admin_user):
    template = Chore(
        id="chore-1",
        title="Dishes",
        description="Wash and put away dishes",
        assignment_mode="assigned",
        recurrence_rule="daily",
        point_value=10,
        created_by_id=admin_user["id"],
    )
    return template


@pytest.fixture
def chore_instance(chore_template, member_user):
    instance = ChoreInstance(
        id="instance-1",
        chore_template_id=chore_template.id,
        assigned_to_id=member_user["id"],
        due_date="2026-06-12",
        status="pending",
    )
    return instance


async def test_admin_can_get_all_instances(
    client: TestClient,
    db_session: AsyncSession,
    admin_user,
    chore_template,
    chore_instance,
):
    """Admin should see all chore instances."""
    db_session.add(chore_template)
    db_session.add(chore_instance)
    await db_session.commit()

    # Override auth to admin
    app.dependency_overrides[get_db] = lambda: db_session
    original_auth = app.dependency_overrides.get(app.dependency_overrides)
    
    # Use admin token
    from app.core.security import create_token
    token = create_token(admin_user["id"], admin_user["name"], admin_user["role"])
    
    response = client.get(
        "/api/chores/admin/instances",
        headers={"Cookie": f"token={token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["title"] == "Dishes"
    assert data[0]["assigned_to_name"] == "Member User"
    assert data[0]["status"] == "pending"
    
    app.dependency_overrides.clear()


async def test_non_admin_cannot_access_admin_endpoint(
    client: TestClient,
    db_session: AsyncSession,
    member_user,
):
    """Non-admin should get 403."""
    from app.core.security import create_token
    token = create_token(member_user["id"], member_user["name"], member_user["role"])
    
    response = client.get(
        "/api/chores/admin/instances",
        headers={"Cookie": f"token={token}"},
    )
    
    assert response.status_code == 403
    
    app.dependency_overrides.clear()


async def test_admin_filter_by_status(
    client: TestClient,
    db_session: AsyncSession,
    admin_user,
    chore_template,
    chore_instance,
):
    """Admin should filter instances by status."""
    db_session.add(chore_template)
    db_session.add(chore_instance)
    await db_session.commit()
    
    from app.core.security import create_token
    token = create_token(admin_user["id"], admin_user["name"], admin_user["role"])
    
    response = client.get(
        "/api/chores/admin/instances",
        params={"status_filter": "pending"},
        headers={"Cookie": f"token={token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert all(item["status"] == "pending" for item in data)
    
    app.dependency_overrides.clear()


async def test_admin_filter_by_date_range(
    client: TestClient,
    db_session: AsyncSession,
    admin_user,
    chore_template,
    chore_instance,
):
    """Admin should filter instances by date range."""
    db_session.add(chore_template)
    db_session.add(chore_instance)
    await db_session.commit()
    
    from app.core.security import create_token
    token = create_token(admin_user["id"], admin_user["name"], admin_user["role"])
    
    response = client.get(
        "/api/chores/admin/instances",
        params={"start_date": "2026-06-01", "end_date": "2026-06-30"},
        headers={"Cookie": f"token={token}"},
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    
    app.dependency_overrides.clear()
```

- [ ] **Step 2: Run the tests**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_chores_admin.py -v
```

Expected: All tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_chores_admin.py
git commit -m "test: add admin instances endpoint tests"
```

---

### Task 4: Add getAdminInstances to choreAPI

**Files:**
- Modify: `frontend/src/api/client.ts:67-91`

- [ ] **Step 1: Add the admin instances method**

Append to `choreAPI` object (after line 90, before the closing brace):

```typescript
  getAdminInstances: (statusFilter?: string, startDate?: string, endDate?: string) =>
    api.get('/chores/admin/instances', { params: { status_filter: statusFilter, start_date: startDate, end_date: endDate } }).then(r => r.data),
```

Full updated choreAPI:

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

  getAdminInstances: (statusFilter?: string, startDate?: string, endDate?: string) =>
    api.get('/chores/admin/instances', { params: { status_filter: statusFilter, start_date: startDate, end_date: endDate } }).then(r => r.data),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add getAdminInstances to choreAPI"
```

---

### Task 5: Add Admin tab to ChoresPage

**Files:**
- Modify: `frontend/src/pages/ChoresPage.tsx`

- [ ] **Step 1: Update Tab type and state**

Change the Tab type from:
```typescript
type Tab = 'my' | 'available' | 'history' | 'templates'
```

To:
```typescript
type Tab = 'my' | 'available' | 'history' | 'templates' | 'admin'
```

Add admin filter state after line 52:
```typescript
  const [adminStatusFilter, setAdminStatusFilter] = useState('all')
  const [adminStartDate, setAdminStartDate] = useState('')
  const [adminEndDate, setAdminEndDate] = useState('')
  const [adminSortColumn, setAdminSortColumn] = useState<'due_date' | 'status' | 'title'>('due_date')
  const [adminSortDirection, setAdminSortDirection] = useState<'asc' | 'desc'>('asc')
```

- [ ] **Step 2: Add admin instances query**

After the existing `stats` query (around line 85), add:

```typescript
  const { data: adminInstances, refetch: refetchAdminInstances } = useQuery({
    queryKey: ['chores-admin-instances', adminStatusFilter, adminStartDate, adminEndDate],
    queryFn: () => choreAPI.getAdminInstances(
      adminStatusFilter !== 'all' ? adminStatusFilter : undefined,
      adminStartDate || undefined,
      adminEndDate || undefined,
    ),
    enabled: isAdmin && activeTab === 'admin',
  })
```

- [ ] **Step 3: Add admin tab content**

Find the existing tab rendering logic (around line 170-200) and add the admin tab case. The admin tab should render a filter bar and table:

```typescript
  if (activeTab === 'admin' && isAdmin) {
    const sortedInstances = [...(adminInstances || [])].sort((a, b) => {
      let aVal: string = ''
      let bVal: string = ''
      
      if (adminSortColumn === 'due_date') {
        aVal = a.due_date
        bVal = b.due_date
      } else if (adminSortColumn === 'status') {
        aVal = a.status
        bVal = b.status
      } else if (adminSortColumn === 'title') {
        aVal = a.title
        bVal = b.title
      }
      
      if (aVal < bVal) return adminSortDirection === 'asc' ? -1 : 1
      if (aVal > bVal) return adminSortDirection === 'asc' ? 1 : -1
      return 0
    })

    const handleSort = (column: 'due_date' | 'status' | 'title') => {
      if (adminSortColumn === column) {
        setAdminSortDirection(adminSortDirection === 'asc' ? 'desc' : 'asc')
      } else {
        setAdminSortColumn(column)
        setAdminSortDirection('asc')
      }
    }

    const getStatusBadge = (status: string) => {
      const colors: Record<string, string> = {
        pending: 'bg-yellow-100 text-yellow-800',
        claimed: 'bg-blue-100 text-blue-800',
        completed: 'bg-green-100 text-green-800',
        expired: 'bg-red-100 text-red-800',
      }
      return colors[status] || 'bg-gray-100 text-gray-800'
    }

    return (
      <div className="space-y-4">
        <h2 className="text-2xl font-bold text-gray-800">Admin Chore Dashboard</h2>
        
        {/* Filter Bar */}
        <div className="flex flex-wrap gap-4 bg-white p-4 rounded-lg shadow">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <select
              value={adminStatusFilter}
              onChange={(e) => setAdminStatusFilter(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All</option>
              <option value="pending">Pending</option>
              <option value="claimed">Claimed</option>
              <option value="completed">Completed</option>
              <option value="expired">Expired</option>
            </select>
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">From</label>
            <input
              type="date"
              value={adminStartDate}
              onChange={(e) => setAdminStartDate(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">To</label>
            <input
              type="date"
              value={adminEndDate}
              onChange={(e) => setAdminEndDate(e.target.value)}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div className="flex items-end">
            <button
              onClick={() => {
                setAdminStatusFilter('all')
                setAdminStartDate('')
                setAdminEndDate('')
              }}
              className="px-4 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300"
            >
              Clear Filters
            </button>
          </div>
        </div>
        
        {/* Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('title')}
                >
                  Title {adminSortColumn === 'title' && (adminSortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Assigned To
                </th>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('status')}
                >
                  Status {adminSortColumn === 'status' && (adminSortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th 
                  className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                  onClick={() => handleSort('due_date')}
                >
                  Due Date {adminSortColumn === 'due_date' && (adminSortDirection === 'asc' ? '↑' : '↓')}
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Completed
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sortedInstances.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-6 py-8 text-center text-gray-500">
                    No chore instances found
                  </td>
                </tr>
              ) : (
                sortedInstances.map((instance: any) => (
                  <tr key={instance.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {instance.title}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {instance.assigned_to_name || 'Unassigned'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`px-2 inline-flex text-xs leading-none font-semibold rounded-full ${getStatusBadge(instance.status)}`}>
                        {instance.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {instance.due_date}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {instance.completed_at ? new Date(instance.completed_at).toLocaleDateString() : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    )
  }
```

- [ ] **Step 2: Add Admin tab button**

Find the tab navigation buttons (around line 200-230) and add an Admin tab button after the Templates tab:

```typescript
{isAdmin && (
  <button
    onClick={() => setActiveTab('admin')}
    className={`px-4 py-2 rounded-lg font-medium transition-colors ${
      activeTab === 'admin'
        ? 'bg-indigo-600 text-white'
        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
    }`}
  >
    Admin
  </button>
)}
```

- [ ] **Step 3: Verify frontend build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ChoresPage.tsx
git commit -m "feat: add Admin tab to ChoresPage with sortable table and filters"
```

---

### Task 6: Run full test suite

**Files:**
- N/A (verification only)

- [ ] **Step 1: Run backend tests**

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
```

Expected: All tests pass (45+ tests).

- [ ] **Step 2: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds.

- [ ] **Step 3: Commit any fixes**

If tests fail, fix and commit. If everything passes:

```bash
git commit -m "chore: verify all tests pass for shared chore list" --allow-empty
```
