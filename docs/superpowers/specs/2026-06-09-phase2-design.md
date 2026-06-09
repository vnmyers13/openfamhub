# OpenFamHub Redo — Phase 2 Design Spec

**Date:** 2026-06-09
**Scope:** Chores, Rewards + Currency, Meal Planning
**Prerequisites:** Phase 1 (Auth, Calendar, Dashboard, Wall Display) complete

---

## 1. Problem Statement

Phase 2 adds family task management, gamified rewards, and meal planning to OpenFamHub. These features build on the Phase 1 foundation (users, auth, dashboard) to create a complete family organization system.

**Primary use cases:**
- Family members complete chores (admin-assigned or self-claimed) and earn reward points
- Admin creates reward catalog; users redeem points for rewards
- Separate virtual allowance system for weekly pocket money
- Family plans meals weekly, auto-generates shopping lists
- Recipe library with dietary tags and text-paste import

---

## 2. Architecture

```
openfamhub.local (Caddy reverse proxy, internal TLS)
      │
   ┌──┴──┐
   │ API  │  FastAPI, SQLAlchemy 2.0 async, aiosqlite, APScheduler
   │      │  + chores, rewards, meal planning services
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

## 3. Chores System

### 3.1 Data Model

```
chores (templates)
  id              TEXT UUID PK
  title           TEXT NOT NULL
  description     TEXT
  assignment_mode TEXT NOT NULL DEFAULT 'assigned'  (assigned | claimable)
  recurrence_rule TEXT NOT NULL  (daily | weekly_mon | weekly_tue | ... | monthly_1st | monthly_2nd | ... | every_n_days_N)
  point_value     INTEGER NOT NULL DEFAULT 10
  is_active       BOOLEAN NOT NULL DEFAULT 1
  created_by_id   TEXT FK → users.id
  created_at      DATETIME UTC
  updated_at      DATETIME UTC

chore_instances (generated from templates)
  id              TEXT UUID PK
  chore_template_id TEXT FK → chores.id
  assigned_to_id  TEXT FK → users.id
  due_date        DATE NOT NULL
  status          TEXT NOT NULL (pending | claimed | completed | expired)
  claimed_by_id   TEXT FK → users.id (nullable, for claimable chores)
  claimed_at      DATETIME UTC (nullable)
  completed_by_id TEXT FK → users.id (nullable)
  completed_at    DATETIME UTC (nullable)
  created_at      DATETIME UTC

chore_completion_log
  id              TEXT UUID PK
  instance_id     TEXT FK → chore_instances.id
  completed_by_id TEXT FK → users.id
  completed_at    DATETIME UTC NOT NULL
  points_earned   INTEGER NOT NULL DEFAULT 0
