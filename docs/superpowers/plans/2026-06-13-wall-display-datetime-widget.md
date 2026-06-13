# Wall Display DateTime Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real-time date/time widget to the wall display top-left panel with editable timezone stored per-user.

**Architecture:** New backend router for timezone settings (GET/PUT), stored in `User.settings_json`. Frontend adds `DateTimeWallPanel` component (real-time clock with `Intl.DateTimeFormat`), `TimezonePickerModal` component, and `settingsAPI` client module. Wall display grid changes from 3 to 4 columns. Timezone editable from wall display (admin-only edit icon) and dashboard (weather widget edit modal).

**Tech Stack:** Python/FastAPI, SQLAlchemy async, React/Vite/TypeScript, native `Intl.DateTimeFormat` (no new dependencies)

---

### Task 1: Backend — Timezone Settings Schema

**Files:**
- Create: `backend/app/schemas/settings.py`

- [ ] **Step 1: Create timezone settings schema module**

```python
from pydantic import BaseModel, Field
from typing import Optional


VALID_TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "UTC",
]


class TimezoneSettingsResponse(BaseModel):
    timezone: str = Field(default="UTC")
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/schemas/settings.py
git commit -m "feat: add timezone settings schema"
```

---

### Task 2: Backend — Timezone Settings Router

**Files:**
- Create: `backend/app/routers/settings.py`

- [ ] **Step 1: Create settings router with GET and PUT endpoints**

```python
import json
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_admin
from app.schemas.settings import TimezoneSettingsResponse, VALID_TIMEZONES
from app.models.event import User

router = APIRouter()


@router.get("/timezone", response_model=TimezoneSettingsResponse)
async def get_timezone(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(User).where(User.id == current_user["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    settings = _parse_settings(user.settings_json)
    tz = settings.get("wall_timezone", "UTC") if settings else "UTC"

    return TimezoneSettingsResponse(timezone=tz)


@router.put("/timezone", response_model=TimezoneSettingsResponse)
async def update_timezone(
    req: dict,
    db: AsyncSession = Depends(get_db),
    admin: dict = Depends(require_admin),
):
    timezone = req.get("timezone", "")

    if timezone not in VALID_TIMEZONES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid timezone. Must be one of: {', '.join(VALID_TIMEZONES)}",
        )

    result = await db.execute(select(User).where(User.id == admin["sub"]))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    current_settings = _parse_settings(user.settings_json) or {}
    current_settings["wall_timezone"] = timezone
    user.settings_json = json.dumps(current_settings)

    await db.flush()

    return TimezoneSettingsResponse(timezone=timezone)


def _parse_settings(settings_json_str: str) -> dict | None:
    """Parse settings from user's settings_json string."""
    try:
        return json.loads(settings_json_str)
    except (json.JSONDecodeError, TypeError):
        return None
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/routers/settings.py
git commit -m "feat: add timezone settings API endpoints"
```

---

### Task 3: Backend — Register Settings Router

**Files:**
- Modify: `backend/app/main.py:5`

- [ ] **Step 1: Add settings to imports**

Change line 5 from:
```python
from app.routers import auth, users, events, calendar, announcements, wall, chores, rewards, meals, books, weather
```

To:
```python
from app.routers import auth, users, events, calendar, announcements, wall, chores, rewards, meals, books, weather, settings
```

- [ ] **Step 2: Register the router**

Add after line 36 (after weather router registration):
```python
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: register settings router in main.py"
```

---

### Task 4: Backend — Tests for Timezone Settings

**Files:**
- Create: `backend/tests/test_settings.py`

- [ ] **Step 1: Create test module**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert
from app.core.security import hash_pin
from app.models import User


@pytest.fixture
def test_client():
    return TestClient(app)


def test_get_timezone_default(test_client, db):
    """GET /api/settings/timezone returns UTC when no timezone is set."""
    res = test_client.get("/api/settings/timezone")
    assert res.status_code == 200
    data = res.json()
    assert data["timezone"] == "UTC"


