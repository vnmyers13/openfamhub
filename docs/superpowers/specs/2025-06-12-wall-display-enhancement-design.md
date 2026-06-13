# Wall Display Enhancement Design

## Overview

Enhance the wall display to show shared chores and today's menu in addition to the existing schedule and announcements. The wall display is a full-screen kiosk view accessed at `/wall`.

## Layout

```
┌─────────────────────────────────────────────────────────┐
│  Announcements  │   Weather   │   Today's Menu    │ Time│
├─────────────────────────────────────────────────────────┤
│                                                 │       │
│                                                 │  Ch   │
│                                                 │ o   │
│                  Today's Schedule               │ r   │
│                                                 │ e   │
│                                                 │ s     │
│                                                 │   │   │
└─────────────────────────────────────────────────┴───────┘
```

- Top row: 25% viewport height, 3 equal columns (announcements, weather, menu)
- Bottom area: 75% viewport height, split 70/30 between calendar and chores
- Existing header with OpenFamHub title and date/time remains at top

## Architecture

```
WallDisplay.tsx (thin composer, ~100 lines)
├── TopBar (header + time)
├── TopRow (1/4 height, 3 columns)
│   ├── AnnouncementsWallPanel (scrollable list)
│   ├── WeatherWidget (existing, mode="wall")
│   └── MenuWallPanel (today's meals with recipe titles)
└── BottomArea (3/4 height)
    ├── CalendarWallView (agenda/daily/weekly/monthly)
    └── ChoresWallPanel (pending+completed today, view toggle)
```

## Components

### TopBar
- Existing header with "OpenFamHub" title and date/time display
- No changes required

### TopRow
- Flex row, 3 equal columns, `h-[25vh]`
- Each column is scrollable if content overflows

#### AnnouncementsWallPanel
- Shows all announcements (pinned first, then recent)
- Reuses existing announcement card styling from WallDisplay
- Pinned announcements have yellow border highlight
- Scrollable container

#### WeatherWidget
- Existing component from `../components/WeatherWidget`
- Passed `mode="wall"` (unchanged from current implementation)

#### MenuWallPanel
- Shows today's meals only (breakfast, lunch, dinner)
- Each meal entry displays:
  - Meal type label (BREAKFAST, LUNCH, DINNER) in uppercase
  - Recipe title if available, otherwise custom title
  - Notes if present (smaller text below title)
- Empty state: "No meals planned for today"

### CalendarWallView
- 4 view modes with toggle buttons in panel header:
  - **Agenda**: List of today's events with time + title
  - **Daily**: Today's events in time-slot layout (vertical timeline)
  - **Weekly**: 7-day grid showing events per day
  - **Monthly**: Full month grid with event indicators (dots or small bars)
- Toggle buttons: small pill-style buttons, active state highlighted
- Each view manages its own empty state

### ChoresWallPanel
- 2 view modes with toggle buttons in panel header:
  - **Pending + Completed**: Shows pending/claimed chores + chores completed today, with status badges (badge colors: pending=yellow, claimed=blue, completed=green)
  - **Pending Only**: Shows only pending/claimed chores
- Each chore entry displays:
  - Chore title
  - Assignee name (if assigned)
  - Status badge
  - Due date
- Empty state: "No chores for today"

## Data Flow

### Fetch
WallDisplay fetches 4 data sources on mount and every 60 seconds:
- `GET /events` → all events (existing)
- `GET /announcements` → all announcements (existing)
- `GET /chores/instances` → all chore instances (new)
- `GET /meals/plans?week_start=<today's monday>` → weekly meal plans (new)

### Client-side Filtering
- **Menu**: Filter meal plans where `date === today (YYYY-MM-DD)`
- **Chores**: 
  - Pending: `due_date === today` AND status in (pending, claimed)
  - Completed: `completed_at` falls on today

### Data Interfaces

```typescript
interface WallMeal {
  meal_type: string;
  date: string;
  title?: string;
  recipe?: { id: string; title: string } | null;
  notes?: string;
}

interface WallChore {
  id: string;
  title: string;
  assigned_to_name?: string;
  status: string;
  due_date: string;
  completed_at?: string;
}
```

## Error Handling

- Each panel handles its own empty state with descriptive message
- Fetch errors logged to console; panels show "Failed to load" placeholder
- Panels render independently — one failure does not block others
- Retry on next 60-second refresh interval

## Styling

- All existing dark theme styling preserved (`bg-[#16213e]`, `text-white`, `text-slate-400`)
- Top row columns: equal width flex items, scrollable overflow
- Bottom area: flex row, calendar ~70%, chores ~30%
- Toggle buttons: pill-style (`rounded-full`), active state with blue background
- Card styling consistent with existing WallDisplay patterns
- Font sizes scaled for wall display readability (text-xl minimum for content)

## Files Modified

- `frontend/src/pages/WallDisplay.tsx` — Refactored into thin composer

## Files Created

- `frontend/src/components/AnnouncementsWallPanel.tsx`
- `frontend/src/components/MenuWallPanel.tsx`
- `frontend/src/components/CalendarWallView.tsx`
- `frontend/src/components/ChoresWallPanel.tsx`

## Existing Files Unchanged

- `frontend/src/components/WeatherWidget.tsx` — Used as-is with `mode="wall"`
- `frontend/src/api/client.ts` — No changes needed (existing endpoints)
- Backend — No changes needed