```

### 3.2 Key Behaviors

- **Admin-assigned chores:** Admin creates template with `assignment_mode='assigned'` and `assigned_to_id` set. Background job generates instances for assigned user.
- **Claimable chores:** Admin creates template with `assignment_mode='claimable'`. Background job generates instances with `status='pending'`. Any family member can claim by clicking "Claim" (sets `claimed_by_id`, `status='claimed'`). Once claimed, only the claimer can complete.
- **Recurrence rules:**
  - `daily` — Every day
  - `weekly_[day]` — Every Monday/Tuesday/etc. (7 values)
  - `monthly_[nth]` — 1st through 31st of month
  - `every_n_days_N` — Custom interval (e.g., `every_3_days_3`)
- **Background job (APScheduler, runs daily at 6 AM):** Generates instances for the upcoming 7 days from active templates. Deletes expired pending instances.
- **Self-reporting:** Any user with a pending/claimed instance can mark it complete. Instant points award.
- **Completion history:** Log records every completion with user, timestamp, points earned.

### 3.3 API Endpoints

```
POST   /api/chores/templates          — Create chore template (admin)
GET    /api/chores/templates           — List templates (admin)
PUT    /api/chores/templates/{id}      — Update template (admin)
DELETE /api/chores/templates/{id}      — Deactivate template (admin)
GET    /api/chores/instances           — List instances (filtered by user/role)
POST   /api/chores/instances/{id}/claim — Claim a chore (claimable)
POST   /api/chores/instances/{id}/complete — Complete a chore
GET    /api/chores/completion-log      — Completion history
GET    /api/chores/stats               — User stats (total completed, streaks)
```

### 3.4 UI

- **Dedicated Chores page:**
  - Tabs: "My Chores" (assigned/claimed), "Available" (claimable), "Templates" (admin only), "History"
  - My Chores: List of pending/claimed instances with "Complete" button
  - Available: Grid of claimable chores with "Claim" button
  - Templates: Admin CRUD for chore templates with recurrence picker
  - History: Paginated completion log with filters
- **Dashboard widget:** Shows today's pending chores with quick "Complete" button

---

## 4. Rewards + Currency System

### 4.1 Data Model

```
reward_points_ledger (reward points - earned/spent)
  id              TEXT UUID PK
  user_id         TEXT FK → users.id
  points          INTEGER NOT NULL  (+ for earned, - for spent)
  type            TEXT NOT NULL (chore_completion | reward_purchase | reward_request | admin_grant | admin_deduct | streak_bonus | badge_bonus)
  reference_id    TEXT (chore_instance_id or reward_id or badge_id)
  description     TEXT
  created_at      DATETIME UTC

allowance_ledger (virtual currency - separate from points)
  id              TEXT UUID PK
  user_id         TEXT FK → users.id
  amount          NUMERIC(10,2) NOT NULL  (+ for earned, - for spent)
  type            TEXT NOT NULL (allowance_weekly | chore_bonus | admin_grant | purchase | parent_allowance)
  reference_id    TEXT
  description     TEXT
  created_at      DATETIME UTC

rewards (reward catalog)
  id              TEXT UUID PK
  name            TEXT NOT NULL
  description     TEXT
  point_cost      INTEGER NOT NULL
  is_auto_fulfill BOOLEAN NOT NULL DEFAULT 0  (admin toggle)
  is_active       BOOLEAN NOT NULL DEFAULT 1
  created_by_id   TEXT FK → users.id
  created_at      DATETIME UTC

reward_requests (for admin-approve rewards)
  id              TEXT UUID PK
  user_id         TEXT FK → users.id
  reward_id       TEXT FK → rewards.id
  status          TEXT NOT NULL (pending | approved | rejected)
  requested_at    DATETIME UTC
  approved_at     DATETIME UTC (nullable)
  approved_by_id  TEXT FK → users.id (admin who approved)
  rejection_reason TEXT (nullable)

badge_definitions
  id              TEXT UUID PK
  name            TEXT NOT NULL
  description     TEXT
  icon            TEXT (emoji)
  trigger_type    TEXT NOT NULL (streak | milestone | custom)
  trigger_value   INTEGER NOT NULL  (e.g., 7 for 7-day streak, 50 for 50 chores)
  points_reward   INTEGER NOT NULL DEFAULT 0
  created_at      DATETIME UTC

user_badges (earned badges)
  id              TEXT UUID PK
  user_id         TEXT FK → users.id
  badge_definition_id TEXT FK → badge_definitions.id
  earned_at       DATETIME UTC NOT NULL

user_streaks
  user_id         TEXT FK → users.id PK (one per user)
  current_streak  INTEGER NOT NULL DEFAULT 0
  longest_streak  INTEGER NOT NULL DEFAULT 0
  last_completion_date DATE
  grace_days      INTEGER NOT NULL DEFAULT 1  (configurable)
  is_active       BOOLEAN NOT NULL DEFAULT 1