def test_get_timezone_with_settings(test_client, db):
    """GET /api/settings/timezone returns stored timezone."""
    from app.core.security import get_current_user
    # Override to test user
    old_user = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test-user-id", "role": "admin"}

    # Set timezone in settings_json
    result = db.execute(
        __import__('sqlalchemy').text(
            "UPDATE users SET settings_json = :settings WHERE id = :uid"
        ),
        {"settings": '{"wall_timezone": "America/New_York"}', "uid": "test-user-id"},
    )
    db.commit()

    res = test_client.get("/api/settings/timezone")
    assert res.status_code == 200
    data = res.json()
    assert data["timezone"] == "America/New_York"

    # Restore override
    app.dependency_overrides[get_current_user] = old_user


def test_put_timezone_invalid(test_client, db):
    """PUT /api/settings/timezone with invalid timezone returns 422."""
    res = test_client.put("/api/settings/timezone", json={"timezone": "Invalid/Zone"})
    assert res.status_code == 422


def test_put_timezone_valid(test_client, db):
    """PUT /api/settings/timezone with valid timezone updates settings."""
    res = test_client.put("/api/settings/timezone", json={"timezone": "America/Los_Angeles"})
    assert res.status_code == 200
    data = res.json()
    assert data["timezone"] == "America/Los_Angeles"

    # Verify it's persisted
    result = db.execute(
        __import__('sqlalchemy').text("SELECT settings_json FROM users WHERE id = :uid"),
        {"uid": "test-user-id"},
    )
    row = result.fetchone()
    import json
    settings = json.loads(row[0])
    assert settings["wall_timezone"] == "America/Los_Angeles"
```

- [ ] **Step 2: Run tests to verify they pass**

```bash
cd backend && source .venv/bin/activate && pytest tests/test_settings.py -v
```

Expected: All 4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_settings.py
git commit -m "test: add timezone settings endpoint tests"
```

---

### Task 5: Frontend — Settings API Client Module

**Files:**
- Modify: `frontend/src/api/client.ts`

- [ ] **Step 1: Add settingsAPI module**

Add at the end of the file (after the existing API modules):

```typescript
export const settingsAPI = {
  getTimezone: () => api.get('/settings/timezone').then(r => r.data as { timezone: string }),
  updateTimezone: (timezone: string) => api.put('/settings/timezone', { timezone }).then(r => r.data),
};
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/client.ts
git commit -m "feat: add settingsAPI client module for timezone settings"
```

---

### Task 6: Frontend — TimezonePickerModal Component

**Files:**
- Create: `frontend/src/components/TimezonePickerModal.tsx`

- [ ] **Step 1: Create the timezone picker modal component**

```typescript
import { useState } from 'react';

interface TimezoneOption {
  value: string;
  label: string;
}

const TIMEZONE_OPTIONS: TimezoneOption[] = [
  { value: 'America/New_York', label: 'Eastern Time (UTC-5)' },
  { value: 'America/Chicago', label: 'Central Time (UTC-6)' },
  { value: 'America/Denver', label: 'Mountain Time (UTC-7)' },
  { value: 'America/Los_Angeles', label: 'Pacific Time (UTC-8)' },
  { value: 'America/Anchorage', label: 'Alaska Time (UTC-9)' },
  { value: 'Pacific/Honolulu', label: 'Hawaii Time (UTC-10)' },
  { value: 'UTC', label: 'UTC' },
];

interface TimezonePickerModalProps {
  isOpen: boolean;
  onClose: () => void;
  currentTimezone: string;
  onSave: (timezone: string) => void;
  saving?: boolean;
}

export default function TimezonePickerModal({
  isOpen,
  onClose,
  currentTimezone,
  onSave,
  saving = false,
}: TimezonePickerModalProps) {
  const [selected, setSelected] = useState(currentTimezone);

  if (!isOpen) return null;

  const handleSave = () => {
    onSave(selected);
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl p-6 w-full max-w-md border border-slate-700">
        <h3 className="text-xl font-bold text-white mb-4">Wall Display Timezone</h3>

        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Timezone</label>
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-white"
            >
              {TIMEZONE_OPTIONS.map((tz) => (
                <option key={tz.value} value={tz.value}>
                  {tz.label}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-3 justify-end">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-lg bg-white/5 border border-white/20 text-gray-400 hover:text-white transition"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/TimezonePickerModal.tsx
git commit -m "feat: add TimezonePickerModal component"
```

