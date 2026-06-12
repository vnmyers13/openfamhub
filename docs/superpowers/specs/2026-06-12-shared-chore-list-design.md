# Shared Chore List - Admin Dashboard

**Date:** 2026-06-12
**Status:** Approved

## Overview

Add an Admin tab to the existing ChoresPage that shows all chore instances across all family members in a sortable table with status and date filtering.

## Decisions

- Admin tab added to existing ChoresPage (not a new page) — data already fetched, tab infrastructure exists
- Table view with columns: Title, Assigned To, Status, Due Date, Completed Date
- Filters: Status dropdown (All/Pending/Claimed/Completed), Date range picker
- Sortable by any column
- Admin-only via `require_admin` dependency
- Future enhancement: Weather widget on Dashboard (separate feature)

## Architecture

### Backend
- New endpoint: `GET /api/chores/admin/instances` in `backend/app/routers/chores.py`
- Query params: `status` (optional), `start_date` (optional), `end_date` (optional)
- Returns: List of chore instances with user info (assigned user name, completed user name)
- Filtered by `require_admin` dependency

### Frontend
- Add "Admin" tab to ChoresPage.tsx
- Filter bar: Status dropdown + Date range inputs
- Table component with sortable headers
- Uses existing `choreAPI` module, adds `getAdminInstances()` method
- Reuses existing chore instance data structure

### Data Flow
1. Admin navigates to ChoresPage → Admin tab
2. Frontend calls `GET /api/chores/admin/instances?status=&start_date=&end_date=`
3. Backend queries ChoreInstance with filters, joins User for names
4. Frontend renders table with filters and sortable columns

## Components

### Backend: Admin Instances Endpoint
```
GET /api/chores/admin/instances
Query params:
  - status: Optional[str] = None  # pending/claimed/completed
  - start_date: Optional[str] = None  # ISO format
  - end_date: Optional[str] = None  # ISO format
Response: list[ChoreInstanceAdminResponse]
  - id, chore_template_id, title (from template), assigned_to_id, assigned_to_name
  - due_date, status, claimed_by_id, claimed_at, completed_by_id, completed_at
  - point_value
```

### Frontend: Admin Tab
- Filter bar with:
  - Status dropdown: All / Pending / Claimed / Completed
  - Date range: From/To date inputs
- Table with columns:
  - Title (clickable to expand details)
  - Assigned To (user name)
  - Status (colored badge)
  - Due Date
  - Completed Date
- Sortable by clicking column headers

## Testing
- Backend: Test admin endpoint with admin user (200), non-admin user (403)
- Backend: Test filtering by status and date range
- Frontend: Tab renders correctly, filters work, table displays data

## Future Enhancements
- Weather widget on Dashboard (separate feature)