```

### 4.2 Key Behaviors

#### Reward Points
- **Earned:** From chore completion (template's `point_value`), streak bonuses, badge bonuses, admin grants
- **Spent:** On reward purchases (auto-fulfill or admin-approve)
- **Ledger:** All transactions tracked with type, reference, description

#### Reward Store
- Admin creates rewards with `point_cost` and `is_auto_fulfill` toggle
- **Auto-fulfill:** User purchases → points deducted instantly, confirmation shown
- **Admin-approve:** User requests → status='pending' → admin approves/rejects → points deducted on approval

#### Allowance (Separate from Points)
- Weekly automatic allowance per user (admin-configurable amount)
- Chore bonuses (optional extra allowance on chore completion)
- Parent grants (manual allowance addition by admin)
- Numeric (decimal) for dollar amounts
- Full ledger tracking

#### Streaks (Automatic)
- Tracked per user: counts consecutive days with at least one chore completion
- Grace period: `grace_days` (default 1) — streak breaks only if no completion within grace days after last completion
- On streak increment: check badge_definitions for matching streak milestones, auto-award badges + bonus points
- Longest streak tracked and updated

#### Badges (Automatic)
- Trigger types: `streak` (N-day streak), `milestone` (N total chores completed), `custom` (future extensibility)
- Auto-awarded when conditions met (checked on each chore completion)
- Shown on user profile and rewards page

### 4.3 API Endpoints

```
# Reward Points
GET    /api/rewards/points/balance       — Current balance + recent transactions
GET    /api/rewards/points/ledger        — Full ledger (paginated)

# Allowance
GET    /api/rewards/allowance/balance    — Current balance + recent transactions
GET    /api/rewards/allowance/ledger     — Full ledger (paginated)
POST   /api/rewards/allowance/config     — Set weekly allowance per user (admin)

# Rewards Catalog
POST   /api/rewards/catalog              — Create reward (admin)
GET    /api/rewards/catalog              — List active rewards
PUT    /api/rewards/catalog/{id}         — Update reward (admin)
DELETE /api/rewards/catalog/{id}         — Deactivate reward (admin)

# Reward Purchases
POST   /api/rewards/purchase/{id}        — Purchase auto-fulfill reward
POST   /api/rewards/request/{id}         — Request admin-approve reward
GET    /api/rewards/my-requests          — User's reward requests
PUT    /api/rewards/requests/{id}/approve — Approve request (admin)
PUT    /api/rewards/requests/{id}/reject  — Reject request (admin)

# Streaks & Badges
GET    /api/rewards/streak               — User's current/longest streak
GET    /api/rewards/badges               — User's earned badges
GET    /api/rewards/badge-definitions    — Available badge definitions (admin)
POST   /api/rewards/badge-definitions    — Create badge definition (admin)
PUT    /api/rewards/badge-definitions/{id} — Update badge definition (admin)
```

### 4.4 UI

- **Dedicated Rewards page:**
  - Tabs: "Store" (browse/ Redeem rewards), "My Requests" (pending/approved/rejected), "Badges" (earned badges), "History" (points + allowance ledger)
  - Header: Current points balance + allowance balance
  - Store: Grid of rewards with point cost, "Redeem" button (auto) or "Request" button (admin-approve)
  - Badges: Grid of earned badges with icons, descriptions, earn dates
  - History: Combined ledger with filters (points vs allowance, type)
- **Dashboard widget:** Quick view of points + allowance balances

---

## 5. Meal Planning System

### 5.1 Data Model

```
recipes
  id              TEXT UUID PK
  title           TEXT NOT NULL
  content_text    TEXT NOT NULL  (pasted text, raw format)
  ingredients_raw TEXT  (parsed from content_text or manually edited)
  steps_raw       TEXT  (parsed from content_text or manually edited)
  dietary_tags    TEXT NOT NULL DEFAULT '[]'  (JSON array: ["vegetarian", "gluten-free"])
  prep_time_min   INTEGER (nullable)
  cook_time_min   INTEGER (nullable)
  servings        INTEGER (nullable)
  imported_from   TEXT (nullable, e.g., "website_paste")
  created_by_id   TEXT FK → users.id
  created_at      DATETIME UTC
  updated_at      DATETIME UTC

