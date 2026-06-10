# Phase 2B: Meal Planning — Implementation Plan

**Created:** 2026-06-10
**Status:** Planned
**Target Version:** 0.18 (already bumped)
**Scope:** Recipe library with text/URL import, family-wide meal planner, shopping list, dietary tags, dashboard widget

---

## Design Decisions (User-Approved)

| Decision | Choice | Rationale |
|---|---|---|
| Recipe import | Text paste + URL import | More useful, httpx already available |
| Meal plan scope | Family-wide | Simpler, matches family use case |
| Shopping list scope | Family-wide | Shared list, persistent items model |
| Dietary tags | Admin-defined list | Prevents tag clutter, cleaner UX |
| Dashboard widget | Week's dinner overview | Most useful at-a-glance info |

---

## Task Group 1: Database Models

**File:** `backend/app/models/event.py` (extend)

### 1.1 Add 4 new model classes

```python
class DietaryTag(Base, TimestampMixin):
    """Admin-defined dietary tag (vegetarian, gluten-free, nut-free, etc.)"""
    name: Mapped[str]  # UNIQUE
    color_hex: Mapped[str]  # Default "#94a3b8"

class Recipe(Base, TimestampMixin):
    """Recipe with parsed ingredients and steps"""
    title: Mapped[str]
    content_text: Mapped[str]  # Raw pasted/fetched text
    ingredients_raw: Mapped[str | None]  # Parsed or manual
    steps_raw: Mapped[str | None]  # Parsed or manual
    dietary_tags_json: Mapped[str]  # JSON array of tag IDs, default "[]"
    prep_time_min: Mapped[int | None]
    cook_time_min: Mapped[int | None]
    servings: Mapped[int | None]
    imported_from: Mapped[str | None]  # "website_paste" or None
    created_by_id: Mapped[str]  # FK → users.id

class MealPlan(Base, TimestampMixin):
    """Family-wide weekly meal plan entry"""
    meal_type: Mapped[str]  # "breakfast"|"lunch"|"dinner"|"snack"
    date: Mapped[str]  # DATE format YYYY-MM-DD
    recipe_id: Mapped[str | None]  # FK → recipes.id, nullable = manual entry
    title: Mapped[str]  # Recipe title or manual entry
    notes: Mapped[str | None]

class ShoppingListItem(Base, TimestampMixin):
    """Shopping list item"""
    item: Mapped[str]
    quantity: Mapped[str | None]
    is_checked: Mapped[bool]  # Default False
    is_persistent: Mapped[bool]  # Default False, carries over week to week
    source: Mapped[str]  # "meal_generated" or "manual"
    meal_plan_id: Mapped[str | None]  # FK → meal_plans.id, nullable = manual
    created_by_id: Mapped[str]  # FK → users.id
    checked_at: Mapped[str | None]
```

**Notes:**
- Use `TimestampMixin` for all (created_at, updated_at)
- `dietary_tags_json` stores JSON array of tag IDs (e.g., `["tag-id-1", "tag-id-2"]`)
- `MealPlan` has no `user_id` — family-wide, not per-user
- `ShoppingListItem` has no `family_id` — single family list
- Shopping list items need a `week_start_date` field to track which week they belong to

**Correction:** Add `week_start_date` to `ShoppingListItem`:
```python
week_start_date: Mapped[str]  # DATE format, the Monday of the current week
```

---

## Task Group 2: Pydantic Schemas

**File:** `backend/app/schemas/models.py` (extend)

### 2.1 Add ~25 new schemas

**DietaryTag schemas:**
```python
class DietaryTagCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color_hex: str = Field(default="#94a3b8", pattern=r"^#[0-9a-fA-F]{6}$")

class DietaryTagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color_hex: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    is_active: Optional[bool] = None

class DietaryTagResponse(BaseModel):
    id: str
    name: str
    color_hex: str
    is_active: bool = True
    created_at: str
```

