"""Meals (Phase 7): recipes, the built-in catalog, the weekly plan, the
shopping list and the pantry.

Everything requires a signed-in family member and is scoped to their family;
viewers can read but not change anything. (v0.29 served recipes, plans and
the shopping list without auth.)
"""
from datetime import date, datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.events import queue_event
from app.core.security import get_current_user
from app.models.meals import MealPlanEntry, PantryItem, Recipe, ShoppingItem
from app.models.user import User
from app.schemas.meals import (
    SLOTS, CatalogRecipe, PantryCreate, PantryResponse, PantryUpdate, PlanEntry, PlanSlotSet, PlanWeek, PlanWeekSet,
    RecipeCreate, RecipeResponse, RecipeUpdate, RegenerateResult, ShoppingCreate, ShoppingResponse, ShoppingUpdate,
    Slot,
)
from app.services import meals as svc
from app.services.rewards import family_zone, local_today, week_start

router = APIRouter()


# ---- helpers ---------------------------------------------------------------

def editor(user: User = Depends(get_current_user)) -> User:
    if user.role == "viewer":
        raise HTTPException(status_code=403, detail="Viewers can't change meals")
    return user


def changed(db: AsyncSession) -> None:
    queue_event(db, "meals_updated", {})


async def today_for(db: AsyncSession, family_id: str) -> date:
    return local_today(await family_zone(db, family_id))


def to_recipe(r: Recipe) -> RecipeResponse:
    return RecipeResponse(id=r.id, title=r.title, description=r.description, servings=r.servings,
                          prep_minutes=r.prep_minutes, cook_minutes=r.cook_minutes, ingredients=r.ingredients or [],
                          steps=r.steps or [], tags=r.tags or [], source_url=r.source_url, video_url=r.video_url,
                          catalog_key=r.catalog_key, created_by=r.created_by)


async def load_recipe(db: AsyncSession, family_id: str, recipe_id: str) -> Recipe:
    recipe = await db.get(Recipe, recipe_id)
    if recipe is None or recipe.family_id != family_id or recipe.is_deleted:
        raise HTTPException(status_code=404, detail="Recipe not found")
    return recipe


async def load_item(db: AsyncSession, model, family_id: str, item_id: str, what: str):
    row = await db.get(model, item_id)
    if row is None or row.family_id != family_id:
        raise HTTPException(status_code=404, detail=f"{what} not found")
    return row


# ---- recipes ---------------------------------------------------------------

