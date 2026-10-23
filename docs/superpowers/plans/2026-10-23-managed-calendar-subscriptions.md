# Managed Calendar Subscriptions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the complete OpenFamHub family calendar through a managed relay as independently revocable title-only and full-details ICS subscriptions.

**Architecture:** OpenFamHub remains the source of truth and performs only outbound authenticated delivery to a configured relay. A calendar-subscriptions service selects eligible normalized event rows and serializes the two privacy variants; a durable subscription model records opaque relay URLs, delivery status, and pending publication. The scheduler retries dirty subscriptions after database commits, while the admin UI controls creation, reveal, rotation, and revocation.

**Tech Stack:** FastAPI, SQLAlchemy async + Alembic, `icalendar`, httpx, APScheduler, React, TanStack Query, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-10-23-managed-calendar-subscriptions-design.md`

## Global Constraints

- OpenFamHub is the source of truth; subscriptions are read-only, standard HTTPS ICS feeds.
- Include every active, non-deleted stored event from the internal calendar and enabled non-deleted iCal sources; do not refetch source URLs or export source URLs.
- Publish two independently revocable feeds: `titles` omits details; `full` includes title, description, location, URL, organizer, and attendees.
- Timed events serialize in UTC; all-day events use `VALUE=DATE` with exclusive date-only `DTEND`.
- Feed URLs are bearer secrets, encrypted at rest, revealable only by an unlocked admin, absent from logs/browser storage, and audited on creation, reveal, rotation, and revocation.
- Relay configuration and its credential are server-only, encrypted where database-backed, bounded by timeouts, and never user-controlled URLs.
- Relay publication occurs only after the local transaction commits; failures never roll back local calendar changes, are retried idempotently, and are visible to an admin.
- Do not implement provider writes, OAuth, CalDAV, conflict resolution, or provider-specific UI.

## Review Focus

- A disabled/deleted source or soft-deleted event must disappear from both feeds on the next published snapshot; test in Task 3.
- An all-day multi-day event must not shift a day or add an inclusive final day; test in Task 3.
- Titles feeds must never contain description, location, URL, organizer, or attendees, including empty or escaped fields; test in Task 3.
- A relay failure after an event edit must leave the local edit committed and schedule retry rather than publish an uncommitted or partial snapshot; test in Task 4.
- Revealing, rotating, or revoking one feed must neither reveal nor invalidate the other feed; test in Task 5.

---

## Provider Decision Gate

The selected managed relay is an OpenFamHub-controlled **Cloudflare Worker
with SQLite-backed Durable Object storage**. Before Task 1's production
configuration, review and accept Cloudflare's current DPA, privacy policy,
subprocessor/retention terms, incident process, and Worker/Durable Object
data-location configuration. Record the Worker endpoint/authentication
contract in the implementation PR description. Do not use Workers KV for feed
state or revocation because it is eventually consistent; Durable Object storage
is required for immediate rotation/revocation semantics.

The application-facing interface below deliberately keeps the vendor implementation in one module; only that module may know provider endpoint paths or authentication headers.

## File Structure

| File | Responsibility |
|---|---|
| `relay/src/index.ts` | Cloudflare Worker routes for authenticated snapshot replacement and opaque public ICS reads. |
| `relay/wrangler.jsonc` | SQLite-backed Durable Object binding and migration; never a Workers KV binding. |
| `relay/src/index.test.ts` | Worker protocol tests using Cloudflare's Worker test pool. |
| `backend/app/models/calendar_subscription.py` | Persist each privacy variant's encrypted relay URL, relay ID, lifecycle, and delivery state. |
| `backend/alembic/versions/*_calendar_subscriptions.py` | Create the subscription table and its family/kind uniqueness constraint. |
| `backend/app/services/calendar_subscriptions.py` | Query eligible events, serialize title/full ICS documents, and coordinate delivery state. |
| `backend/app/integrations/calendar_relay.py` | Cloudflare Worker async relay client and normalized errors. |
| `backend/app/jobs/calendar_subscriptions.py` | Retry pending/failed snapshots through the existing single scheduler. |
| `backend/app/routers/calendar_subscriptions.py` | Password-gated subscription management API. |
| `backend/app/schemas/calendar_subscription.py` | API request/response models that never accidentally expose a URL. |
| `frontend/src/api/calendarSubscriptions.ts` | Types and React Query hooks for management operations. |
| `frontend/src/pages/admin/CalendarSubscriptions.tsx` | Admin-only subscription lifecycle UI. |
| `frontend/src/pages/admin/CalendarSubscriptions.test.tsx` | UI behaviour and URL-secret handling tests. |
| `backend/tests/test_calendar_subscriptions.py` | Serializer, authorization, lifecycle, and publication integration tests. |

### Task 1: Relay configuration and isolated client

**Files:**
- Create: `relay/package.json`
- Create: `relay/tsconfig.json`
- Create: `relay/vitest.config.ts`
- Create: `relay/wrangler.jsonc`
- Create: `relay/src/index.ts`
- Create: `relay/src/index.test.ts`
- Modify: `backend/app/core/config.py:39-69`
- Modify: `backend/app/services/server_config.py:40-115, 255-266`
- Modify: `backend/app/routers/server_settings.py:22-76`
- Create: `backend/app/integrations/calendar_relay.py`
- Modify: `backend/tests/test_server_settings.py`
- Create: `backend/tests/test_calendar_relay.py`
- Modify: `frontend/src/pages/admin/FamilySettings.tsx:10-116`
- Modify: `frontend/src/pages/admin/ServerSettingsForm.tsx:23-34`
- Modify: `frontend/src/api/serverSettings.ts:33-35`
- Modify: `frontend/src/pages/admin/ServerSettings.test.tsx`

**Interfaces:**
- Produces: the Cloudflare Worker protocol: `POST /v1/feeds` creates a feed from JSON `{kind, ics}` and returns `{relay_id, subscription_url}`; `PUT /v1/feeds/{relay_id}` atomically replaces its complete ICS document from JSON `{ics}`; `DELETE /v1/feeds/{relay_id}` revokes it; all `/v1/*` routes require a constant-time `Authorization: Bearer <RELAY_API_TOKEN>` comparison. `GET /c/{opaque-token}.ics` returns only an active document as `text/calendar; charset=utf-8`, otherwise 404.
- Produces: one SQLite-backed Durable Object that owns the token→feed mapping and document replacement/revocation transaction. The Worker never logs a token or ICS body, never accepts caller-selected public URLs, and uses `Cache-Control: no-store` on public feeds so a CDN cannot extend a revoked feed's lifetime.
- Produces: `calendar_relay.configured() -> bool`, `calendar_relay.create_feed(kind: Literal["titles", "full"], ics: bytes) -> RelayFeed`, `replace_feed(relay_id: str, ics: bytes) -> None`, and `revoke_feed(relay_id: str) -> None`, using exactly the Worker protocol above.
- Produces: `RelayFeed(relay_id: str, subscription_url: str)` and `RelayUnavailable(message: str)`; no caller handles raw httpx exceptions.
- Produces: encrypted server settings `calendar_relay_url` and `calendar_relay_token`; `calendar_relay_url` is HTTPS-only and its token is secret.

- [ ] **Step 1: Write failing backend tests for relay configuration and client boundaries**

```python
async def test_relay_settings_are_encrypted_and_never_returned(client, admin, setup_db):
    await put(client, admin, {"calendar_relay_url": "https://relay.example", "calendar_relay_token": "secret"})
    assert "secret" not in (await client.get(URL, headers=_h(admin))).text

@pytest.mark.anyio
async def test_create_feed_uses_the_configured_https_endpoint_and_normalizes_a_timeout(monkeypatch):
    # fake AsyncClient records the bounded request and raises httpx.TimeoutException
    with pytest.raises(calendar_relay.RelayUnavailable, match="calendar relay timed out"):
        await calendar_relay.create_feed("titles", b"BEGIN:VCALENDAR\r\nEND:VCALENDAR\r\n")
```

Add Worker tests that prove unauthenticated management requests are 401, an authorized create returns an opaque URL, a public read returns `text/calendar; charset=utf-8`, replacement is atomic, and deleting the relay ID makes the old public URL 404.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `cd relay && npm test`

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_calendar_relay.py tests/test_server_settings.py -v`

Expected: FAIL because relay fields/client do not exist.

- [ ] **Step 3: Implement the Worker protocol, relay settings, and `app.integrations.calendar_relay`**

Configure `wrangler.jsonc` with `new_sqlite_classes`, not `new_classes`, for the relay Durable Object. The Worker must generate high-entropy IDs and public tokens, hash public tokens before storage, and use the Durable Object's transactional SQLite storage for create/replace/revoke. Add the two backend settings to `Settings` and `server_config.FIELDS`; use the existing Fernet-backed setting path and return only `is_set`/locked state from `describe()`. The client uses the fixed configured Worker base URL, HTTPS validation, explicit connect/read/write timeout, a bounded response body, and normalizes all transport/provider errors. Keep URLs, tokens, and ICS content out of logs and exception messages.

- [ ] **Step 4: Add the relay settings section to Admin → Settings**

Add a `calendar-relay` section and `ServerSettingsForm` field definitions. Extend the test-action union only if the selected provider has a safe non-mutating health check; otherwise omit a test button.

- [ ] **Step 5: Run focused backend and frontend tests**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_calendar_relay.py tests/test_server_settings.py -v`

Run: `cd frontend && npm test -- ServerSettings`

Run: `cd relay && npm test`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add relay backend/app/core/config.py backend/app/services/server_config.py backend/app/routers/server_settings.py backend/app/integrations/calendar_relay.py backend/tests/test_calendar_relay.py backend/tests/test_server_settings.py frontend/src/api/serverSettings.ts frontend/src/pages/admin/FamilySettings.tsx frontend/src/pages/admin/ServerSettingsForm.tsx frontend/src/pages/admin/ServerSettings.test.tsx
git commit -m "feat: add managed calendar relay"
```

### Task 2: Subscription persistence and ICS serialization

**Files:**
- Create: `backend/app/models/calendar_subscription.py`
- Modify: `backend/app/models/__init__.py:1-17`
- Modify: `backend/alembic/env.py:16-28`
- Create: `backend/alembic/versions/*_calendar_subscriptions.py`
- Create: `backend/app/services/calendar_subscriptions.py`
- Create: `backend/tests/test_calendar_subscriptions.py`

**Interfaces:**
- Consumes: `calendar_relay.RelayFeed` from Task 1.
- Produces: `CalendarSubscription` with `family_id`, `kind: Literal["titles", "full"]`, encrypted `relay_url`, `relay_id`, `active`, `publication_pending`, `last_published_at`, `last_error`, and timestamps; `(family_id, kind)` is unique.
- Produces: `CalendarSubscriptionAudit` with subscription/family IDs, action (`created`, `revealed`, `rotated`, `revoked`), actor user ID, and timestamp; audit records never contain a URL or token.
- Produces: `async def render_ics(db: AsyncSession, family_id: str, kind: Literal["titles", "full"]) -> bytes`.

- [ ] **Step 1: Write failing model and serializer tests**

```python
async def test_render_ics_exports_local_and_synced_events_but_not_deleted_or_disabled_sources(setup_db, family):
    rendered = await render_ics(setup_db, family.id, "full")
    assert b"SUMMARY:Family dinner" in rendered
    assert b"SUMMARY:School concert" in rendered
    assert b"SUMMARY:Deleted" not in rendered

async def test_titles_ics_omits_all_detail_properties_and_full_ics_preserves_them(setup_db, family):
    titles = await render_ics(setup_db, family.id, "titles")
    full = await render_ics(setup_db, family.id, "full")
    assert b"DESCRIPTION" not in titles and b"LOCATION" not in titles and b"ATTENDEE" not in titles
    assert b"DESCRIPTION:Bring forms" in full and b"LOCATION:Library" in full
```

- [ ] **Step 2: Run the serializer tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_calendar_subscriptions.py -v`

Expected: FAIL because the model and renderer do not exist.

- [ ] **Step 3: Add `CalendarSubscription` and migration**

Store the relay URL encrypted using the same key derivation as server settings (a helper in the subscriptions service, not a plaintext model column). Add the URL-free audit table in the same migration. Import both models in `models/__init__.py` and `alembic/env.py`; base the new migration on the actual latest revision, not a guessed number.

- [ ] **Step 4: Implement `render_ics`**

Query `CalendarEvent` joined to `CalendarSource` with the same family, source enabled/deleted, event deleted, and overlap rules as `get_events_in_range`, across the documented stored publication horizon. Use `icalendar.Calendar`/`Event`; set a stable calendar name and deterministic UID derived from OpenFamHub source/event identity. Serialize UTC timed values and date-only all-day boundaries. The titles variant sets only timing, UID, sequence/modified data, and `SUMMARY`; the full variant adds allowed stored detail fields.

- [ ] **Step 5: Add review-focus tests for all-day and identity behaviour**

```python
async def test_all_day_export_uses_date_only_exclusive_end_and_stable_uid_after_re_render(setup_db, family):
    first = await render_ics(setup_db, family.id, "full")
    second = await render_ics(setup_db, family.id, "full")
    assert first == second
    assert b"DTSTART;VALUE=DATE:20261023" in first
    assert b"DTEND;VALUE=DATE:20261025" in first
```

- [ ] **Step 6: Run focused tests**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_calendar_subscriptions.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/calendar_subscription.py backend/app/models/__init__.py backend/alembic/env.py backend/alembic/versions backend/app/services/calendar_subscriptions.py backend/tests/test_calendar_subscriptions.py
git commit -m "feat: serialize managed calendar subscriptions"
```

### Task 3: Durable, post-commit publication and retries

**Files:**
- Create: `backend/app/jobs/calendar_subscriptions.py`
- Modify: `backend/app/jobs/scheduler.py:5-26`
- Modify: `backend/app/routers/calendar.py:73-101, 116-165, 201-291`
- Modify: `backend/app/jobs/calendar_sync.py:26-133`
- Modify: `backend/app/services/calendar_subscriptions.py`
- Modify: `backend/tests/test_calendar_subscriptions.py`
- Modify: `backend/tests/test_calendar_sync.py`

**Interfaces:**
- Consumes: `render_ics()` from Task 2 and relay client methods from Task 1.
- Produces: `async def mark_family_subscriptions_dirty(db: AsyncSession, family_id: str) -> None`, `async def publish_due_subscriptions() -> None`, and `async def publish_subscription(db: AsyncSession, subscription: CalendarSubscription) -> None`.
- Produces: `register_calendar_subscription_jobs(scheduler) -> None`.

- [ ] **Step 1: Write failing tests for committed publication and retry**

```python
async def test_event_edit_marks_both_active_feeds_dirty_only_after_commit(client, admin, monkeypatch):
    # replace relay calls with a recorder; the recorder sees the updated title only after request completion
    ...

async def test_relay_failure_keeps_local_event_change_marks_subscription_pending_and_retries(setup_db, family, monkeypatch):
    await publish_due_subscriptions()
    assert subscription.last_error == "Could not reach the calendar relay"
    assert subscription.publication_pending is True
```

- [ ] **Step 2: Run publication tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_calendar_subscriptions.py tests/test_calendar_sync.py -v`

Expected: FAIL because no publication coordinator or job exists.

- [ ] **Step 3: Implement durable dirty marking and the scheduler retry job**

Mark active subscriptions dirty inside the same database transaction as a calendar/source mutation. Publish only from a fresh background session after commit; use the existing single `AsyncIOScheduler`, a bounded retry interval, and idempotent full-document replacement. On success clear `publication_pending`, set `last_published_at`, and clear the error; on failure retain the last relay copy, save a safe error, and keep it pending.

- [ ] **Step 4: Wire every calendar-changing path**

Call `mark_family_subscriptions_dirty` for local event create/update/delete, source metadata/enable/delete changes, successful manual source sync, and successful scheduled source sync. Do not mark a subscription for a failed source fetch or a rolled-back savepoint. Preserve `queue_event` for live updates; do not call `event_bus.emit` directly.

- [ ] **Step 5: Add the review-focus source-removal test**

```python
async def test_disabling_or_deleting_source_republishes_without_its_events(client, admin, relay_recorder):
    await client.patch("/api/calendar/sources/school", json={"enabled": False}, headers=_h(admin))
    await publish_due_subscriptions()
    assert b"School concert" not in relay_recorder.last_full_document
```

- [ ] **Step 6: Run focused backend tests**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_calendar_subscriptions.py tests/test_calendar_sync.py tests/test_calendar_routes.py -v`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/jobs/calendar_subscriptions.py backend/app/jobs/scheduler.py backend/app/routers/calendar.py backend/app/jobs/calendar_sync.py backend/app/services/calendar_subscriptions.py backend/tests/test_calendar_subscriptions.py backend/tests/test_calendar_sync.py
git commit -m "feat: publish calendar subscriptions after changes"
```

### Task 4: Password-gated subscription management API

**Files:**
- Create: `backend/app/schemas/calendar_subscription.py`
- Create: `backend/app/routers/calendar_subscriptions.py`
- Modify: `backend/app/main.py:88-115`
- Modify: `backend/app/services/calendar_subscriptions.py`
- Modify: `backend/tests/test_calendar_subscriptions.py`

**Interfaces:**
- Consumes: `CalendarSubscription`, `calendar_relay.create_feed/replace_feed/revoke_feed`, and Task 3 publication helpers.
- Produces: `GET /api/calendar/subscriptions`, `POST /api/calendar/subscriptions/{kind}`, `POST /api/calendar/subscriptions/{kind}/reveal`, `POST /api/calendar/subscriptions/{kind}/rotate`, and `DELETE /api/calendar/subscriptions/{kind}`.
- Produces: list responses with `kind`, `active`, `last_published_at`, `last_error`, and suffix only; create/reveal/rotate responses additionally carry `subscription_url`.

- [ ] **Step 1: Write failing authorization and secret-response tests**

```python
async def test_only_unlocked_admin_can_create_or_reveal_subscription_url(client, admin, member):
    assert (await client.post("/api/calendar/subscriptions/titles", headers=_h(member))).status_code == 403
    assert (await client.post("/api/calendar/subscriptions/titles", headers=_h(admin))).status_code == 403  # PIN admin

async def test_list_response_never_contains_url_but_reveal_returns_only_requested_kind(client, password_admin):
    listed = (await client.get("/api/calendar/subscriptions", headers=_h(password_admin))).text
    assert "https://relay.example/secret" not in listed
    assert (await client.post("/api/calendar/subscriptions/titles/reveal", headers=_h(password_admin))).json()["subscription_url"].endswith("titles-token")
```

- [ ] **Step 2: Run API tests to verify they fail**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_calendar_subscriptions.py -v`

Expected: FAIL with 404 because the router is absent.

- [ ] **Step 3: Implement schemas and router lifecycle operations**

Use `require_role("admin")` so the existing password/elevation gate applies. Create initial feed content through the relay before marking it active; encrypt the returned URL and persist only the chosen kind. Reveal decrypts only the requested feed. Rotate creates a replacement relay feed, persists it atomically, then revokes the old relay ID; if revocation fails, retain safe remediation status without disclosing tokens. Revoke marks the selected feed inactive and calls the relay; a retryable relay failure must be visible and must not affect the other kind.

- [ ] **Step 4: Add lifecycle and review-focus tests**

```python
async def test_rotating_titles_invalidates_only_titles_and_revealing_full_still_returns_its_original_url(client, password_admin):
    ...

async def test_revoke_marks_only_requested_feed_inactive_and_audits_action(client, password_admin):
    ...
```

- [ ] **Step 5: Run focused backend tests**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_calendar_subscriptions.py tests/test_phase2.py -v`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/calendar_subscription.py backend/app/routers/calendar_subscriptions.py backend/app/main.py backend/app/services/calendar_subscriptions.py backend/tests/test_calendar_subscriptions.py
git commit -m "feat: manage calendar subscription links"
```

### Task 5: Calendar subscriptions admin interface

**Files:**
- Create: `frontend/src/api/calendarSubscriptions.ts`
- Create: `frontend/src/pages/admin/CalendarSubscriptions.tsx`
- Create: `frontend/src/pages/admin/CalendarSubscriptions.test.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/admin/CalendarSettings.tsx`
- Modify: `frontend/src/pages/admin/CalendarSettings.test.tsx`

**Interfaces:**
- Consumes: Task 4 API endpoints and response types.
- Produces: `useCalendarSubscriptions`, `useCreateCalendarSubscription`, `useRevealCalendarSubscription`, `useRotateCalendarSubscription`, and `useRevokeCalendarSubscription`.
- Produces: Admin navigation from Calendar Settings to the subscriptions screen; no URL is saved in React Query cache after the reveal/create/rotate interaction closes.

- [ ] **Step 1: Write failing component tests**

```tsx
it('creates a titles feed, presents the URL for copying, then removes it when the dialog closes', async () => {
  mockApi({ 'GET /calendar/subscriptions': [], 'POST /calendar/subscriptions/titles': { kind: 'titles', subscription_url: 'https://relay.example/secret' } })
  renderApp(<CalendarSubscriptions />)
  fireEvent.click(await screen.findByRole('button', { name: 'Create titles subscription' }))
  expect(await screen.findByDisplayValue('https://relay.example/secret')).toBeTruthy()
  fireEvent.click(screen.getByRole('button', { name: 'Close' }))
  expect(screen.queryByDisplayValue('https://relay.example/secret')).toBeNull()
})

it('shows delivery error/status and asks before rotating or revoking only the selected feed', async () => { ... })
```

- [ ] **Step 2: Run the UI tests to verify they fail**

Run: `cd frontend && npm test -- CalendarSubscriptions CalendarSettings`

Expected: FAIL because the component and hooks do not exist.

- [ ] **Step 3: Implement API hooks and the admin page**

Use the project `apiClient`, Query keys scoped to `calendar-subscriptions`, and existing `errorDetail`/password-prompt behavior. Explain that subscriptions are read-only, that the titles feed hides details, and that client refreshes can lag. Display URLs only in a focused create/reveal/rotate dialog with copy affordance and clear it from component state on close; listing cards show only kind, status, safe suffix, timestamps, and errors.

- [ ] **Step 4: Link from Calendar Settings and preserve admin routing**

Add a visible “Calendar subscriptions” action near source management and a protected lazy route consistent with the other admin pages. Do not expose the page or management actions to non-admin routes.

- [ ] **Step 5: Run focused frontend tests**

Run: `cd frontend && npm test -- CalendarSubscriptions CalendarSettings`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/calendarSubscriptions.ts frontend/src/pages/admin/CalendarSubscriptions.tsx frontend/src/pages/admin/CalendarSubscriptions.test.tsx frontend/src/pages/admin/CalendarSettings.tsx frontend/src/pages/admin/CalendarSettings.test.tsx frontend/src/App.tsx
git commit -m "feat: add calendar subscription controls"
```

### Task 6: Deployment documentation and final regression verification

**Files:**
- Modify: `deploy/env.template`
- Modify: `docs/deployment.md`
- Modify: `docs/architecture.md:88-99`
- Modify: `GETTING_STARTED.md`
- Modify: `backend/tests/test_startup.py`

**Interfaces:**
- Consumes: relay configuration, scheduler registration, admin API, and UI from Tasks 1–5.
- Produces: operator setup/rotation/revocation guidance, documented data-sharing boundary, and startup coverage for the retry job.

- [ ] **Step 1: Write failing startup and configuration documentation tests where applicable**

```python
async def test_app_boot_registers_calendar_subscription_retry_job(monkeypatch):
    # assert scheduler contains the subscription retry job after lifespan startup
    ...
```

- [ ] **Step 2: Run the startup test to verify it fails**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest tests/test_startup.py -v`

Expected: FAIL until the scheduler registration exists.

- [ ] **Step 3: Document operator setup and the privacy boundary**

Add Cloudflare Worker URL/token environment variables to the template without values. Document the privacy-policy/processor review gate (including Cloudflare DPA, privacy policy, retention/subprocessor review, and data-location choice), that the relay stores the two feed snapshots, the dependency on client refresh intervals, feed creation/reveal/rotation/revocation, and required cleanup at the relay when retiring an installation. Update architecture's calendar-sync section with the outbound relay flow and retry semantics.

- [ ] **Step 4: Run the complete verification suite**

Run: `cd backend && source .venv/bin/activate && SECRET_KEY=test-secret pytest -v --cov`

Run: `cd frontend && npm run test:coverage && npm run lint && npm run build`

Expected: all backend and frontend tests pass, coverage remains above configured floors, lint reports no errors, and the production build succeeds.

- [ ] **Step 5: Commit**

```bash
git add deploy/env.template docs/deployment.md docs/architecture.md GETTING_STARTED.md backend/tests/test_startup.py
git commit -m "docs: document managed calendar subscriptions"
```

## Self-Review

- **Spec coverage:** Tasks 1–2 cover the managed-relay boundary, encrypted secret storage, all-event export, privacy variants, and ICS correctness. Task 3 covers post-commit delivery, retries, and source/event changes. Task 4 covers password-gated lifecycle actions and audit requirements. Task 5 covers clear admin management UX. Task 6 covers deployment, privacy review, scheduler startup, and full regression verification.
- **Step scan:** Every task begins with an executable failing test, names exact interfaces/files, validates the smallest deliverable, and ends in a focused commit.
- **Type consistency:** `titles`/`full`, `CalendarSubscription`, `RelayFeed`, `RelayUnavailable`, `render_ics`, and `mark_family_subscriptions_dirty` are defined before dependent tasks use them.
- **Review focus:** Each listed risk is assigned to Tasks 2–4 with a named test step.
- **Proportion:** The plan records interfaces and test cases without prescribing implementation bodies, except for critical serialization and lifecycle behavior.