**Recipe schemas:**
```python
class RecipeCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    content_text: str = Field(..., min_length=1)
    ingredients_raw: Optional[str] = None
    steps_raw: Optional[str] = None
    dietary_tag_ids: list[str] = Field(default_factory=list)
    prep_time_min: Optional[int] = Field(None, ge=0)
    cook_time_min: Optional[int] = Field(None, ge=0)
    servings: Optional[int] = Field(None, ge=1)
    imported_from: Optional[str] = None

class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    content_text: Optional[str] = None
    ingredients_raw: Optional[str] = None
    steps_raw: Optional[str] = None
    dietary_tag_ids: Optional[list[str]] = None
    prep_time_min: Optional[int] = None
    cook_time_min: Optional[int] = None
    servings: Optional[int] = None

class RecipeResponse(BaseModel):
    id: str
    title: str
    content_text: str
    ingredients_raw: Optional[str] = None
    steps_raw: Optional[str] = None
    dietary_tag_ids: list[str]
    dietary_tags: list[dict]  # {id, name, color_hex}
    prep_time_min: Optional[int] = None
    cook_time_min: Optional[int] = None
    servings: Optional[int] = None
    imported_from: Optional[str] = None
    created_by_id: str
    created_at: str
    updated_at: str

class RecipeImportRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = None
```

**MealPlan schemas:**
```python
class MealPlanCreate(BaseModel):
    meal_type: str = Field(..., pattern=r"^(breakfast|lunch|dinner|snack)$")
    date: str  # YYYY-MM-DD
    recipe_id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=200)
    notes: Optional[str] = None

class MealPlanUpdate(BaseModel):
    meal_type: Optional[str] = None
    date: Optional[str] = None
    recipe_id: Optional[str] = None
    title: Optional[str] = None
    notes: Optional[str] = None

class MealPlanResponse(BaseModel):
    id: str
    meal_type: str
    date: str
    recipe_id: Optional[str] = None
    title: str
    notes: Optional[str] = None
    recipe: Optional[dict] = None  # Full recipe if recipe_id set
    created_at: str
    updated_at: str

class MealPlanWeekResponse(BaseModel):
    week_start: str  # YYYY-MM-DD (Monday)
    week_end: str  # YYYY-MM-DD (Sunday)
    meals: list[MealPlanResponse]
```

**ShoppingList schemas:**
```python
class ShoppingListItemCreate(BaseModel):
    item: str = Field(..., min_length=1, max_length=200)
    quantity: Optional[str] = None
    is_persistent: bool = False
    meal_plan_id: Optional[str] = None

class ShoppingListItemUpdate(BaseModel):
    item: Optional[str] = None
    quantity: Optional[str] = None
    is_checked: Optional[bool] = None
    is_persistent: Optional[bool] = None

class ShoppingListItemResponse(BaseModel):
    id: str
    item: str
    quantity: Optional[str] = None
    is_checked: bool
    is_persistent: bool
    source: str
    meal_plan_id: Optional[str] = None
    created_by_id: str
    week_start_date: str
    checked_at: Optional[str] = None
    created_at: str
```

---

## Task Group 3: Meals Router

**File:** `backend/app/routers/meals.py` (new)

### 3.1 Endpoints

**Dietary Tags:**
```
GET    /api/meals/dietary-tags           — List all tags
POST   /api/meals/dietary-tags           — Create tag (admin only)
PATCH  /api/meals/dietary-tags/{id}      — Update tag (admin only)
DELETE /api/meals/dietary-tags/{id}      — Delete tag (admin only)
```

**Recipes:**
```
GET    /api/meals/recipes                — List recipes (optional ?tag_id=xxx filter, ?search=xxx)
GET    /api/meals/recipes/{id}           — Get recipe detail (includes ingredients/steps)
POST   /api/meals/recipes                — Create recipe from paste
POST   /api/meals/recipes/import         — Import recipe from URL
PATCH  /api/meals/recipes/{id}           — Update recipe
DELETE /api/meals/recipes/{id}           — Delete recipe
```