meal_plans
  id              TEXT UUID PK
  user_id         TEXT FK → users.id (who created the plan)
  meal_type       TEXT NOT NULL (breakfast | lunch | dinner | snack)
  date            DATE NOT NULL
  recipe_id       TEXT FK → recipes.id (nullable = manual entry)
  title           TEXT NOT NULL  (e.g., "Spaghetti" or "PB&J")
  notes           TEXT (nullable)
  created_at      DATETIME UTC

shopping_list
  id              TEXT UUID PK
  family_id       TEXT NOT NULL DEFAULT 'family'  (single family list)
  item            TEXT NOT NULL
  quantity        TEXT (nullable)
  is_checked      BOOLEAN NOT NULL DEFAULT 0
  is_persistent   BOOLEAN NOT NULL DEFAULT 0  (carries over week to week)
  source          TEXT NOT NULL (meal_generated | manual)
  meal_plan_id    TEXT FK → meal_plans.id (nullable = manual items)
  created_by_id   TEXT FK → users.id
  created_at      DATETIME UTC
  checked_at      DATETIME UTC (nullable)

dietary_tags (reference table for tag definitions)
  id              TEXT UUID PK
  name            TEXT NOT NULL UNIQUE  (e.g., "vegetarian")
  color_hex       TEXT NOT NULL DEFAULT '#94a3b8'
  created_at      DATETIME UTC
```

### 5.2 Key Behaviors

#### Recipe Library
- Family-wide: all members see all recipes
- Create from text paste: user pastes recipe text → system stores raw text, attempts heuristic parsing to extract ingredients (lines with quantities like "2 cups", "1 tbsp") and steps (numbered/bulleted lines)
- Manual editing: ingredients/steps editable as free text
- Dietary tags: Admin defines tag list. Users tag recipes from predefined list. Filter library by tags.

#### Weekly Meal Planner
- Grid view: 7 days (columns) × 4 meal types (rows: breakfast, lunch, dinner, snack)
- Assign recipes or type manual entries
- Drag-and-drop to change day/type
- Week navigation (previous/next week)

#### Shopping List
- Auto-generated from weekly meal plan: extracts ingredients from assigned recipes
- Anyone can add manual items
- Items marked "persistent" carry over week to week (non-persistent reset each Monday)
- Check/uncheck items (checked_at timestamp)
- List view with quantity, check button, delete button

#### Dashboard Widget
- Shows today's meals (breakfast/lunch/dinner/snack) with titles

### 5.3 API Endpoints

```
# Recipes
POST   /api/meals/recipes                — Create recipe (admin/members)
GET    /api/meals/recipes                — List recipes (with tag filter)
GET    /api/meals/recipes/{id}           — Get recipe detail
PUT    /api/meals/recipes/{id}           — Update recipe
DELETE /api/meals/recipes/{id}           — Delete recipe

# Meal Plans
GET    /api/meals/plans?week_start=...   — Get meal plan for week
PUT    /api/meals/plans                  — Update meal plan (assign recipe to day/type)
POST   /api/meals/plans                  — Create meal plan entry
DELETE /api/meals/plans/{id}             — Remove meal plan entry

# Shopping List
GET    /api/meals/shopping-list          — Get current week's shopping list
POST   /api/meals/shopping-list          — Add item (manual)
PUT    /api/meals/shopping-list/{id}     — Update item (check/uncheck, persistent)
DELETE /api/meals/shopping-list/{id}     — Remove item
POST   /api/meals/shopping-list/regenerate — Regenerate from current meal plan