---

### Task 7: Frontend — DateTimeWallPanel Component

**Files:**
- Create: `frontend/src/components/DateTimeWallPanel.tsx`

- [ ] **Step 1: Create the date/time wall panel component**

```typescript
import { useState, useEffect, useCallback, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { settingsAPI } from '../api/client';
import { useAuthStore } from '../stores/auth';
import TimezonePickerModal from './TimezonePickerModal';

interface DateTimeData {
  dateStr: string;
  timeStr: string;
  timezone: string;
}

export default function DateTimeWallPanel() {
  const currentUser = useAuthStore((s) => s.user);
  const isAdmin = currentUser?.role === 'admin';
  const [showTimezoneModal, setShowTimezoneModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [currentTime, setCurrentTime] = useState<Date>(new Date());
  const intervalRef = useRef<number | null>(null);

  const { data: timezoneData, isLoading } = useQuery({
    queryKey: ['wall-timezone'],
    queryFn: () => settingsAPI.getTimezone(),
    staleTime: Infinity,
  });

  const timezone = timezoneData?.timezone || 'UTC';

  // Update clock every second
  const updateClock = useCallback(() => {
    setCurrentTime(new Date());
  }, []);

  useEffect(() => {
    intervalRef.current = window.setInterval(updateClock, 1000);
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [updateClock]);

  // Format date/time using Intl.DateTimeFormat
  const formatDateTime = useCallback((date: Date, tz: string): DateTimeData => {
    const dateOptions: Intl.DateTimeFormatOptions = {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      timeZone: tz,
    };

    const timeOptions: Intl.DateTimeFormatOptions = {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
      timeZone: tz,
    };

    const tzOptions: Intl.DateTimeFormatOptions = {
      timeZoneName: 'short',
      timeZone: tz,
    };

    const dateStr = new Intl.DateTimeFormat('en-US', dateOptions).format(date);
    const timeStr = new Intl.DateTimeFormat('en-US', timeOptions).format(date);
    const tzAbbr = new Intl.DateTimeFormat('en-US', tzOptions).format(date);

    return { dateStr, timeStr, timezone: tzAbbr };
  }, []);

  const { dateStr, timeStr, timezone: tzAbbr } = formatDateTime(currentTime, timezone);

  const handleSaveTimezone = async (newTimezone: string) => {
    setSaving(true);
    try {
      await settingsAPI.updateTimezone(newTimezone);
      setShowTimezoneModal(false);
    } catch {
      alert('Failed to update timezone');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="bg-slate-800/50 backdrop-blur rounded-xl p-4 border border-slate-700 h-full flex flex-col justify-center relative">
      {isLoading ? (
        <div className="text-slate-400 text-xl">Loading...</div>
      ) : (
        <>
          <div className="text-xl font-semibold text-white">{dateStr}</div>
          <div className="text-3xl font-bold text-white mt-1">
            {timeStr} <span className="text-slate-400 text-lg">{tzAbbr}</span>
          </div>
          {isAdmin && (
            <button
              onClick={() => setShowTimezoneModal(true)}
              className="absolute top-2 right-2 text-slate-500 hover:text-white transition text-lg"
              title="Edit timezone"
            >
              ⚙
            </button>
          )}
        </>
      )}

      <TimezonePickerModal
        isOpen={showTimezoneModal}
        onClose={() => setShowTimezoneModal(false)}
        currentTimezone={timezone}
        onSave={handleSaveTimezone}
        saving={saving}
      />
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/DateTimeWallPanel.tsx
git commit -m "feat: add DateTimeWallPanel component for wall display"
```