**Meal Plans:**
```
GET    /api/meals/plans                  — Get meal plans for week (?week_start=YYYY-MM-DD)
POST   /api/meals/plans                  — Create meal plan entry
PATCH  /api/meals/plans/{id}             — Update meal plan entry
DELETE /api/meals/plans/{id}             — Delete meal plan entry
PUT    /api/meals/plans/bulk              — Bulk update week's meal plans (array of {id, ...} or create ops)
```

**Shopping List:**
```
GET    /api/meals/shopping-list          — Get current week's shopping list (?week_start=YYYY-MM-DD)
POST   /api/meals/shopping-list          — Add item (manual)
POST   /api/meals/shopping-list/regenerate — Regenerate from current week's meal plan
PATCH  /api/meals/shopping-list/{id}     — Update item (check/uncheck, edit, toggle persistent)
DELETE /api/meals/shopping-list/{id}     — Remove item
POST   /api/meals/shopping-list/clear-week — Clear all non-persistent items for a week
```

### 3.2 Dependencies

- All endpoints require auth (`get_current_user`)
- Dietary tag CRUD (POST/PATCH/DELETE) requires `require_role("admin")`
- Recipe CRUD: all roles allowed (members can create/edit recipes)
- Meal plan CRUD: all roles allowed (family-wide)
- Shopping list CRUD: all roles allowed (family-wide)

### 3.3 Implementation Details

**Recipe import from URL:**
- Use `httpx.AsyncClient` to fetch URL
- Try to extract schema.org/Recipe JSON-LD from page
- If found, parse title, ingredients, steps, prep/cook time, servings
- If not found, fall back to storing raw HTML as content_text

**Recipe text parsing (heuristic):**
- Ingredients: lines containing quantity patterns (`\d+\s*(cups|tbsp|tsp|oz|lb|g|kg|ml|L|pinch|slice|piece|can|bunch|bag|box|package|medium|large|small`)
- Steps: numbered lines (`1\.`, `2\.`, etc.) or bulleted lines (`-`, `*`)
- Store raw text, parsed ingredients/steps as separate fields
- Both remain editable

**Meal plan week query:**
- `week_start` param defaults to Monday of current week
- Return all meal plans for dates `week_start` through `week_start + 6 days`
- Group by date for frontend grid rendering

**Shopping list regeneration:**
- Delete all non-persistent items for current week
- Extract all ingredients from current week's meal plans
- Create new shopping list items from ingredients (deduplicate by item name)
- Keep all persistent items

**Shopping list week tracking:**
- On each Monday at 7:00 AM, run a job to:
  1. Clear `checked_at` for all unchecked items of previous week
  2. Optionally: archive or keep old items (keep for history)

---

## Task Group 4: Recipe Parser Service

**File:** `backend/app/services/recipe_parser.py` (new)

### 4.1 Functions

