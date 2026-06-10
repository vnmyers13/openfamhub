"""Meal planning router: dietary tags, recipes, meal plans, shopping list."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, delete as sa_delete, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.event import (
    DietaryTag, Recipe, MealPlan, ShoppingListItem, User,
)
from app.schemas.models import (
    DietaryTagCreate, DietaryTagUpdate, DietaryTagResponse,
    RecipeCreate, RecipeUpdate, RecipeResponse, RecipeImportRequest,
    MealPlanCreate, MealPlanUpdate, MealPlanResponse, MealPlanWeekResponse,
    ShoppingListItemCreate, ShoppingListItemUpdate, ShoppingListItemResponse,
)
from app.services.recipe_parser import parse_recipe_text, import_recipe_from_url
from pydantic import BaseModel

router = APIRouter(tags=["meals"])


class BulkMealPlanUpdate(BaseModel):
    week_start: str
    meals: list[MealPlanCreate]


# ─── Dietary Tags ───────────────────────────────────────────────────────────

@router.get("/dietary-tags", response_model=list[DietaryTagResponse])
async def list_dietary_tags(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DietaryTag).order_by(DietaryTag.name))
    tags = result.scalars().all()
    return [
        DietaryTagResponse(
            id=t.id, name=t.name, color_hex=t.color_hex,
            is_active=True, created_at=str(t.created_at),
        )
        for t in tags
    ]


@router.post("/dietary-tags", response_model=DietaryTagResponse)
async def create_dietary_tag(
    data: DietaryTagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    existing = await db.execute(
        select(DietaryTag).where(DietaryTag.name == data.name.lower())
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, f"Tag '{data.name}' already exists")

    tag = DietaryTag(name=data.name.lower(), color_hex=data.color_hex)
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return DietaryTagResponse(id=tag.id, name=tag.name, color_hex=tag.color_hex, is_active=True, created_at=str(tag.created_at))


@router.patch("/dietary-tags/{tag_id}", response_model=DietaryTagResponse)
async def update_dietary_tag(
    tag_id: str,
    data: DietaryTagUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    result = await db.execute(select(DietaryTag).where(DietaryTag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(404, "Dietary tag not found")

    if data.name is not None:
        existing = await db.execute(
            select(DietaryTag).where(DietaryTag.id != tag_id, DietaryTag.name == data.name.lower())
        )
        if existing.scalar_one_or_none():
            raise HTTPException(400, f"Tag '{data.name}' already exists")
        tag.name = data.name.lower()
    if data.color_hex is not None:
        tag.color_hex = data.color_hex

    await db.commit()
    await db.refresh(tag)
    return DietaryTagResponse(id=tag.id, name=tag.name, color_hex=tag.color_hex, is_active=True, created_at=str(tag.created_at))


@router.delete("/dietary-tags/{tag_id}")
async def delete_dietary_tag(
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_role("admin")),
):
    result = await db.execute(select(DietaryTag).where(DietaryTag.id == tag_id))
    tag = result.scalar_one_or_none()
    if not tag:
        raise HTTPException(404, "Dietary tag not found")
    await db.delete(tag)
    await db.commit()
    return {"ok": True}


# ─── Recipes ────────────────────────────────────────────────────────────────

@router.get("/recipes", response_model=list[RecipeResponse])
async def list_recipes(
    db: AsyncSession = Depends(get_db),
    tag_id: Optional[str] = Query(None, description="Filter by dietary tag ID"),
    search: Optional[str] = Query(None, description="Search by title"),
):
    query = select(Recipe).order_by(Recipe.title)

    if tag_id:
        query = query.where(Recipe.dietary_tags_json.like(f'%"{tag_id}"%'))
    if search:
        query = query.where(Recipe.title.ilike(f"%{search}%"))

    result = await db.execute(query)
    recipes = result.scalars().all()

    # Fetch tag details for each recipe
    all_tags_result = await db.execute(select(DietaryTag))
    all_tags = {t.id: {"id": t.id, "name": t.name, "color_hex": t.color_hex} for t in all_tags_result.scalars().all()}

    return [
        RecipeResponse(
            id=r.id, title=r.title, content_text=r.content_text,
            ingredients_raw=r.ingredients_raw, steps_raw=r.steps_raw,
            dietary_tag_ids=[],  # Will be parsed from JSON
            dietary_tags=[],
            prep_time_min=r.prep_time_min, cook_time_min=r.cook_time_min,
            servings=r.servings, imported_from=r.imported_from,
            created_by_id=r.created_by_id, created_at=str(r.created_at), updated_at=str(r.updated_at),
        )
        for r in recipes
    ]


@router.get("/recipes/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(404, "Recipe not found")

    # Parse dietary tag IDs from JSON
    import json
    try:
        tag_ids = json.loads(recipe.dietary_tags_json) if recipe.dietary_tags_json else []
    except (json.JSONDecodeError, TypeError):
        tag_ids = []

    # Fetch tag details
    if tag_ids:
        tags_result = await db.execute(
            select(DietaryTag).where(DietaryTag.id.in_(tag_ids))
        )
        tags = {t.id: {"id": t.id, "name": t.name, "color_hex": t.color_hex} for t in tags_result.scalars().all()}
    else:
        tags = {}

    return RecipeResponse(
        id=recipe.id, title=recipe.title, content_text=recipe.content_text,
        ingredients_raw=recipe.ingredients_raw, steps_raw=recipe.steps_raw,
        dietary_tag_ids=tag_ids,
        dietary_tags=list(tags.values()),
        prep_time_min=recipe.prep_time_min, cook_time_min=recipe.cook_time_min,
        servings=recipe.servings, imported_from=recipe.imported_from,
        created_by_id=recipe.created_by_id, created_at=str(recipe.created_at), updated_at=str(recipe.updated_at),
    )


@router.post("/recipes", response_model=RecipeResponse)
async def create_recipe(
    data: RecipeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Parse text if provided without manual ingredients
    ingredients_raw = data.ingredients_raw
    steps_raw = data.steps_raw

    if not ingredients_raw and not steps_raw and data.content_text:
        parsed = parse_recipe_text(data.content_text)
        ingredients_raw = parsed["ingredients_raw"]
        steps_raw = parsed["steps_raw"]

    import json
    recipe = Recipe(
        title=data.title,
        content_text=data.content_text,
        ingredients_raw=ingredients_raw,
        steps_raw=steps_raw,
        dietary_tags_json=json.dumps(data.dietary_tag_ids),
        prep_time_min=data.prep_time_min,
        cook_time_min=data.cook_time_min,
        servings=data.servings,
        imported_from=data.imported_from,
        created_by_id=current_user["sub"],
    )
    db.add(recipe)
    await db.commit()
    await db.refresh(recipe)

    return RecipeResponse(
        id=recipe.id, title=recipe.title, content_text=recipe.content_text,
        ingredients_raw=recipe.ingredients_raw, steps_raw=recipe.steps_raw,
        dietary_tag_ids=data.dietary_tag_ids, dietary_tags=[],
        prep_time_min=recipe.prep_time_min, cook_time_min=recipe.cook_time_min,
        servings=recipe.servings, imported_from=recipe.imported_from,
        created_by_id=recipe.created_by_id, created_at=str(recipe.created_at), updated_at=str(recipe.updated_at),
    )


@router.post("/recipes/import", response_model=RecipeResponse)
async def import_recipe(
    data: RecipeImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    if data.url:
        parsed = await import_recipe_from_url(data.url)
    elif data.text:
        parsed = parse_recipe_text(data.text)
    else:
        raise HTTPException(400, "Either url or text must be provided")

    import json
    recipe = Recipe(
        title=parsed["title"],
        content_text=parsed["content_text"],
        ingredients_raw=parsed.get("ingredients_raw"),
        steps_raw=parsed.get("steps_raw"),
        dietary_tags_json="[]",
        prep_time_min=parsed.get("prep_time_min"),
        cook_time_min=parsed.get("cook_time_min"),
        servings=parsed.get("servings"),
        imported_from=parsed.get("imported_from"),
        created_by_id=current_user["sub"],
    )
    db.add(recipe)
    await db.commit()
    await db.refresh(recipe)

    return RecipeResponse(
        id=recipe.id, title=recipe.title, content_text=recipe.content_text,
        ingredients_raw=recipe.ingredients_raw, steps_raw=recipe.steps_raw,
        dietary_tag_ids=[], dietary_tags=[],
        prep_time_min=recipe.prep_time_min, cook_time_min=recipe.cook_time_min,
        servings=recipe.servings, imported_from=recipe.imported_from,
        created_by_id=recipe.created_by_id, created_at=str(recipe.created_at), updated_at=str(recipe.updated_at),
    )


@router.patch("/recipes/{recipe_id}", response_model=RecipeResponse)
async def update_recipe(
    recipe_id: str,
    data: RecipeUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(404, "Recipe not found")

    update_data = data.model_dump(exclude_unset=True)
    if "dietary_tag_ids" in update_data:
        import json
        update_data["dietary_tags_json"] = json.dumps(update_data.pop("dietary_tag_ids"))

    for key, value in update_data.items():
        setattr(recipe, key, value)

    await db.commit()
    await db.refresh(recipe)

    return RecipeResponse(
        id=recipe.id, title=recipe.title, content_text=recipe.content_text,
        ingredients_raw=recipe.ingredients_raw, steps_raw=recipe.steps_raw,
        dietary_tag_ids=[], dietary_tags=[],
        prep_time_min=recipe.prep_time_min, cook_time_min=recipe.cook_time_min,
        servings=recipe.servings, imported_from=recipe.imported_from,
        created_by_id=recipe.created_by_id, created_at=str(recipe.created_at), updated_at=str(recipe.updated_at),
    )


@router.delete("/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(Recipe).where(Recipe.id == recipe_id))
    recipe = result.scalar_one_or_none()
    if not recipe:
        raise HTTPException(404, "Recipe not found")
    await db.delete(recipe)
    await db.commit()
    return {"ok": True}


# ─── Meal Plans ─────────────────────────────────────────────────────────────

@router.get("/plans", response_model=MealPlanWeekResponse)
async def get_meal_plan_week(
    db: AsyncSession = Depends(get_db),
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD), defaults to current Monday"),
):
    if week_start:
        start_date = datetime.strptime(week_start, "%Y-%m-%d").date()
    else:
        today = datetime.now(timezone.utc).date()
        start_date = today - timedelta(days=today.weekday())  # Monday

    end_date = start_date + timedelta(days=6)  # Sunday

    result = await db.execute(
        select(MealPlan).where(
            MealPlan.date >= str(start_date),
            MealPlan.date <= str(end_date),
        ).order_by(MealPlan.date, MealPlan.meal_type)
    )
    plans = result.scalars().all()

    # Fetch recipe details for each plan that has one
    recipe_ids = list(set(p.recipe_id for p in plans if p.recipe_id))
    recipes = {}
    if recipe_ids:
        recip_result = await db.execute(select(Recipe).where(Recipe.id.in_(recipe_ids)))
        recipes = {r.id: {"id": r.id, "title": r.title} for r in recip_result.scalars().all()}

    meals = []
    for p in plans:
        meal = MealPlanResponse(
            id=p.id, meal_type=p.meal_type, date=p.date,
            recipe_id=p.recipe_id, title=p.title, notes=p.notes,
            recipe=recipes.get(p.recipe_id),
            created_at=str(p.created_at), updated_at=str(p.updated_at),
        )
        meals.append(meal)

    return MealPlanWeekResponse(
        week_start=str(start_date),
        week_end=str(end_date),
        meals=meals,
    )


@router.post("/plans", response_model=MealPlanResponse)
async def create_meal_plan(
    data: MealPlanCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    plan = MealPlan(
        meal_type=data.meal_type,
        date=data.date,
        recipe_id=data.recipe_id,
        title=data.title,
        notes=data.notes,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)

    # Fetch recipe if present
    recipe = None
    if plan.recipe_id:
        r_result = await db.execute(select(Recipe).where(Recipe.id == plan.recipe_id))
        r = r_result.scalar_one_or_none()
        if r:
            recipe = {"id": r.id, "title": r.title}

    return MealPlanResponse(
        id=plan.id, meal_type=plan.meal_type, date=plan.date,
        recipe_id=plan.recipe_id, title=plan.title, notes=plan.notes,
        recipe=recipe, created_at=str(plan.created_at), updated_at=str(plan.updated_at),
    )


@router.patch("/plans/{plan_id}", response_model=MealPlanResponse)
async def update_meal_plan(
    plan_id: str,
    data: MealPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(MealPlan).where(MealPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Meal plan entry not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(plan, key, value)

    await db.commit()
    await db.refresh(plan)

    recipe = None
    if plan.recipe_id:
        r_result = await db.execute(select(Recipe).where(Recipe.id == plan.recipe_id))
        r = r_result.scalar_one_or_none()
        if r:
            recipe = {"id": r.id, "title": r.title}

    return MealPlanResponse(
        id=plan.id, meal_type=plan.meal_type, date=plan.date,
        recipe_id=plan.recipe_id, title=plan.title, notes=plan.notes,
        recipe=recipe, created_at=str(plan.created_at), updated_at=str(plan.updated_at),
    )


@router.delete("/plans/{plan_id}")
async def delete_meal_plan(
    plan_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(MealPlan).where(MealPlan.id == plan_id))
    plan = result.scalar_one_or_none()
    if not plan:
        raise HTTPException(404, "Meal plan entry not found")
    await db.delete(plan)
    await db.commit()
    return {"ok": True}


@router.put("/plans/bulk", response_model=list[MealPlanResponse])
async def bulk_update_meal_plans(
    data: BulkMealPlanUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Bulk create/update meal plans for a week."""
    results = []
    for meal_data in data.meals:
        existing = await db.execute(
            select(MealPlan).where(
                MealPlan.date == meal_data.date,
                MealPlan.meal_type == meal_data.meal_type,
            )
        )
        plan = existing.scalar_one_or_none()
        
        if plan:
            plan.meal_type = meal_data.meal_type
            plan.recipe_id = meal_data.recipe_id
            plan.title = meal_data.title
            plan.notes = meal_data.notes
        else:
            plan = MealPlan(
                meal_type=meal_data.meal_type,
                date=meal_data.date,
                recipe_id=meal_data.recipe_id,
                title=meal_data.title,
                notes=meal_data.notes,
            )
            db.add(plan)
        results.append(plan)
    
    await db.commit()
    
    recipe_ids = list(set(p.recipe_id for p in results if p.recipe_id))
    recipes = {}
    if recipe_ids:
        r_result = await db.execute(select(Recipe).where(Recipe.id.in_(recipe_ids)))
        recipes = {r.id: {"id": r.id, "title": r.title} for r in r_result.scalars().all()}
    
    return [
        MealPlanResponse(
            id=p.id, meal_type=p.meal_type, date=p.date,
            recipe_id=p.recipe_id, title=p.title, notes=p.notes,
            recipe=recipes.get(p.recipe_id),
            created_at=str(p.created_at), updated_at=str(p.updated_at),
        )
        for p in results
    ]


