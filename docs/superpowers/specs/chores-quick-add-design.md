# Chores Quick-Add Feature Design

## Overview
Add ability for any logged-in user to quickly create a chore template with an assigned instance, appearing immediately in the assignee's todo list.

## Frontend Changes

### ChoresPage.tsx
- Add "Quick Add" button in page header (visible to all logged-in users)
- Modal form with fields:
  - Title (required, text input)
  - Description (optional, textarea)
  - Point value (default 10, number input, min 1)
  - Assign to (required, user dropdown)
  - Recurrence rule (optional dropdown: none/daily/weekly_mon/weekly_tue/etc./every_X_days/monthly_X)
- Submit button disabled while loading
- On success: invalidate `chores-instances` and `chores-stats` queries, close modal, show success toast, reset form
- On error: show error message in modal

### client.ts
- Add `choreAPI.quickAdd` method:
  - `POST /chores/quick-add` with body `{ title, description?, point_value, assigned_to_id, recurrence_rule }`

## Backend Changes

### schemas/models.py
- Add `ChoreQuickAdd` schema:
  - `title: str` (required, 1-200 chars)
  - `description: Optional[str]` (optional)
  - `point_value: int` (default 10, 1-1000)
  - `assigned_to_id: str` (required)
  - `recurrence_rule: str` (optional, default "none")

### routers/chores.py
- Add `POST /chores/quick-add` endpoint:
  - Auth: `get_current_user` (any logged-in user)
  - Logic:
    1. Validate `assigned_to_id` exists (query User model)
    2. Create `Chore` template with `assignment_mode="assigned"`, `recurrence_rule` as provided, `default_assigned_to_id` = selected user, `created_by_id` = current user
    3. If `recurrence_rule == "none"`: create 1 instance due today
    4. If recurrence set: use existing `_parse_recurrence_rule` and create instances for each date (limit to 7 days from today)
    5. All instances: `assigned_to_id` = selected user, `status = "pending"`
  - Response: `{ template: ChoreResponse, instances: [ChoreInstanceResponse] }`
  - Error handling:
    - 400 if title missing/empty
    - 404 if `assigned_to_id` not found
    - 400 if invalid recurrence format

## Error Handling
- Frontend: React Query `onError` on mutation shows error in modal
- Backend: Validation errors return 400/404 with descriptive message
- Loading state: button shows spinner during submission