```python
async def parse_recipe_text(text: str) -> dict:
    """
    Heuristic parsing of pasted recipe text.
    Returns: {title, ingredients_raw, steps_raw, prep_time_min, cook_time_min, servings}
    """
    lines = text.strip().split('\n')
    title = lines[0].strip() if lines else "Untitled Recipe"
    
    ingredients = []
    steps = []
    current_section = None  # "ingredients" or "steps"
    
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        
        # Detect section transitions
        lower = line.lower()
        if lower in ('ingredients:', 'ingredients', 'what you\'ll need:', 'for the recipe:'):
            current_section = "ingredients"
            continue
        elif lower in ('instructions:', 'directions:', 'steps:', 'method:', 'how to make:'):
            current_section = "steps"
            continue
        
        # Parse based on section
        if current_section == "ingredients":
            if line and re.match(r'^[\d\w]', line):  # Starts with number/word
                ingredients.append(line)
        elif current_section == "steps":
            if re.match(r'^\d+[\.\)]\s', line) or re.match(r'^[-*•]\s', line):
                steps.append(re.sub(r'^\d+[\.\)]\s|^[*-•]\s', '', line))
        else:
            # Heuristic: lines with quantities are ingredients
            if re.search(r'\d+\s*(cups?|tbsp|tsp|oz|lb|g|kg|ml|L|pinch|slice|piece|can|bunch|bag|box|package|medium|large|small)', line, re.IGNORECASE):
                ingredients.append(line)
            # Numbered lines are steps
            elif re.match(r'^\d+[\.\)]\s', line):
                steps.append(re.sub(r'^\d+[\.\)]\s', '', line))
    
    return {
        "title": title,
        "ingredients_raw": '\n'.join(ingredients) if ingredients else None,
        "steps_raw": '\n'.join(steps) if steps else None,
        "prep_time_min": None,  # Could add time extraction
        "cook_time_min": None,
        "servings": None,
    }


async def import_recipe_from_url(url: str) -> dict:
    """
    Fetch a URL and try to extract recipe data from schema.org/Recipe JSON-LD.
    Falls back to storing raw HTML.
    """
    import httpx
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url)
        response.raise_for_status()
        
        html = response.text
    
    # Try to find JSON-LD with schema.org/Recipe
    import json
    import re
    
    json_ld_pattern = r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>'
    scripts = re.findall(json_ld_pattern, html, re.DOTALL)
    
    for script in scripts:
        try:
            data = json.loads(script)
            recipe = extract_recipe_from_jsonld(data)
            if recipe:
                recipe["imported_from"] = "website"
                recipe["content_text"] = html  # Store raw for reference
                return recipe
        except json.JSONDecodeError:
            continue
    
    # Fallback: store raw HTML
    return {
        "title": "Imported Recipe",
        "content_text": html,
        "ingredients_raw": None,
        "steps_raw": None,
        "imported_from": "website_fallback",
    }


def extract_recipe_from_jsonld(data) -> dict | None:
    """Recursively search JSON-LD data for schema.org/Recipe."""
    if isinstance(data, dict):
        if data.get("@type") in ("Recipe", ["Recipe"]):
            return {
                "title": data.get("name", "Untitled"),
                "ingredients_raw": "\n".join(data.get("recipeIngredient", [])) if data.get("recipeIngredient") else None,
                "steps_raw": "\n".join(data.get("recipeInstructions", [])) if data.get("recipeInstructions") else None,
                "prep_time_min": _parse_duration(data.get("prepTime")),
                "cook_time_min": _parse_duration(data.get("cookTime")),
                "total_time_min": _parse_duration(data.get("totalTime")),
                "servings": data.get("recipeYield"),
            }
        for value in data.values():
            result = extract_recipe_from_jsonld(value)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = extract_recipe_from_jsonld(item)
            if result:
                return result
    return None


def _parse_duration(iso_duration: str) -> int | None:
    """Parse ISO 8601 duration (PT30M, PT1H30M, P1D) to minutes."""
    if not iso_duration:
        return None
    import re
    match = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?', iso_duration)
    if not match:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    return hours * 60 + minutes
```

---

## Task Group 5: Register Router + Main

**File:** `backend/app/main.py`

### 5.1 Import and register meals router

```python
from app.routers.meals import router as meals_router

# In app creation:
app.include_router(meals_router, prefix="/api/meals", tags=["meals"])
```

---

## Task Group 6: Background Jobs

**File:** `backend/app/jobs/shopping_list_reset.py` (new)

### 6.1 Weekly shopping list reset job

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, update
from app.models.event import ShoppingListItem
from app.core.database import get_async_session