---

### Task 8: Frontend — Update WallDisplay Grid Layout

**Files:**
- Modify: `frontend/src/pages/WallDisplay.tsx`

- [ ] **Step 1: Add DateTimeWallPanel import**

Add after existing imports (around line 8):
```typescript
import DateTimeWallPanel from '../components/DateTimeWallPanel';
```

- [ ] **Step 2: Update grid mode layout — change from 3 to 4 columns**

Change the top row grid from:
```jsx
<div className="h-[25vh] grid grid-cols-3 gap-2 p-2">
  <div className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
    <AnnouncementsWallPanel />
  </div>
  <div className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
    <WeatherWidget mode="wall" />
  </div>
  <div className="rounded-xl bg-white/5 border border-white/10 overflow-hidden">
    <MenuWallPanel />
  </div>
</div>
```

To:
```jsx
<div className="h-[25vh] grid grid-cols-4 gap-2 p-2">
  <div className="col-span-1 rounded-xl bg-white/5 border border-white/10 overflow-hidden">
    <DateTimeWallPanel />
  </div>
  <div className="col-span-1 rounded-xl bg-white/5 border border-white/10 overflow-hidden">
    <AnnouncementsWallPanel />
  </div>
  <div className="col-span-1 rounded-xl bg-white/5 border border-white/10 overflow-hidden">
    <WeatherWidget mode="wall" />
  </div>
  <div className="col-span-1 rounded-xl bg-white/5 border border-white/10 overflow-hidden">
    <MenuWallPanel />
  </div>
</div>
```

- [ ] **Step 3: Add to cycling panels**

Add `'datetime'` panel type to the `cyclingPanels` array:
```typescript
const cyclingPanels = [
  { type: 'calendar' as const, title: "Today's Schedule" },
  { type: 'chores' as const, title: 'Family Chores' },
  { type: 'announcements' as const, title: 'Announcements' },
  { type: 'weather' as const, title: 'Weather' },
  { type: 'menu' as const, title: "Today's Menu" },
  { type: 'datetime' as const, title: 'Date & Time' },
];
```

- [ ] **Step 4: Add datetime panel case in renderPanelContent**

Add to the `switch` statement in `renderPanelContent`:
```typescript
case 'datetime':
  return <DateTimeWallPanel />;
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/WallDisplay.tsx
git commit -m "feat: add DateTimeWallPanel to wall display grid and cycling mode"
```

---

### Task 9: Frontend — Add Timezone to Weather Widget Edit Modal

**Files:**
- Modify: `frontend/src/components/WeatherWidget.tsx`

- [ ] **Step 1: Add settingsAPI import**

Add to existing imports:
```typescript
import { settingsAPI } from "../api/client";
```

- [ ] **Step 2: Add timezone state variables**

Add after existing state declarations (around line 32):
```typescript
  const [editTimezone, setEditTimezone] = useState("UTC");
  const [loadingTimezone, setLoadingTimezone] = useState(false);
```

- [ ] **Step 3: Add timezone loading in `handleOpenEdit`**

Modify `handleOpenEdit` to also load timezone:
```typescript
  const handleOpenEdit = async () => {
    if (weather?.settings) {
      setEditLat(weather.settings.lat.toString());
      setEditLon(weather.settings.lon.toString());
      setEditLocation(weather.settings.location_name || "");
    }
    try {
      const tzData = await settingsAPI.getTimezone();
      setEditTimezone(tzData.timezone || "UTC");
    } catch {
      setEditTimezone("UTC");
    }
    setShowEditModal(true);
  };
```

- [ ] **Step 4: Add timezone save function**

