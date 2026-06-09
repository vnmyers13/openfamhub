# OpenFamHub Redo — Phase 1 Design Spec

**Date:** 2026-06-08
**Scope:** Auth, Profiles, Calendar, Dashboard, Wall Display
**Phase 2 (deferred):** Chores, Rewards, Meal Planning

---

## 1. Problem Statement

OpenFamHub v0.17 was never completed — no sprints finished, code removed. This is a fresh start to build a self-hosted family calendar and organizer hub, starting with core functionality (auth, calendar, dashboard, wall display). Phase 2 will add chores, gamified rewards with currency, and meal planning.

**Primary use cases:**
- Main wall display on Raspberry Pi at 1920×1080 showing calendar and family info
- Family members access via tablet or phone PWA to view calendar and dashboard
- Admin manages family profiles, calendar events, and ICS feed imports

---

## 2. Architecture

```
openfamhub.local (Caddy reverse proxy, internal TLS)
      │
   ┌──┴──┐
   │ API  │  FastAPI, SQLAlchemy 2.0 async, aiosqlite, APScheduler
   │ Web  │  React 19, Vite, TypeScript, Tailwind, Zustand, TanStack Query
   └──────┘
      │
   ┌──┴──┐
   │ SQLite │  WAL mode, foreign_keys=ON, Alembic migrations
   └──────┘
```

**Deployment:** Docker Compose on home server/NAS. Three services: `api`, `web`, `caddy:2-alpine`.

**CI:** GitHub Actions, AMD64 only, runs tests before building Docker images.

---

## 3. Profile & Authentication System

### 3.1 Profile Picker (Netflix-style)

- On first visit (no active session), show full-screen profile selection grid
- Display family member avatars (emoji-based) in a responsive grid
- Selecting a profile prompts for PIN entry (4-6 digit numeric PIN)
- After successful PIN entry, JWT issued and stored in httpOnly SameSite=Strict cookie
- Session auto-locks after 5 minutes of inactivity (configurable per-profile in settings)
- "Add Profile" button visible to admins only

### 3.2 Authentication Flow

1. User visits app → no session → profile picker shown
2. User selects profile → PIN modal appears
3. Correct PIN → JWT issued, app loads with that profile's context
4. Incorrect PIN → error message, rate-limited (5 attempts per 60s)
5. Active session → skips profile picker, goes directly to dashboard
6. Session expired/inactive → returns to profile picker

### 3.3 Admin Profile Management

Admin can:
- Create profiles: name, avatar emoji, PIN, role (admin/member), active status
- Edit profiles: change name, avatar, PIN, role
- Deactivate profiles (soft delete, no data loss)
- View profile activity (last login, session count)

### 3.4 Data Model

```
users
  id            TEXT UUID PK
  name          TEXT NOT NULL
  avatar_emoji  TEXT NOT NULL  (e.g., "👨", "👧")
  pin_hash      TEXT NOT NULL  (bcrypt)
  role          TEXT NOT NULL  (admin | member)
  settings_json TEXT NOT NULL  (default '{}')
  is_active     BOOLEAN NOT NULL DEFAULT 1
  created_at    DATETIME UTC
  updated_at    DATETIME UTC
  last_login_at DATETIME UTC
```

### 3.5 Settings Schema

```json
{
  "theme": "dark" | "light",
  "session_timeout_minutes": 5,
  "pin_length": 4
}
```

---

## 4. Calendar System

### 4.1 Internal Events

Family members with permission can create, edit, and delete internal calendar events.

**Event fields:**
- title, description, location
- start_time, end_time (datetime)
- is_all_day (boolean)
- created_by_id (FK → users)
- assigned_to_id (FK → users, nullable — for events assigned to specific people)
- color_hex (string, for visual grouping)

**Recurrence:** Full RRULE support. Events expand to individual rows on import/save. 12-month rolling window of expanded events.

### 4.2 ICS Feed Integration

Admins can subscribe to external calendar feeds (Google, iCloud, TeamSnap, etc.).

**CalendarSource fields:**
- name, url (HTTPS), color_hex
- sync_interval_hours (default 4, min 1)
- last_synced_at, is_active