def reset_weekly_shopping_list():
    """
    Run every Monday at 7:00 AM.
    Clears checked_at timestamps for items from the previous week.
    Does NOT delete items — keeps history.
    """
    async def _reset():
        async with get_async_session() as db:
            # Find the Monday of last week
            today = datetime.now(timezone.utc).date()
            last_monday = today - timedelta(days=today.weekday()) - timedelta(weeks=1)
            
            # Uncheck any remaining checked items from last week
            await db.execute(
                update(ShoppingListItem)
                .where(
                    (ShoppingListItem.week_start_date == str(last_monday)) &
                    (ShoppingListItem.is_checked == True)
                )
                .values(is_checked=False, checked_at=None)
            )
            await db.commit()
    
    import asyncio
    asyncio.run(_reset())
```

### 6.2 Initialize in main.py startup

In the existing APScheduler initialization:

```python
scheduler.add_job(
    reset_weekly_shopping_list,
    "cron",
    day_of_week="mon",
    hour=7,
    minute=0,
    id="shopping_list_reset",
    replace_existing=True,
)
```

---

## Task Group 7: Backend Tests

**File:** `backend/tests/test_meals.py` (new)

### 7.1 Test cases (target: 8-10 tests)

1. **test_create_dietary_tag** — Admin creates a dietary tag, verify name/color
2. **test_create_recipe_from_text** — Create recipe with pasted text, verify parsing
3. **test_create_recipe_manual** — Create recipe with manual ingredients/steps
4. **test_recipe_filter_by_tag** — Filter recipes by dietary tag ID
5. **test_create_meal_plan** — Create meal plan entry for a date/type
6. **test_get_meal_plan_week** — Get all meals for a week, verify 7x4 grid data
7. **test_add_shopping_item** — Add manual shopping list item
8. **test_regenerate_shopping_list** — Regenerate from meal plans, verify items created
9. **test_shopping_item_check** — Check/uncheck item, verify checked_at timestamp
10. **test_persistent_item_survives_reset** — Mark item persistent, regenerate, verify it stays

---

## Task 8: Frontend — MealsPage

**File:** `frontend/src/pages/MealsPage.tsx` (new)

### 8.1 Page structure

```
MealsPage
├── Top bar: Week navigation (← Week of June 9 →)
├── Tabs: Planner | Recipes | Shopping List
│
├── Tab 1: Planner (7x4 grid)
│   ├── Columns: Mon, Tue, Wed, Thu, Fri, Sat, Sun
│   ├── Rows: Breakfast, Lunch, Dinner, Snack
│   ├── Each cell: recipe title (or manual entry), click to edit
│   └── Click empty cell → modal: "Assign recipe or type manual entry"
│       ├── Search recipes dropdown
│       └── OR type manual title
│
├── Tab 2: Recipes
│   ├── Search bar + tag filter dropdown
│   ├── Recipe cards (title, prep/cook time, servings, tags)
│   ├── "Add Recipe" button → modal
│   │   ├── Text paste area
│   │   ├── OR URL import
│   │   └── "Import" button
│   └── Click recipe → detail view (ingredients, steps, edit)
│
└── Tab 3: Shopping List
    ├── "Regenerate from meal plan" button
    ├── "Add Item" button
    ├── Items list:
    │   ├── Checkbox + item name + quantity
    │   ├── Check/uncheck toggles checked state
    │   ├── "Persistent" toggle
    │   └── Delete button
    └── Summary: X items checked, Y remaining