@router.get("/recipes", response_model=List[RecipeResponse])
async def list_recipes(q: Optional[str] = None, tag: Optional[str] = None, db: AsyncSession = Depends(get_db),
                       user: User = Depends(get_current_user)):
    query = select(Recipe).where(Recipe.family_id == user.family_id, Recipe.is_deleted == False)  # noqa: E712
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        query = query.where(or_(func.lower(Recipe.title).like(like), func.lower(Recipe.description).like(like)))
    rows = (await db.execute(query.order_by(func.lower(Recipe.title)))).scalars().all()
    if tag:
        rows = [r for r in rows if tag.strip().lower() in (r.tags or [])]
    return [to_recipe(r) for r in rows]


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(recipe_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    return to_recipe(await load_recipe(db, user.family_id, recipe_id))


@router.post("/recipes", response_model=RecipeResponse, status_code=201)
async def create_recipe(data: RecipeCreate, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    recipe = Recipe(family_id=user.family_id, created_by=user.id, **data.model_dump())
    db.add(recipe)
    await db.flush()
    changed(db)
    return to_recipe(recipe)


@router.patch("/recipes/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(recipe_id: str, data: RecipeUpdate, db: AsyncSession = Depends(get_db),
                        user: User = Depends(editor)):
    recipe = await load_recipe(db, user.family_id, recipe_id)
    for key, value in data.model_dump(exclude_unset=True).items():
        if value is None and key in ("title", "ingredients", "steps", "tags"):
            continue
        setattr(recipe, key, value)
    await db.flush()
    await db.refresh(recipe)
    changed(db)
    return to_recipe(recipe)


@router.delete("/recipes/{recipe_id}")
async def delete_recipe(recipe_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    recipe = await load_recipe(db, user.family_id, recipe_id)
    recipe.is_deleted = True  # planned meals keep their title
    await db.flush()
    changed(db)
    return {"message": "Recipe deleted"}


# ---- catalog ---------------------------------------------------------------

@router.get("/catalog", response_model=List[CatalogRecipe])
async def list_catalog(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    added = set((await db.execute(
        select(Recipe.catalog_key).where(Recipe.family_id == user.family_id, Recipe.is_deleted == False,  # noqa: E712
                                         Recipe.catalog_key.is_not(None))
    )).scalars().all())
    return [CatalogRecipe(**r, added=r["key"] in added) for r in svc.catalog()]


@router.post("/catalog/{key}", response_model=RecipeResponse, status_code=201)
async def add_from_catalog(key: str, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    entry = svc.catalog_entry(key)
    if entry is None:
        raise HTTPException(status_code=404, detail="Not in the catalog")
    exists = (await db.execute(
        select(Recipe.id).where(Recipe.family_id == user.family_id, Recipe.catalog_key == key,
                                Recipe.is_deleted == False)  # noqa: E712
    )).first()
    if exists:
        raise HTTPException(status_code=409, detail="That recipe is already in your recipes")
    fields = {k: v for k, v in entry.items() if k != "key"}
    recipe = Recipe(family_id=user.family_id, created_by=user.id, catalog_key=key,
                    **{**{"source_url": None, "video_url": None}, **fields})
    db.add(recipe)
    await db.flush()
    changed(db)
    return to_recipe(recipe)


# ---- meal plan ---------------------------------------------------------------

def _monday(start: Optional[date], today: date) -> date:
    return week_start(start or today)


def to_entry(e: MealPlanEntry) -> PlanEntry:
    return PlanEntry(id=e.id, day=e.day, slot=e.slot, recipe_id=e.recipe_id, title=e.title, note=e.note)


async def _plan_week(db: AsyncSession, family_id: str, monday: date) -> PlanWeek:
    rows = (await db.execute(
        select(MealPlanEntry)
        .where(MealPlanEntry.family_id == family_id, MealPlanEntry.day >= monday,
               MealPlanEntry.day < monday + timedelta(days=7))
        .order_by(MealPlanEntry.day)
    )).scalars().all()
    rows = sorted(rows, key=lambda e: (e.day, SLOTS.index(e.slot) if e.slot in SLOTS else 9))
    return PlanWeek(week_start=monday, days=[monday + timedelta(days=i) for i in range(7)],
                    entries=[to_entry(e) for e in rows])


async def _slot_values(db: AsyncSession, family_id: str, data: PlanSlotSet) -> tuple[Optional[str], str]:
    if data.recipe_id:
        recipe = await load_recipe(db, family_id, data.recipe_id)
        return recipe.id, (data.title or "").strip() or recipe.title
    return None, data.title.strip()


@router.get("/plan", response_model=PlanWeek)
async def get_plan(start: Optional[date] = None, db: AsyncSession = Depends(get_db),
                   user: User = Depends(get_current_user)):
    return await _plan_week(db, user.family_id, _monday(start, await today_for(db, user.family_id)))


# Registered before /plan/{day}/{slot}, which would otherwise match "week" as a day.
@router.put("/plan/week/{monday}", response_model=PlanWeek)
async def set_week(monday: date, data: PlanWeekSet, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    """Replace the whole week: slots not in `entries` are cleared."""
    if monday.weekday() != 0:
        raise HTTPException(status_code=400, detail="A week starts on a Monday")
    seen = set()
    resolved = []
    for e in data.entries:
        if not monday <= e.day < monday + timedelta(days=7):
            raise HTTPException(status_code=400, detail=f"{e.day} isn't in the week of {monday}")
        if (e.day, e.slot) in seen:
            raise HTTPException(status_code=400, detail=f"{e.day} {e.slot} is listed twice")
        seen.add((e.day, e.slot))
        resolved.append((e, *(await _slot_values(db, user.family_id, e))))
    old = (await db.execute(
        select(MealPlanEntry).where(MealPlanEntry.family_id == user.family_id, MealPlanEntry.day >= monday,
                                    MealPlanEntry.day < monday + timedelta(days=7))
    )).scalars().all()
    for row in old:
        await db.delete(row)
    await db.flush()
    for e, recipe_id, title in resolved:
        db.add(MealPlanEntry(family_id=user.family_id, day=e.day, slot=e.slot, recipe_id=recipe_id, title=title,
                             note=e.note, created_by=user.id))
    await db.flush()
    changed(db)
    return await _plan_week(db, user.family_id, monday)


@router.put("/plan/{day}/{slot}", response_model=PlanEntry)
async def set_slot(day: date, slot: Slot, data: PlanSlotSet, db: AsyncSession = Depends(get_db),
                   user: User = Depends(editor)):
    recipe_id, title = await _slot_values(db, user.family_id, data)
    entry = (await db.execute(
        select(MealPlanEntry).where(MealPlanEntry.family_id == user.family_id, MealPlanEntry.day == day,
                                    MealPlanEntry.slot == slot)
    )).scalar_one_or_none()
    if entry is None:
        entry = MealPlanEntry(family_id=user.family_id, day=day, slot=slot, created_by=user.id, title=title)
        db.add(entry)
    entry.recipe_id, entry.title, entry.note = recipe_id, title, data.note
    await db.flush()
    changed(db)
    return to_entry(entry)


@router.delete("/plan/{day}/{slot}")
async def clear_slot(day: date, slot: Slot, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    entry = (await db.execute(
        select(MealPlanEntry).where(MealPlanEntry.family_id == user.family_id, MealPlanEntry.day == day,
                                    MealPlanEntry.slot == slot)
    )).scalar_one_or_none()
    if entry is not None:
        await db.delete(entry)
        await db.flush()
        changed(db)
    return {"message": "Cleared"}


# ---- shopping list ---------------------------------------------------------------

def to_item(i: ShoppingItem, pantry: list[PantryItem], today: date) -> ShoppingResponse:
    return ShoppingResponse(id=i.id, name=i.name, quantity=i.quantity, source=i.source, recipe_id=i.recipe_id,
                            recipe_title=i.recipe_title, week_start=i.week_start, checked=i.checked,
                            checked_at=i.checked_at, checked_by=i.checked_by,
                            in_pantry=None if i.checked else svc.pantry_match(i.name, pantry, today))


async def _pantry(db: AsyncSession, family_id: str) -> list[PantryItem]:
    return list((await db.execute(select(PantryItem).where(PantryItem.family_id == family_id))).scalars().all())


@router.get("/shopping", response_model=List[ShoppingResponse])
async def shopping_list(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(ShoppingItem).where(ShoppingItem.family_id == user.family_id, ShoppingItem.archived_at.is_(None))
    )).scalars().all()
    rows = sorted(rows, key=lambda i: (i.checked, (i.recipe_title or "").lower(), i.name.lower()))
    pantry, today = await _pantry(db, user.family_id), await today_for(db, user.family_id)
    return [to_item(i, pantry, today) for i in rows]


@router.get("/shopping/history", response_model=List[ShoppingResponse])
async def shopping_history(limit: int = Query(100, ge=1, le=500), db: AsyncSession = Depends(get_db),
                           user: User = Depends(get_current_user)):
    rows = (await db.execute(
        select(ShoppingItem)
        .where(ShoppingItem.family_id == user.family_id, ShoppingItem.archived_at.is_not(None))
        .order_by(ShoppingItem.checked_at.desc()).limit(limit)
    )).scalars().all()
    return [to_item(i, [], date.min) for i in rows]


@router.post("/shopping", response_model=ShoppingResponse, status_code=201)
async def add_item(data: ShoppingCreate, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    item = ShoppingItem(family_id=user.family_id, name=data.name.strip(), quantity=(data.quantity or "").strip() or None,
                        source="manual", created_by=user.id, created_at=datetime.now(timezone.utc))
    db.add(item)
    await db.flush()
    changed(db)
    return to_item(item, await _pantry(db, user.family_id), await today_for(db, user.family_id))


@router.patch("/shopping/{item_id}", response_model=ShoppingResponse)
async def update_item(item_id: str, data: ShoppingUpdate, db: AsyncSession = Depends(get_db),
                      user: User = Depends(editor)):
    item = await load_item(db, ShoppingItem, user.family_id, item_id, "Item")
    if item.archived_at is not None:
        raise HTTPException(status_code=409, detail="That item is in the purchase history now")
    if data.name is not None:
        item.name = data.name.strip()
    if "quantity" in data.model_fields_set:
        item.quantity = (data.quantity or "").strip() or None
    if data.checked is not None and data.checked != item.checked:
        item.checked = data.checked
        item.checked_at = datetime.now(timezone.utc) if data.checked else None
        item.checked_by = user.id if data.checked else None
    await db.flush()
    changed(db)
    return to_item(item, await _pantry(db, user.family_id), await today_for(db, user.family_id))


@router.delete("/shopping/{item_id}")
async def delete_item(item_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    item = await load_item(db, ShoppingItem, user.family_id, item_id, "Item")
    await db.delete(item)
    await db.flush()
    changed(db)
    return {"message": "Removed"}


@router.post("/shopping/from-plan", response_model=RegenerateResult)
async def shopping_from_plan(start: Optional[date] = None, db: AsyncSession = Depends(get_db),
                             user: User = Depends(editor)):
    monday = _monday(start, await today_for(db, user.family_id))
    added, removed = await svc.regenerate_shopping(db, user.family_id, monday, user.id)
    changed(db)
    return RegenerateResult(added=added, removed=removed, week_start=monday)


@router.post("/shopping/clear-checked")
async def clear_checked(db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    """Move everything ticked off into the purchase history now."""
    now = datetime.now(timezone.utc)
    rows = (await db.execute(
        select(ShoppingItem).where(ShoppingItem.family_id == user.family_id, ShoppingItem.checked == True,  # noqa: E712
                                   ShoppingItem.archived_at.is_(None))
    )).scalars().all()
    for row in rows:
        row.archived_at = now
    await db.flush()
    changed(db)
    return {"archived": len(rows)}


# ---- pantry ----------------------------------------------------------------------

def to_pantry(p: PantryItem, today: date) -> PantryResponse:
    return PantryResponse(id=p.id, name=p.name, quantity=p.quantity, unit=p.unit, low_at=p.low_at,
                          expires_on=p.expires_on, **svc.pantry_flags(p, today))


@router.get("/pantry", response_model=List[PantryResponse])
async def list_pantry(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    today = await today_for(db, user.family_id)
    rows = sorted(await _pantry(db, user.family_id), key=lambda p: p.name.lower())
    return [to_pantry(p, today) for p in rows]


@router.post("/pantry", response_model=PantryResponse, status_code=201)
async def add_pantry(data: PantryCreate, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    item = PantryItem(family_id=user.family_id, **{**data.model_dump(), "name": data.name.strip()})
    db.add(item)
    await db.flush()
    changed(db)
    return to_pantry(item, await today_for(db, user.family_id))


@router.patch("/pantry/{item_id}", response_model=PantryResponse)
async def update_pantry(item_id: str, data: PantryUpdate, db: AsyncSession = Depends(get_db),
                        user: User = Depends(editor)):
    item = await load_item(db, PantryItem, user.family_id, item_id, "Pantry item")
    for key, value in data.model_dump(exclude_unset=True).items():
        if key == "name" and value is None:
            continue
        setattr(item, key, value.strip() if key == "name" else value)
    await db.flush()
    await db.refresh(item)
    changed(db)
    return to_pantry(item, await today_for(db, user.family_id))


@router.delete("/pantry/{item_id}")
async def delete_pantry(item_id: str, db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    item = await load_item(db, PantryItem, user.family_id, item_id, "Pantry item")
    await db.delete(item)
    await db.flush()
    changed(db)
    return {"message": "Removed"}


@router.post("/pantry/restock")
async def restock(db: AsyncSession = Depends(get_db), user: User = Depends(editor)):
    """Put every low or expired pantry item on the shopping list (once)."""
    today = await today_for(db, user.family_id)
    on_list = {n.strip().lower() for n in (await db.execute(
        select(ShoppingItem.name).where(ShoppingItem.family_id == user.family_id, ShoppingItem.checked == False,  # noqa: E712
                                        ShoppingItem.archived_at.is_(None))
    )).scalars().all()}
    added = 0
    for p in await _pantry(db, user.family_id):
        flags = svc.pantry_flags(p, today)
        if (flags["is_low"] or flags["expired"]) and p.name.strip().lower() not in on_list:
            db.add(ShoppingItem(family_id=user.family_id, name=p.name, source="pantry", created_by=user.id,
                                created_at=datetime.now(timezone.utc)))
            on_list.add(p.name.strip().lower())
            added += 1
    await db.flush()
    if added:
        changed(db)
    return {"added": added}