**Sync job (APScheduler):**
- Runs every 15 minutes (base interval)
- Checks each active source: if `now - last_synced_at >= sync_interval_hours`, trigger sync
- Fetches ICS, parses events, expands recurrence
- Upserts on (source_id, external_uid) — external data wins on conflict
- Deletes events no longer present in feed
- Logs sync results to sync_log table

**CalendarEvent fields:**
- id, source_id (FK), external_uid, title, description, location
- start_time, end_time, all_day
- color_hex (from source)
- synced_at

### 4.3 Calendar UI

- react-big-calendar with four views: Month, Week, Day, Agenda
- Source filter chips (toggle visibility per source, color-coded)
- Event detail modal on click (show title, time, description, assigned person)
- Admin can delete events from any source
- Swipe gesture navigation between views (mobile)
- Event creation/editing modal for internal events

### 4.4 Data Models

```
events (internal)
  id              TEXT UUID PK
  title           TEXT NOT NULL
  description     TEXT
  location        TEXT
  start_time      DATETIME UTC NOT NULL
  end_time        DATETIME UTC NOT NULL
  is_all_day      BOOLEAN NOT NULL DEFAULT 0
  created_by_id   TEXT FK → users.id
  assigned_to_id  TEXT FK → users.id (nullable)
  color_hex       TEXT
  is_deleted      BOOLEAN NOT NULL DEFAULT 0
  created_at      DATETIME UTC
  updated_at      DATETIME UTC

calendar_sources
  id              TEXT UUID PK
  name            TEXT NOT NULL
  url             TEXT NOT NULL
  color_hex       TEXT NOT NULL
  sync_interval_hours INTEGER NOT NULL DEFAULT 4
  last_synced_at  DATETIME UTC
  is_active       BOOLEAN NOT NULL DEFAULT 1
  created_at      DATETIME UTC
  updated_at      DATETIME UTC

calendar_events (external)
  id              TEXT UUID PK
  source_id       TEXT FK → calendar_sources.id
  external_uid    TEXT NOT NULL
  title           TEXT NOT NULL
  description     TEXT
  location        TEXT
  start_time      DATETIME UTC NOT NULL
  end_time        DATETIME UTC NOT NULL
  all_day         BOOLEAN NOT NULL DEFAULT 0
  color_hex       TEXT NOT NULL
  synced_at       DATETIME UTC
  is_deleted      BOOLEAN NOT NULL DEFAULT 0
  created_at      DATETIME UTC

sync_log
  id              TEXT UUID PK
  source_id       TEXT FK → calendar_sources.id
  events_imported INTEGER NOT NULL DEFAULT 0
  events_deleted  INTEGER NOT NULL DEFAULT 0
  errors          TEXT (JSON array of error messages)
  started_at      DATETIME UTC
  completed_at    DATETIME UTC
  status          TEXT (success | partial | failed)
```

---

## 5. Dashboard

### 5.1 Dashboard Components

1. **Greeting widget** — Time-based greeting ("Good morning, [Name]!") with profile avatar
2. **Today's events** — List of today's calendar events (internal + ICS), grouped by time
3. **Quick actions** — Row of action buttons:
   - "Add Event" (opens event creation modal)
   - "Manage ICS Feeds" (admin only, opens calendar settings)
   - "New Announcement" (admin only)
4. **Announcements board** — Pinned and recent announcements from family members
5. **Sync status** (admin only) — Last sync time per source, sync health indicator

### 5.2 Announcements

Any family member can create announcements. Admins can pin them.

```
announcements
  id              TEXT UUID PK
  author_id       TEXT FK → users.id
  content         TEXT NOT NULL
  is_pinned       BOOLEAN NOT NULL DEFAULT 0
  is_deleted      BOOLEAN NOT NULL DEFAULT 0
  created_at      DATETIME UTC
```

---

## 6. Wall Display

### 6.1 Display Specs

- Resolution: 1920×1080
- Access: `/wall` — public, no authentication required
- Auto-refresh: 60 seconds
- Idle detection: 30 seconds of no interaction → clock + photo slideshow mode
- Real-time updates via WebSocket (`/api/ws/wall`)

### 6.2 Two Display Modes