```

### 8.2 State management

Use TanStack Query (no new Zustand store needed):

```typescript
// Query keys:
["meals", "dietary-tags"]
["meals", "recipes", { tagId?, search? }]
["meals", "recipes", recipeId]
["meals", "plans", { weekStart }]
["meals", "shopping", { weekStart }]
```

### 8.3 Week navigation

- Default to current week (Monday to Sunday)
- ←/→ buttons navigate by week
- "Today" button jumps to current week
- Week stored in URL query param: `/meals?week=2026-06-09`

---

## Task 9: Frontend — Recipe Modal + Detail

**File:** `frontend/src/components/RecipeModal.tsx` (new)

### 9.1 Add Recipe modal

```
Add Recipe Modal
├── Tab: Paste Text | URL Import
│
├── Paste Text:
│   ├── Large textarea for recipe text
│   ├── "Parse" button (heuristic parsing preview)
│   └── Parsed preview:
│       ├── Title (editable)
│       ├── Ingredients (editable, one per line)
│       ├── Steps (editable, one per line)
│       └── Optional: prep time, cook time, servings
│
├── URL Import:
│   ├── URL input
│   ├── "Import" button
│   └── Loading state while fetching
│
├── Dietary tags: multi-select from admin-defined list
└── "Save" button
```

### 9.2 Recipe detail view (inline in Recipes tab)

- Click a recipe card → expand to show full detail
- Show: title, prep/cook time, servings, dietary tags, ingredients list, steps list
- "Edit" button → opens edit modal (same as add but pre-filled)
- "Delete" button (admin only)

---

## Task 10: Dashboard Widget + Navigation

### 10.1 Add Meals navigation to Dashboard.tsx

- Add "Meals" (`FaUtensils`) nav item to `navItems` array
- Path: `/meals`

### 10.2 Add Meals dashboard widget to DashboardHome.tsx

**Widget: This Week's Dinner Overview**
- Show dinners for Mon-Fri (or upcoming days)
- Each dinner: day name + recipe title
- Click to navigate to `/meals`
- Style: green-themed card (food theme)

```
┌─────────────────────────────────┐
│ 🍽️ This Week's Dinners          │
├─────────────────────────────────┤
│ Mon: Spaghetti Bolognese        │
│ Tue: Chicken Stir Fry           │
│ Wed:                            │
│ Thu: Taco Night                 │
│ Fri: Pizza                      │
│                                 │
│ View Full Planner →             │
└─────────────────────────────────┘
```

### 10.3 Add Meals route to App.tsx

```typescript
import MealsPage from './pages/MealsPage'

<Route path="/meals" element={<MealsPage />} />
```

---

## Task 11: Version Bump & Commit

### 11.1 Files to update

- `README.md`: badge already at 0.18 (from Phase 2A)
- `backend/app/core/config.py`: already at 0.18 (from Phase 2A)
- No Dockerfile LABEL to update (wasn't present in Phase 2A)

### 11.2 Verify

- Run `pytest backend/tests/ -v` — expect all tests pass
- Run `npm run build` in frontend/ — expect clean build
- Commit with message: `feat(phase2b): Meal planning system (recipes, meal planner, shopping list)`
- Push to Gitea

---

## File Summary

### Backend (new files)
| File | Description |
|---|---|
| `backend/app/models/event.py` | +4 models (DietaryTag, Recipe, MealPlan, ShoppingListItem) |
| `backend/app/schemas/models.py` | +25 schemas (dietary tags, recipes, meal plans, shopping list) |
| `backend/app/routers/meals.py` | New — 20+ endpoints (tags, recipes, meal plans, shopping) |
| `backend/app/services/recipe_parser.py` | New — text parsing + URL import |
| `backend/app/jobs/shopping_list_reset.py` | New — weekly shopping list reset |
| `backend/app/main.py` | Register meals router + APScheduler job |
| `backend/tests/test_meals.py` | New — 8-10 tests |

### Frontend (new files)
| File | Description |
|---|---|
| `frontend/src/pages/MealsPage.tsx` | New — 3-tab page (Planner, Recipes, Shopping) |
| `frontend/src/components/RecipeModal.tsx` | New — add/edit recipe modal |
| `frontend/src/api/client.ts` | +mealAPI (~20 methods) |
| `frontend/src/App.tsx` | Add `/meals` route |
| `frontend/src/pages/Dashboard.tsx` | Add "Meals" nav item |
| `frontend/src/pages/DashboardHome.tsx` | Add week's dinners widget |

### Total
- **7 backend files** (4 new, 3 modified)
- **6 frontend files** (2 new, 4 modified)
- **~20 API endpoints**
- **~25 Pydantic schemas**
- **4 new DB models**
- **8-10 tests**