# ─── Shopping List ──────────────────────────────────────────────────────────

def _get_week_start(date_str: str) -> str:
    """Get the Monday of the week for a given date string."""
    d = datetime.strptime(date_str, "%Y-%m-%d").date()
    monday = d - timedelta(days=d.weekday())
    return str(monday)


@router.get("/shopping-list", response_model=list[ShoppingListItemResponse])
async def get_shopping_list(
    db: AsyncSession = Depends(get_db),
    week_start: Optional[str] = Query(None, description="Week start date (YYYY-MM-DD), defaults to current Monday"),
):
    if week_start:
        ws = week_start
    else:
        today = datetime.now(timezone.utc).date()
        ws = str(today - timedelta(days=today.weekday()))

    result = await db.execute(
        select(ShoppingListItem)
        .where(ShoppingListItem.week_start_date == ws)
        .order_by(ShoppingListItem.is_checked, ShoppingListItem.item)
    )
    items = result.scalars().all()

    return [
        ShoppingListItemResponse(
            id=i.id, item=i.item, quantity=i.quantity,
            is_checked=i.is_checked, is_persistent=i.is_persistent,
            source=i.source, meal_plan_id=i.meal_plan_id,
            created_by_id=i.created_by_id, week_start_date=i.week_start_date,
            checked_at=i.checked_at, created_at=i.created_at,
        )
        for i in items
    ]


