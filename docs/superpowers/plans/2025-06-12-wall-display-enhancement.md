# Wall Display Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add shared chores and today's menu to the wall display, with configurable calendar views (agenda/daily/weekly/monthly) and chore views (pending+completed / pending only).

**Architecture:** Extract 4 new React components from WallDisplay, add a minimal backend endpoint for wall chores (includes completed), refactor WallDisplay into a thin composer. Zero backend changes for meals or announcements — uses existing endpoints.

**Tech Stack:** React 19, TypeScript, Tailwind CSS 3, FastAPI (minimal), SQLAlchemy async

---

## Task 1: Backend — Wall chores endpoint

**Files:**
- Modify: `backend/app/routers/chores.py`
- Modify: `backend/app/schemas/models.py`

- [ ] **Step 1: Add WallChoreResponse schema**

Add this class to `backend/app/schemas/models.py` after `ChoreInstanceAdminResponse` (around line 223):

```python
class WallChoreResponse(BaseModel):
    id: str
    title: str
    assigned_to_name: Optional[str] = None
    status: str
    due_date: str
    completed_at: Optional[str] = None
```

- [ ] **Step 2: Add GET /chores/wall endpoint**

Add this route to `backend/app/routers/chores.py` after the existing `/instances` endpoint (around line 222):

```python
@router.get("/wall", response_model=list[WallChoreResponse])
async def list_wall_chores(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Get today's chores (pending + completed) for wall display."""
    today = datetime.now(timezone.utc).date().isoformat()

    query = (
        select(ChoreInstance, Chore, User)
        .join(Chore, ChoreInstance.chore_template_id == Chore.id)
        .outerjoin(User, ChoreInstance.assigned_to_id == User.id)
        .where(
            or_(
                ChoreInstance.due_date == today,
                ChoreInstance.completed_at != None,  # noqa: E711
            )
        )
        .order_by(ChoreInstance.status, ChoreInstance.due_date)
    )

    result = await db.execute(query)
    rows = result.all()

    return [
        WallChoreResponse(
            id=inst.id,
            title=chore.title,
            assigned_to_name=user.name if user else None,
            status=inst.status,
            due_date=inst.due_date,
            completed_at=str(inst.completed_at) if inst.completed_at else None,
        )
        for inst, chore, user in rows
    ]
```

Note: Add `or_` to the imports at the top of the file if not already present:
```python
from sqlalchemy import func, select, or_
```

