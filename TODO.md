# OpenFamHub — TODO

Known bugs and planned fixes, from the code review of 2026-10-04. Phase 1 shipped in v0.18.

## Phase 2 — Security
- [ ] Enforce roles on events. Viewers are read-only. Members edit their own and internal events. Admins can edit everything. Synced iCal events are read-only. Scope `PATCH /calendar/events` by family.
- [ ] Rate-limit password login. Block deleted users at login. Make display names unique (case-insensitive) with a clear error.
- [ ] Remove `POST /users/switch`. It mints a token for any user ID and nothing uses it.
- [ ] Server-side session revocation using the `sessions` table and a `jti` claim, so logout, password changes and user deletion revoke tokens.
- [ ] Optional: authenticate the `/api/ws/wall` WebSocket.
- [ ] Fix the remaining react-hooks lint error in `ManageUsers.tsx`.

## Phase 3 — iCal correctness
- [ ] Don't duplicate the first occurrence of recurring events.
- [ ] Honor EXDATE and RECURRENCE-ID (cancelled or moved instances).
- [ ] Keep `all_day` on expanded recurrences.
- [ ] Store a window only (about 90 days back to 365 days ahead) instead of full history.
- [ ] Look up existing UIDs in one batch query per sync.

## Phase 4 — Infra and cleanup
- [ ] Run Alembic migrations on container start instead of `create_all`.
- [ ] CI: set `SECRET_KEY` for tests; add a frontend lint + build job; move to Forgejo Actions once a runner exists.
- [ ] Fix the Workbox `runtimeCaching` URL patterns (they're matched against the full URL, so they never match).
- [ ] `setup-wall-pi.sh`: make it idempotent and Bookworm-compatible (`chromium`, labwc/Wayland autostart).
- [ ] Remove dead code and placeholders: `notifications.py`, the `/lists` nav link, the `co_admin` role checks, and `/admin/settings` rendering the Dashboard.
- [ ] Deduplicate the event response builders and the user validators.
- [ ] Read `WALL_IDLE_TIMEOUT_SECONDS` and `FAMILY_NAME` from settings, or drop them.
- [ ] Add tests for users and permissions.
- [ ] Update `release_checklist.json` and the sprint manifests, or archive them.

## Completed
- [x] v0.18: the Phase 1 fixes (routing, login errors, time zones, range queries, Sync Now, source delete, source filter, wall pairing, deploy script). See CHANGELOG.
