# Wall Display DateTime Widget — Design Spec

**Date**: 2026-06-13
**Status**: Approved

## Overview

Add a real-time date/time widget to the wall display top-left panel, replacing the announcements panel in grid mode. Timezone is stored per-user in `settings_json` and editable from both the wall display (admin) and dashboard (weather widget edit modal).

## Format

Compact format: `Jun 13, 2026 — 3:45 PM EDT`

- Date: `MMM DD, YYYY` (e.g., "Jun 13, 2026")
- Separator: em dash `—`
- Time: 12-hour format with AM/PM (e.g., "3:45 PM")
- Timezone: abbreviation (e.g., "EDT", "PST", "UTC")

## Architecture

### Components

**`DateTimeWallPanel`** (new — `frontend/src/components/DateTimeWallPanel.tsx`)
- Purpose: Display real-time date/time in user's timezone on wall display
- Props: none (reads timezone from settings API)
- Updates every second via `setInterval`
- Uses `Intl.DateTimeFormat` with IANA timezone string
- Admin-only edit icon (⚙) in top-right corner — opens timezone picker modal
- Default timezone: `UTC` if not set

**`TimezonePickerModal`** (new — `frontend/src/components/TimezonePickerModal.tsx`)
- Purpose: Select wall display timezone
- Props: `isOpen`, `onClose`, `currentTimezone`, `onSave`
- Dropdown of common IANA timezones with display labels
- Saves via `PUT /api/settings/timezone`
- Reused from both wall display (admin edit icon) and weather widget modal

### Backend API

**`GET /api/settings/timezone`** (`backend/app/routers/settings.py`)
- Auth: `get_current_user`
- Returns: `{ "timezone": "America/New_York" }`
- Reads `settings_json.wall_timezone` from User model
- Returns `"UTC"` if not set

**`PUT /api/settings/timezone`** (same file)
- Auth: `require_admin`
- Body: `{ "timezone": "America/New_York" }`
- Validates timezone is a valid IANA identifier
- Writes to `settings_json.wall_timezone`
- Returns updated settings

**`backend/app/routers/settings.py`** (new file)
- New router module for wall display settings
- Registered in `main.py` under `/api/settings` prefix
- Follows weather router pattern for `settings_json` access

### Frontend API Client

**`settingsAPI`** (new — in `frontend/src/api/client.ts`)
- `getTimezone()` → `GET /api/settings/timezone`
- `updateTimezone(timezone: string)` → `PUT /api/settings/timezone`

### Data Storage

- Timezone stored in `User.settings_json` under key `wall_timezone`
- Example: `{"wall_timezone": "America/New_York"}`
- Same pattern as weather settings (`weather_lat`, `weather_lon`, `weather_location_name`)
- No new database columns — reuses existing `settings_json` Text column

### Wall Display Layout

**Grid mode** (top row, 25vh):
```
┌─────────────┬──────────────────┬──────────────────┬──────────────────┐
│  Date/Time  │  Announcements   │     Weather      │    Today's Menu  │
│  (col-span) │    (col-span)    │    (col-span)    │    (col-span)    │
└─────────────┴──────────────────┴──────────────────┴──────────────────┘
```
- Grid changes from `grid-cols-3` to `grid-cols-4`
- Each panel gets equal width (`col-span` computed from 12/4 = 3)

**Cycling mode**: 6 panels cycle (was 5):
1. Calendar
2. Chores
3. Announcements
4. Weather
5. Menu
6. **Date/Time** (new)

### Dashboard Integration

**Weather Widget Edit Modal** (`frontend/src/components/WeatherWidget.tsx`):
- New section below location settings: "Wall Display Timezone"
- Dropdown with timezone options
- Label: "Wall Display Timezone (affects wall board clock)"
- Saves to same `PUT /api/settings/timezone` endpoint

### Timezone Options

Common timezones with display labels:
| IANA Identifier | Display Label |
|---|---|
| America/New_York | Eastern Time (UTC-5) |
| America/Chicago | Central Time (UTC-6) |
| America/Denver | Mountain Time (UTC-7) |
| America/Los_Angeles | Pacific Time (UTC-8) |
| America/Anchorage | Alaska Time (UTC-9) |
| Pacific/Honolulu | Hawaii Time (UTC-10) |
| UTC | UTC |

### Error Handling

- Invalid timezone on PUT: return 422 with error message
- API failure on widget load: display `UTC` as fallback
- Wall display edit icon: show toast/alert on save failure

### Testing

- **Backend**: Test timezone GET/PUT endpoints in `tests/test_settings.py`
- **Frontend**: No unit tests (UI component), verified via manual testing

## Files Changed/Created

| File | Action | Purpose |
|---|---|---|
| `backend/app/routers/settings.py` | **New** | Timezone settings API endpoints |
| `frontend/src/components/DateTimeWallPanel.tsx` | **New** | Date/time display widget |
| `frontend/src/components/TimezonePickerModal.tsx` | **New** | Timezone picker modal |
| `frontend/src/api/client.ts` | **Modified** | Add `settingsAPI` module |
| `frontend/src/pages/WallDisplay.tsx` | **Modified** | Add DateTimeWallPanel to grid, add to cycling panels |

## Decisions

1. **Native `Intl.DateTimeFormat`** over date library — no new dependencies, handles DST automatically
2. **4-column grid** instead of replacing announcements — keeps all panels visible; announcements still in cycling mode
3. **Weather modal for dashboard edit** — reuses existing edit modal pattern, groups settings together
4. **Admin-only wall edit** — wall display is shared; timezone is a system-level setting
5. **IANA timezone identifiers** — handles DST transitions automatically, standard format