@router.post("/shopping-list", response_model=ShoppingListItemResponse)
async def add_shopping_item(
    data: ShoppingListItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    today = datetime.now(timezone.utc).date()
    ws = str(today - timedelta(days=today.weekday()))

    item = ShoppingListItem(
        item=data.item,
        quantity=data.quantity,
        is_checked=False,
        is_persistent=data.is_persistent,
        source="manual",
        meal_plan_id=data.meal_plan_id,
        created_by_id=current_user["sub"],
        week_start_date=ws,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)

    return ShoppingListItemResponse(
        id=item.id, item=item.item, quantity=item.quantity,
        is_checked=item.is_checked, is_persistent=item.is_persistent,
        source=item.source, meal_plan_id=item.meal_plan_id,
        created_by_id=item.created_by_id, week_start_date=item.week_start_date,
        checked_at=str(item.checked_at) if item.checked_at else None, created_at=str(item.created_at),
    )


@router.post("/shopping-list/regenerate")
async def regenerate_shopping_list(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Regenerate shopping list from current week's meal plans."""
    today = datetime.now(timezone.utc).date()
    ws = today - timedelta(days=today.weekday())
    we = ws + timedelta(days=6)

    # Delete non-persistent items for current week
    await db.execute(
        sa_delete(ShoppingListItem).where(
            ShoppingListItem.week_start_date == str(ws),
            ShoppingListItem.is_persistent == False,
        )
    )

    # Get all meal plans for current week
    result = await db.execute(
        select(MealPlan).where(
            MealPlan.date >= str(ws),
            MealPlan.date <= str(we),
        )
    )
    plans = result.scalars().all()

    # Extract ingredients from recipes
    import re
    ingredient_map: dict[str, str] = {}  # item -> quantity

    for plan in plans:
        if plan.recipe_id:
            r_result = await db.execute(select(Recipe).where(Recipe.id == plan.recipe_id))
            recipe = r_result.scalar_one_or_none()
            if recipe and recipe.ingredients_raw:
                for line in recipe.ingredients_raw.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    # Extract item name and quantity
                    match = re.match(r'^(\d+[\d./]*\s*\S*\s*(?:cups?|tbsp|tsp|oz|lb|g|kg|ml|L|pinch|slice|piece|can|bunch|bag|box|package|medium|large|small|whole|\w+))\s+(.+)$', line, re.IGNORECASE)
                    if match:
                        qty = match.group(1)
                        item = match.group(2).strip().lower()
                    else:
                        # Try simpler: everything after first word(s) with quantity
                        match2 = re.match(r'^(\d+[\d./]*\s*\S*\s*\S+)\s+(.+)$', line)
                        if match2:
                            qty = match2.group(1)
                            item = match2.group(2).strip().lower()
                        else:
                            qty = ""
                            item = line.lower()

                    # Normalize item name for dedup
                    normalized = re.sub(r'[,.]', '', item).strip()
                    if normalized in ingredient_map:
                        ingredient_map[normalized] = f"{ingredient_map[normalized]} / {qty}"
                    else:
                        ingredient_map[normalized] = qty

    # Create shopping list items
    for item_name, quantity in ingredient_map.items():
        item = ShoppingListItem(
            item=item_name,
            quantity=quantity,
            is_checked=False,
            is_persistent=False,
            source="meal_generated",
            meal_plan_id=None,
            created_by_id=current_user["sub"],
            week_start_date=str(ws),
        )
        db.add(item)

    await db.commit()

    return {"ok": True, "items_created": len(ingredient_map)}


@router.patch("/shopping-list/{item_id}", response_model=ShoppingListItemResponse)
async def update_shopping_item(
    item_id: str,
    data: ShoppingListItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(ShoppingListItem).where(ShoppingListItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Shopping list item not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    # Set checked_at when checking
    if data.is_checked is not None:
        item.checked_at = datetime.now(timezone.utc).isoformat() if data.is_checked else None

    await db.commit()
    await db.refresh(item)

    return ShoppingListItemResponse(
        id=item.id, item=item.item, quantity=item.quantity,
        is_checked=item.is_checked, is_persistent=item.is_persistent,
        source=item.source, meal_plan_id=item.meal_plan_id,
        created_by_id=item.created_by_id, week_start_date=item.week_start_date,
        checked_at=str(item.checked_at) if item.checked_at else None, created_at=str(item.created_at),
    )


@router.delete("/shopping-list/{item_id}")
async def delete_shopping_item(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    result = await db.execute(select(ShoppingListItem).where(ShoppingListItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, "Shopping list item not found")
    await db.delete(item)
    await db.commit()
    return {"ok": True}


@router.post("/shopping-list/clear-week")
async def clear_week_shopping_list(
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    week_start: Optional[str] = Query(None, description="Week to clear (YYYY-MM-DD), defaults to current week"),
):
    """Clear all non-persistent shopping list items for a week."""
    if week_start:
        ws = week_start
    else:
        today = datetime.now(timezone.utc).date()
        ws = str(today - timedelta(days=today.weekday()))
    
    result = await db.execute(
        sa_delete(ShoppingListItem).where(
            ShoppingListItem.week_start_date == ws,
            ShoppingListItem.is_persistent == False,
        )
    )
    await db.commit()
    return {"ok": True, "items_deleted": result.rowcount}