# Dietary Tags
GET    /api/meals/dietary-tags           — List tags
POST   /api/meals/dietary-tags           — Create tag (admin)
PUT    /api/meals/dietary-tags/{id}      — Update tag (admin)
DELETE /api/meals/dietary-tags/{id}      — Delete tag (admin)
```

### 5.4 UI

- **Dedicated Meals page:**
  - Tabs: "Planner" (weekly grid), "Recipes" (library with search/filter), "Shopping List" (checklist)
  - Planner: 7×4 grid, click cell to assign recipe or type manual entry
  - Recipes: Searchable list with tag filters, click to view detail, "Paste Recipe" button
  - Shopping List: Checklist with check/uncheck, "Add Item" button, "Regenerate" button, persistent item toggle
- **Dashboard widget:** Shows today's meals (breakfast/lunch/dinner/snack)

---

## 6. Navigation & Layout Updates

### 6.1 New Routes

```
/chores          — Chores page (all users)
/meals           — Meals page (all users)
/rewards         — Rewards page (all users)
/dashboard/manage-chores    — Chore template management (admin only)
/dashboard/manage-rewards   — Reward catalog management (admin only)
/dashboard/manage-meals     — Recipe/dietary tag management (admin only)
```

### 6.2 NavShell Updates

Add to navigation bar:
- Chores (all users)
- Meals (all users)
- Rewards (all users)

Admin-only items in settings dropdown:
- Manage Chores (templates)
- Manage Rewards (catalog + badge definitions)
- Manage Meals (recipes + dietary tags)

### 6.3 Dashboard Updates

Add widgets to DashboardHome:
- **Chores Widget:** Today's pending/claimed chores with quick "Complete" button
- **Meals Widget:** Today's meals (breakfast/lunch/dinner/snack)
- **Rewards Widget:** Points balance + allowance balance (quick view)

---

## 7. Background Jobs (APScheduler)

### 7.1 Chore Instance Generator
- **Schedule:** Daily at 6:00 AM
- **Actions:**
  1. For each active chore template, generate instances for next 7 days based on recurrence_rule
  2. For `assigned` mode: set `assigned_to_id` from template
  3. For `claimable` mode: set `status='pending'`, `assigned_to_id=NULL`
  4. Delete expired pending instances (past due_date)

### 7.2 Allowance Distributor
- **Schedule:** Weekly on Monday at 7:00 AM
- **Actions:**
  1. For each active user, create allowance_ledger entry with weekly amount (admin-configurable per user)
  2. Skip users with $0 weekly allowance

### 7.3 Streak & Badge Evaluator
- **Schedule:** After each chore completion (triggered by API) + daily at 8:00 AM (catch-all)
- **Actions:**
  1. Update user_streaks: increment streak if completion within grace_days of last_completion_date
  2. Check badge_definitions for matching conditions
  3. Auto-award badges + bonus points when conditions met

---

## 8. Testing Strategy

### 8.1 Backend Tests

**Chores:**
- Chore template CRUD (create, read, update, deactivate)
- Instance generation from templates (all recurrence types)
- Claimable chore flow (claim → complete)
- Assigned chore flow (complete only by assigned user)
- Points award on completion
- Completion log creation

**Rewards:**
- Points ledger (earn, spend, balance calculation)
- Allowance ledger (weekly distribution, manual grants)
- Reward purchase (auto-fulfill: instant deduction)
- Reward request (admin-approve: pending → approved/rejected)
- Streak tracking (consecutive days, grace period)
- Badge auto-award (streak milestone, chore milestone)

**Meals:**
- Recipe CRUD (create from paste, update tags)
- Meal plan CRUD (create, update, delete)
- Shopping list generation from meal plan
- Shopping list persistent items (carry over)
- Dietary tag filtering

### 8.2 Frontend Tests

- Chores page: tab switching, claim/complete actions, template CRUD
- Rewards page: purchase/request flow, badge display, ledger view
- Meals page: planner grid, recipe paste, shopping list interactions

---

## 9. Version Bump

- APP_VERSION: `0.17` → `0.18`
- Dockerfile LABEL updated
- README badge updated