**Mode A — Grid Layout (default):**
```
┌─────────────────────────────────────┐
│  LIVE CLOCK (top center, large)     │
├─────────────────┬───────────────────┤
│  7-DAY CALENDAR │   TODAY'S EVENTS  │
│  STRIP (top)    │   LIST (left)     │
├─────────────────┴───────────────────┤
│  ANNOUNCEMENTS  │   FAMILY MEMBERS  │
│  BOARD (left)   │   GRID (right)    │
└─────────────────────────────────────┘
```

**Mode B — Panel Cycling:**
- Auto-cycles through 4 panels every 10 seconds:
  1. Calendar strip (full width, 7-day view)
  2. Today's events (full width, detailed list)
  3. Announcements (full width, scrolling)
  4. Family member status (full width, who's home/active)
- Admin can manually switch panels by tapping screen

### 6.3 Wall Display Data

Wall display fetches:
- Today's events (internal + ICS, next 7 days)
- Active announcements (pinned first, then recent)
- Active family members list
- Current time (client-side)

### 6.4 WebSocket Protocol

```
Client connects: ws://openfamhub.local/api/ws/wall

Server pushes events on:
- New/updated/deleted calendar events
- New announcements
- Family member status changes

Message format:
{
  "type": "event_updated" | "announcement_new" | "members_updated",
  "timestamp": "2026-06-08T12:00:00Z",
  "payload": { ... }
}
```

---

## 7. API Endpoints (Phase 1)

### Auth & Profiles
- `POST /api/auth/login` — PIN login, returns JWT
- `POST /api/auth/logout` — Invalidate session
- `GET /api/auth/me` — Current profile info
- `GET /api/profiles` — List active profiles (for profile picker, no auth)
- `POST /api/admin/profiles` — Create profile (admin)
- `PATCH /api/admin/profiles/{id}` — Update profile (admin)
- `DELETE /api/admin/profiles/{id}` — Deactivate profile (admin)

### Calendar
- `GET /api/events` — List events (with query params: start, end, view)
- `POST /api/events` — Create internal event (auth required)
- `PATCH /api/events/{id}` — Update internal event (author or admin)
- `DELETE /api/events/{id}` — Delete internal event (author or admin)
- `GET /api/calendar/sources` — List ICS sources (admin)
- `POST /api/calendar/sources` — Add ICS source (admin)
- `PATCH /api/calendar/sources/{id}` — Update source (admin)
- `DELETE /api/calendar/sources/{id}` — Remove source (admin)
- `POST /api/calendar/sources/{id}/sync` — Trigger immediate sync (admin)
- `GET /api/calendar/sync-log` — Sync history (admin)

### Dashboard
- `GET /api/dashboard/today` — Today's events + announcements + sync status
- `GET /api/announcements` — List announcements
- `POST /api/announcements` — Create announcement (auth)
- `PATCH /api/announcements/{id}/pin` — Pin/unpin (admin)

### Wall
- `GET /api/wall/data` — Wall display data (public, no auth)
- `WS /api/ws/wall` — WebSocket for real-time updates

---

## 8. Frontend Routing

```
/                    → Profile picker (no session) → Dashboard (session)
/wall                → Wall display (public)
/calendar            → Calendar page (Month/Week/Day/Agenda)
/calendar/settings   → Calendar settings (admin)
/announcements       → Announcements board
/admin/users         → User management (admin)
```

---

## 9. Non-Functional Requirements

- **Database:** SQLite with WAL mode, foreign_keys=ON, auto-backup daily
- **Auth:** JWT in httpOnly SameSite=Strict cookie, 30-day expiry, bcrypt for PIN hashing
- **Performance:** Calendar page loads < 2s, wall data fetches < 1s
- **Mobile:** Responsive design for tablet and phone (min-width 320px)
- **PWA:** Installable on Android/iOS, offline read capability for calendar
- **Security:** Rate limiting on PIN login (5 attempts/60s), CORS restricted to LAN

---

## 10. Phase 2 Preview (Deferred)

- **Chore management:** Fixed recurring chores + flexible one-off tasks
- **Reward system:** Points + streaks + badges + virtual currency
- **Reward store:** Auto-fulfill low-cost, admin-approve high-cost
- **Meal planning:** Recipe library, dietary tags, suggestion voting, shopping lists

---

*Design approved by user on 2026-06-08.*