Add after `handleSave`:
```typescript
  const handleSaveTimezone = async () => {
    setLoadingTimezone(true);
    try {
      await settingsAPI.updateTimezone(editTimezone);
      await queryClient.invalidateQueries({ queryKey: ["weather"] });
    } catch {
      alert("Failed to update timezone");
    } finally {
      setLoadingTimezone(false);
    }
  };
```

- [ ] **Step 5: Add timezone section to edit modal**

Add the timezone section inside the edit modal, after the location save button and before the close button. Find the existing modal content ending with the save button and add:

```jsx
            <div className="border-t border-slate-700 pt-4 mt-4">
              <h4 className="text-sm font-semibold text-slate-300 mb-2">
                Wall Display Timezone (affects wall board clock)
              </h4>
              <select
                value={editTimezone}
                onChange={(e) => setEditTimezone(e.target.value)}
                className="w-full p-3 rounded-lg bg-white/5 border border-white/20 focus:border-white/50 focus:outline-none text-white"
              >
                <option value="America/New_York">Eastern Time (UTC-5)</option>
                <option value="America/Chicago">Central Time (UTC-6)</option>
                <option value="America/Denver">Mountain Time (UTC-7)</option>
                <option value="America/Los_Angeles">Pacific Time (UTC-8)</option>
                <option value="America/Anchorage">Alaska Time (UTC-9)</option>
                <option value="Pacific/Honolulu">Hawaii Time (UTC-10)</option>
                <option value="UTC">UTC</option>
              </select>
              <button
                onClick={handleSaveTimezone}
                disabled={loadingTimezone}
                className="mt-2 w-full px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white disabled:opacity-50 text-sm"
              >
                {loadingTimezone ? 'Saving...' : 'Save Timezone'}
              </button>
            </div>
```

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/WeatherWidget.tsx
git commit -m "feat: add timezone editing to weather widget edit modal"
```

---

### Task 10: Frontend — Build Verification

- [ ] **Step 1: Run frontend build**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no errors.

- [ ] **Step 2: Commit any build artifacts if needed**

```bash
git add -A
git commit -m "chore: verify frontend build for datetime widget"
```

---

### Task 11: Backend — Full Test Suite

- [ ] **Step 1: Run full backend test suite**

```bash
cd backend && source .venv/bin/activate && pytest
```

Expected: All 63 tests pass (59 original + 4 new settings tests).

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "test: verify full test suite passes"
```

---

### Task 12: Git — Commit and Push

- [ ] **Step 1: Final commit and push**

```bash
git add -A
git commit -m "feat: add wall display date/time widget with editable timezone"
git push origin main
```

---

## Plan Self-Review

### Spec Coverage
- ✅ DateTimeWallPanel component with real-time clock (`MMM DD, YYYY — h:mm AM TZ` format)
- ✅ TimezonePickerModal component
- ✅ Backend GET /api/settings/timezone (any user)
- ✅ Backend PUT /api/settings/timezone (admin only)
- ✅ Settings stored in `User.settings_json.wall_timezone`
- ✅ Wall display grid: 3 columns → 4 columns
- ✅ Cycling mode: adds datetime panel
- ✅ Dashboard edit via weather widget modal
- ✅ Admin-only edit icon on wall display
- ✅ Default timezone: UTC
- ✅ Valid timezone list with IANA identifiers

### Placeholder Scan
- No "TBD", "TODO", "implement later", or vague requirements found.
- All code is complete and copy-paste ready.

### Type Consistency
- `settingsAPI.getTimezone()` returns `{ timezone: string }` — matches `TimezoneSettingsResponse`
- `settingsAPI.updateTimezone(timezone: string)` sends `{ timezone }` — matches backend `req.get("timezone")`
- `TimezonePickerModal` props: `isOpen`, `onClose`, `currentTimezone`, `onSave`, `saving` — consistent usage
- `DateTimeWallPanel` uses `settingsAPI` consistently

### Scope Check
- Focused on single feature: datetime widget + timezone settings
- No decomposition needed