- [ ] **Step 3: Run backend tests**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_chores*.py -v`
Expected: Existing chore tests pass (any failures are pre-existing)

- [ ] **Step 4: Commit**

```bash
git add backend/app/routers/chores.py backend/app/schemas/models.py
git commit -m "feat: add wall chores endpoint with pending+completed"
```

## Task 2: Frontend — API client for wall chores

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add wallChoreAPI object**

Add this after the existing `choreAPI` export (around line 112):

```typescript
export const wallChoreAPI = {
  getWallChores: () => api.get('/chores/wall').then(r => r.data),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add wallChoreAPI for wall display"
```

## Task 3: Frontend — MenuWallPanel component

**Files:**
- Create: `frontend/src/components/MenuWallPanel.tsx`

- [ ] **Step 1: Create MenuWallPanel.tsx**

```typescript
import { useQuery } from '@tanstack/react-query';
import api from '../api/client';

interface WallMeal {
  id: string;
  meal_type: string;
  date: string;
  title: string;
  notes?: string | null;
  recipe?: { id: string; title: string } | null;
}

const MEAL_ORDER = ['breakfast', 'lunch', 'dinner', 'snack'];

export default function MenuWallPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['wall-menu'],
    queryFn: async () => {
      const res = await api.get('/meals/plans');
      const meals = res.data as { meals: WallMeal[] };
      const today = new Date().toISOString().split('T')[0];
      return meals.meals.filter((m) => m.date === today).sort((a, b) => {
        return MEAL_ORDER.indexOf(a.meal_type) - MEAL_ORDER.indexOf(b.meal_type);
      });
    },
    refetchInterval: 60000,
  });

  const meals = data as WallMeal[] | undefined;

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">Loading menu...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400 text-xl">Failed to load menu</div>
      </div>
    );
  }

  if (!meals || meals.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">No meals planned for today</div>
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      {meals.map((meal) => (
        <div key={meal.id} className="bg-white/5 rounded-xl p-4 border border-white/10">
          <div className="text-xs font-semibold text-blue-400 uppercase tracking-wider mb-1">
            {meal.meal_type}
          </div>
          <div className="text-2xl font-semibold text-white">
            {meal.recipe?.title || meal.title}
          </div>
          {meal.notes && (
            <div className="text-slate-400 text-lg mt-1">{meal.notes}</div>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Frontend build check**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/MenuWallPanel.tsx
git commit -m "feat: add MenuWallPanel component"
```

## Task 4: Frontend — CalendarWallView component

**Files:**
- Create: `frontend/src/components/CalendarWallView.tsx`

- [ ] **Step 1: Create CalendarWallView.tsx**

```typescript
import { useState } from 'react';

interface WallEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  color_hex?: string;
  is_all_day?: boolean;
  description?: string;
  location?: string;
}

type CalendarView = 'agenda' | 'daily' | 'weekly' | 'monthly';

interface CalendarWallViewProps {
  events: WallEvent[];
}

const formatTime = (dateStr: string) => {
  return new Date(dateStr).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  });
};

export default function CalendarWallView({ events }: CalendarWallViewProps) {
  const [view, setView] = useState<CalendarView>('daily');

  const now = new Date();
  const today = now.toDateString();
  const todayStr = now.toISOString().split('T')[0];

  const todayEvents = events
    .filter((e) => new Date(e.start_time).toDateString() === today)
    .sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());

  // Weekly: get all events this week
  const weekStart = new Date(now);
  weekStart.setDate(now.getDate() - now.getDay());
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekStart.getDate() + 6);

  const weeklyEvents = events.filter((e) => {
    const d = new Date(e.start_time);
    return d >= weekStart && d <= weekEnd;
  });

  // Monthly: get all events this month
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);
  const monthEnd = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  const monthlyEvents = events.filter((e) => {
    const d = new Date(e.start_time);
    return d >= monthStart && d <= monthEnd;
  });

  const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  const viewButtons: { key: CalendarView; label: string }[] = [
    { key: 'agenda', label: 'Agenda' },
    { key: 'daily', label: 'Daily' },
    { key: 'weekly', label: 'Weekly' },
    { key: 'monthly', label: 'Monthly' },
  ];

  const renderAgenda = () => {
    if (todayEvents.length === 0) {
      return <p className="text-slate-400 text-xl text-center mt-8">No events today</p>;
    }
    return (
      <div className="space-y-3">
        {todayEvents.map((event) => (
          <div key={event.id} className="flex items-center gap-4 p-3 rounded-xl bg-white/5">
            <div className="w-2 h-12 rounded-full flex-shrink-0" style={{ backgroundColor: event.color_hex || '#3B82F6' }} />
            <div className="flex-1 min-w-0">
              <p className="text-xl font-semibold text-white truncate">{event.title}</p>
              <p className="text-slate-400 text-lg">{formatTime(event.start_time)} - {formatTime(event.end_time)}</p>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderDaily = () => {
    if (todayEvents.length === 0) {
      return <p className="text-slate-400 text-xl text-center mt-8">No events today</p>;
    }
    return (
      <div className="space-y-2">
        {todayEvents.map((event) => (
          <div key={event.id} className="flex gap-4 p-3 rounded-xl bg-white/5">
            <div className="text-lg text-slate-400 w-24 flex-shrink-0 text-right">
              {formatTime(event.start_time)}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xl font-semibold text-white truncate">{event.title}</p>
              <p className="text-slate-400 text-lg">{formatTime(event.end_time)}</p>
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderWeekly = () => {
    const weekDays = [];
    for (let i = 0; i < 7; i++) {
      const d = new Date(weekStart);
      d.setDate(weekStart.getDate() + i);
      const dayStr = d.toISOString().split('T')[0];
      const dayEvents = weeklyEvents.filter((e) => new Date(e.start_time).toISOString().split('T')[0] === dayStr);
      weekDays.push({ date: d, label: days[d.getDay()], dayStr, events: dayEvents });
    }

    return (
      <div className="grid grid-cols-7 gap-2 h-full">
        {weekDays.map((day) => (
          <div key={day.dayStr} className={`rounded-xl p-2 ${day.dayStr === todayStr ? 'bg-blue-600/20 border border-blue-500/30' : 'bg-white/5'}`}>
            <div className="text-center text-sm font-semibold text-slate-400 mb-2">{day.label}</div>
            <div className="space-y-1">
              {day.events.slice(0, 3).map((event) => (
                <div key={event.id} className="text-xs text-white truncate bg-white/10 rounded px-1 py-0.5" title={event.title}>
                  {event.title}
                </div>
              ))}
              {day.events.length > 3 && (
                <div className="text-xs text-slate-500 text-center">+{day.events.length - 3} more</div>
              )}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderMonthly = () => {
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
    const startPadding = firstDay.getDay();
    const daysInMonth = lastDay.getDate();

    const cells: { day: number; isCurrentMonth: boolean; dateStr: string; events: WallEvent[] }[] = [];

    // Previous month padding
    for (let i = 0; i < startPadding; i++) {
      cells.push({ day: 0, isCurrentMonth: false, dateStr: '', events: [] });
    }

    // Current month
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
      const dayEvents = monthlyEvents.filter((e) => new Date(e.start_time).toISOString().split('T')[0] === dateStr);
      cells.push({ day: d, isCurrentMonth: true, dateStr, events: dayEvents });
    }

    return (
      <div className="grid grid-cols-7 gap-1 h-full">
        {days.map((d) => (
          <div key={d} className="text-center text-sm font-semibold text-slate-500">{d}</div>
        ))}
        {cells.map((cell, i) => (
          <div
            key={i}
            className={`rounded-lg p-1 min-h-[60px] ${
              !cell.isCurrentMonth ? 'bg-transparent' :
              cell.dateStr === todayStr ? 'bg-blue-600/20 border border-blue-500/30' : 'bg-white/5'
            }`}
          >
            {cell.isCurrentMonth && (
              <>
                <div className="text-sm text-white">{cell.day}</div>
                <div className="space-y-0.5 mt-1">
                  {cell.events.slice(0, 2).map((event) => (
                    <div key={event.id} className="text-[10px] text-white truncate bg-white/10 rounded px-0.5" title={event.title}>
                      {event.title}
                    </div>
                  ))}
                  {cell.events.length > 2 && (
                    <div className="text-[10px] text-slate-500">+{cell.events.length - 2}</div>
                  )}
                </div>
              </>
            )}
          </div>
        ))}
      </div>
    );
  };

  const renderContent = () => {
    switch (view) {
      case 'agenda': return renderAgenda();
      case 'daily': return renderDaily();
      case 'weekly': return renderWeekly();
      case 'monthly': return renderMonthly();
    }
  };

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-2xl font-bold text-white">Schedule</h2>
        <div className="flex gap-1">
          {viewButtons.map((btn) => (
            <button
              key={btn.key}
              onClick={() => setView(btn.key)}
              className={`px-3 py-1 rounded-full text-sm font-medium transition ${
                view === btn.key
                  ? 'bg-blue-600 text-white'
                  : 'bg-white/10 text-slate-300 hover:bg-white/20'
              }`}
            >
              {btn.label}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 overflow-y-auto">{renderContent()}</div>
    </div>
  );
}
```

- [ ] **Step 2: Frontend build check**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/CalendarWallView.tsx
git commit -m "feat: add CalendarWallView with agenda/daily/weekly/monthly"
```

## Task 5: Frontend — ChoresWallPanel component

**Files:**
- Create: `frontend/src/components/ChoresWallPanel.tsx`

- [ ] **Step 1: Create ChoresWallPanel.tsx**

```typescript
import { useQuery } from '@tanstack/react-query';
import { wallChoreAPI } from '../api/client';

interface WallChore {
  id: string;
  title: string;
  assigned_to_name?: string | null;
  status: string;
  due_date: string;
  completed_at?: string | null;
}

type ChoreView = 'pending_completed' | 'pending_only';

const STATUS_BADGES: Record<string, { label: string; bg: string; text: string }> = {
  pending: { label: 'Pending', bg: 'bg-yellow-500/20', text: 'text-yellow-400' },
  claimed: { label: 'Claimed', bg: 'bg-blue-500/20', text: 'text-blue-400' },
  completed: { label: 'Done', bg: 'bg-green-500/20', text: 'text-green-400' },
  expired: { label: 'Expired', bg: 'bg-red-500/20', text: 'text-red-400' },
};

export default function ChoresWallPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['wall-chores'],
    queryFn: wallChoreAPI.getWallChores,
    refetchInterval: 60000,
  });

  const [view, setView] = useState<ChoreView>('pending_completed');
  const chores = data as WallChore[] | undefined;

  const filteredChores = view === 'pending_only'
    ? (chores?.filter((c) => c.status !== 'completed') || [])
    : (chores || []);

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">Loading chores...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400 text-xl">Failed to load chores</div>
      </div>
    );
  }

  if (filteredChores.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">No chores for today</div>
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col">
      <div className="flex items-center justify-between mb-3">
        <h2 className="text-2xl font-bold text-white">Chores</h2>
        <div className="flex gap-1">
          <button
            onClick={() => setView('pending_completed')}
            className={`px-3 py-1 rounded-full text-sm font-medium transition ${
              view === 'pending_completed'
                ? 'bg-blue-600 text-white'
                : 'bg-white/10 text-slate-300 hover:bg-white/20'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setView('pending_only')}
            className={`px-3 py-1 rounded-full text-sm font-medium transition ${
              view === 'pending_only'
                ? 'bg-blue-600 text-white'
                : 'bg-white/10 text-slate-300 hover:bg-white/20'
            }`}
          >
            Pending
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-y-auto space-y-2">
        {filteredChores.map((chore) => {
          const badge = STATUS_BADGES[chore.status] || { label: chore.status, bg: 'bg-white/10', text: 'text-white' };
          return (
            <div key={chore.id} className="flex items-center gap-3 p-3 rounded-xl bg-white/5">
              <div className={`px-2 py-0.5 rounded-full text-xs font-semibold ${badge.bg} ${badge.text}`}>
                {badge.label}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-xl font-semibold text-white truncate">{chore.title}</p>
                {chore.assigned_to_name && (
                  <p className="text-slate-400 text-lg">{chore.assigned_to_name}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

Wait — I need to add the `useState` import. Let me fix the imports:

```typescript
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { wallChoreAPI } from '../api/client';
```

- [ ] **Step 2: Frontend build check**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/ChoresWallPanel.tsx
git commit -m "feat: add ChoresWallPanel with view toggle"
```

## Task 6: Frontend — AnnouncementsWallPanel component

**Files:**
- Create: `frontend/src/components/AnnouncementsWallPanel.tsx`

- [ ] **Step 1: Create AnnouncementsWallPanel.tsx**

```typescript
import { useQuery } from '@tanstack/react-query';
import api from '../api/client';

interface WallAnnouncement {
  id: string;
  content: string;
  is_pinned: boolean;
  created_at?: string;
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export default function AnnouncementsWallPanel() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['wall-announcements'],
    queryFn: async () => {
      const res = await api.get('/announcements');
      return res.data as WallAnnouncement[];
    },
    refetchInterval: 60000,
  });

  const announcements = data as WallAnnouncement[] | undefined;

  if (isLoading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">Loading...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-red-400 text-xl">Failed to load announcements</div>
      </div>
    );
  }

  if (!announcements || announcements.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-slate-400 text-xl">No announcements</div>
      </div>
    );
  }

  const pinned = announcements.filter((a) => a.is_pinned);
  const recent = announcements.filter((a) => !a.is_pinned);

  return (
    <div className="h-full overflow-y-auto p-4 space-y-3">
      {pinned.length > 0 && (
        <>
          {pinned.map((a) => (
            <div key={a.id} className="p-4 rounded-xl bg-yellow-500/10 border-2 border-yellow-500/30">
              <p className="text-xl text-white whitespace-pre-wrap">{a.content}</p>
              {a.created_at && (
                <p className="text-slate-500 text-sm mt-2">{formatDate(a.created_at)}</p>
              )}
            </div>
          ))}
        </>
      )}
      {recent.map((a) => (
        <div key={a.id} className="p-4 rounded-xl bg-white/5">
          <p className="text-xl text-white whitespace-pre-wrap">{a.content}</p>
          {a.created_at && (
            <p className="text-slate-500 text-sm mt-2">{formatDate(a.created_at)}</p>
          )}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Frontend build check**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AnnouncementsWallPanel.tsx
git commit -m "feat: add AnnouncementsWallPanel component"
```

## Task 7: Refactor WallDisplay into thin composer

**Files:**
- Modify: `frontend/src/pages/WallDisplay.tsx`

- [ ] **Step 1: Replace entire WallDisplay.tsx**

Replace the entire file with:

```typescript
import { useState, useEffect, useCallback, useRef } from "react";
import api from "../api/client";
import WeatherWidget from "../components/WeatherWidget";
import AnnouncementsWallPanel from "../components/AnnouncementsWallPanel";
import MenuWallPanel from "../components/MenuWallPanel";
import CalendarWallView from "../components/CalendarWallView";
import ChoresWallPanel from "../components/ChoresWallPanel";

interface WallEvent {
  id: string;
  title: string;
  start_time: string;
  end_time: string;
  color_hex?: string;
}

interface WallAnnouncement {
  id: string;
  content: string;
  is_pinned: boolean;
  created_at?: string;
}

export default function WallDisplay() {
  const [events, setEvents] = useState<WallEvent[]>([]);
  const [announcements, setAnnouncements] = useState<WallAnnouncement[]>([]);
  const [isHovered, setIsHovered] = useState(false);
  const timerRef = useRef<number | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const [eventsRes, announcementsRes] = await Promise.all([
        api.get('/events'),
        api.get('/announcements'),
      ]);
      setEvents(eventsRes.data as WallEvent[]);
      setAnnouncements(announcementsRes.data as WallAnnouncement[]);
    } catch (err) {
      console.error("Failed to fetch wall data:", err);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const now = new Date();
  const today = now.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
  const time = now.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });

  return (
    <div
      className="h-screen w-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex flex-col overflow-hidden"
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Top Bar */}
      <header className="bg-[#16213e]/80 backdrop-blur px-8 py-2 flex justify-between items-center flex-shrink-0">
        <h1 className="text-3xl font-bold text-white">OpenFamHub</h1>
        <div className="text-right">
          <p className="text-2xl text-white">{today}</p>
          <p className="text-xl text-slate-400">{time}</p>
        </div>
      </header>

      {/* Top Row: Announcements | Weather | Menu */}
      <div className="h-[25vh] flex flex-shrink-0">
        <div className="flex-1 min-w-0 border-r border-white/10">
          <AnnouncementsWallPanel />
        </div>
        <div className="flex-1 min-w-0 border-r border-white/10 p-3">
          <WeatherWidget mode="wall" />
        </div>
        <div className="flex-1 min-w-0">
          <MenuWallPanel />
        </div>
      </div>

      {/* Bottom Area: Calendar + Chores */}
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 min-w-0 p-6 border-r border-white/10">
          <CalendarWallView events={events} />
        </div>
        <div className="w-[30%] min-w-0 p-6">
          <ChoresWallPanel />
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Frontend build check**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/WallDisplay.tsx
git commit -m "refactor: WallDisplay into thin composer with new panels"
```

## Task 8: Final verification

**Files:**
- None (verification only)

- [ ] **Step 1: Full frontend build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 2: Full backend test suite**

Run: `cd backend && source .venv/bin/activate && pytest`
Expected: 30 passed (19 pre-existing failures in events/meals/rewards — unrelated)

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: verify wall display enhancement" --allow-empty
```
