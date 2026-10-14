# Wall Dashboard Configuration Spec

## Goal

Complete Phase 10's wall-panel TODO by making the wall display use a configurable, dashboard-style layout owned by the whole family.

## User decisions

- The wall should have “the dashboard look”.
- The wall look should be configurable, not hard-coded.
- Any signed-in family user may configure it.
- The configuration is shared by the whole family, not per wall display and not per user.
- The paired wall itself remains read-only and displays the saved family configuration through its wall-device cookie.

## Product behavior

- Store a family-wide wall dashboard configuration in existing family settings JSON.
- The configuration controls wall pages, card order, and normal/wide card size.
- Provide safe defaults when no configuration is saved.
- Allow every signed-in user role to read and save the wall dashboard configuration.
- Publish a wall settings update when the configuration changes, so paired wall displays refresh.
- Paired wall displays read their layout from `/api/wall/session` and render the dashboard-style pages.
- Paired wall displays may read wall-only data endpoints with the wall cookie; no family-member login is required on the wall.
- Wall data endpoints are read-only and family-scoped through the paired `WallDevice`.

## Wall cards

Supported wall dashboard card keys:

- `events`: calendar events for today.
- `chores`: non-routine chores due today.
- `routines`: today's routines and current step countdown.
- `meals`: today's meals.
- `weather`: current weather / forecast.
- `announcements`: recent/pinned announcements.
- `progress`: family points/progress and upcoming birthdays.
- `birthdays`: upcoming birthdays.

## Constraints

- Do not let the wall cookie mutate chores, meals, announcements, weather settings, or family settings.
- Do not require an admin session for wall dashboard configuration; any authenticated family user can edit it.
- Reuse existing family timezone, date, dashboard, weather, routines, rewards, announcements, meals, and chores services where possible.
- Keep wall sleep and idle behavior higher priority than the dashboard renderer.
