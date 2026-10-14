"""Phase 7 rules shared by the meals API and the weekly shopping reset.

- Weeks start on Monday, in the family's timezone (like allowance).
- Regenerating the shopping list from a week's plan is idempotent: it adds
  missing ingredient lines, drops unchecked lines whose recipe left the plan,
  and never touches checked (bought) items or items people added themselves.
- The weekly reset archives bought items (they stay as purchase history,
  never deleted) and drops unbought plan items from past weeks.
"""
import json
import re
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.family import Family
from app.models.meals import MealPlanEntry, PantryItem, Recipe, ShoppingItem
from app.services.rewards import week_start, zone_for

EXPIRES_SOON_DAYS = 3
CATALOG_FILE = Path(__file__).resolve().parent.parent / "data" / "recipe_catalog.json"


@lru_cache(maxsize=1)
def catalog() -> tuple[dict, ...]:
    return tuple(json.loads(CATALOG_FILE.read_text(encoding="utf-8")))


def catalog_entry(key: str) -> Optional[dict]:
    return next((r for r in catalog() if r["key"] == key), None)


# ---- shopping list from the plan ------------------------------------------------

async def regenerate_shopping(db: AsyncSession, family_id: str, week: date, user_id: Optional[str]) -> tuple[int, int]:
    """Make the week's plan-generated items match the week's planned recipes."""
    entries = (await db.execute(
        select(MealPlanEntry.recipe_id)
        .where(MealPlanEntry.family_id == family_id, MealPlanEntry.day >= week,
               MealPlanEntry.day < week + timedelta(days=7), MealPlanEntry.recipe_id.is_not(None))
    )).scalars().all()
    times: dict[str, int] = {}
    for rid in entries:
        times[rid] = times.get(rid, 0) + 1
    recipes = {r.id: r for r in (await db.execute(
        select(Recipe).where(Recipe.family_id == family_id, Recipe.id.in_(list(times) or [""]),
                             Recipe.is_deleted == False)  # noqa: E712
    )).scalars().all()}

    wanted: dict[tuple[str, str], tuple[Recipe, str, int]] = {}
    for rid, recipe in recipes.items():
        for line in recipe.ingredients or []:
            key = (rid, line.strip().lower())
            if key[1] and key not in wanted:
                wanted[key] = (recipe, line.strip(), times[rid])

    existing = (await db.execute(
        select(ShoppingItem).where(ShoppingItem.family_id == family_id, ShoppingItem.source == "plan",
                                   ShoppingItem.week_start == week, ShoppingItem.archived_at.is_(None))
    )).scalars().all()
    have = {(i.recipe_id, i.name.strip().lower()): i for i in existing}

    removed = 0
    for key, item in have.items():
        if key not in wanted and not item.checked:
            await db.delete(item)
            removed += 1
        elif key in wanted and not item.checked:
            item.quantity = _times_label(wanted[key][2])
    added = 0
    for key, (recipe, line, n) in wanted.items():
        if key not in have:
            db.add(ShoppingItem(family_id=family_id, name=line[:256], quantity=_times_label(n), source="plan",
                                recipe_id=recipe.id, recipe_title=recipe.title, week_start=week,
                                created_by=user_id, created_at=datetime.now(timezone.utc)))
            added += 1
    await db.flush()
    return added, removed


def _times_label(n: int) -> Optional[str]:
    return f"×{n}" if n > 1 else None


# ---- pantry ---------------------------------------------------------------------

def pantry_flags(item: PantryItem, today: date) -> dict:
    low = item.quantity is not None and item.low_at is not None and item.quantity <= item.low_at
    expired = item.expires_on is not None and item.expires_on < today
    soon = item.expires_on is not None and today <= item.expires_on <= today + timedelta(days=EXPIRES_SOON_DAYS)
    return {"is_low": low, "expired": expired, "expires_soon": soon}


def pantry_match(name: str, pantry: list[PantryItem], today: date) -> Optional[str]:
    """A usable pantry item whose name appears as a word in `name` ("2 cups rice" ↔ "Rice")."""
    text = name.lower()
    for p in sorted(pantry, key=lambda p: -len(p.name)):
        flags = pantry_flags(p, today)
        if flags["is_low"] or flags["expired"] or (p.quantity is not None and p.quantity <= 0):
            continue
        if re.search(rf"\b{re.escape(p.name.lower().strip())}s?\b", text):
            return p.name
    return None


# ---- weekly reset ---------------------------------------------------------------

async def weekly_reset(db: AsyncSession, family: Family, now: datetime) -> tuple[int, int]:
    """Archive items bought before this week; drop unbought plan items from past
    weeks. Manual and pantry items still to buy stay. Idempotent."""
    zone = zone_for(family.timezone)
    monday = week_start(now.astimezone(zone).date())
    monday_utc = datetime.combine(monday, time(0), zone).astimezone(timezone.utc)
    archived = (await db.execute(
        update(ShoppingItem)
        .where(ShoppingItem.family_id == family.id, ShoppingItem.checked == True,  # noqa: E712
               ShoppingItem.archived_at.is_(None), ShoppingItem.checked_at < monday_utc)
        .values(archived_at=now)
        .execution_options(synchronize_session=False)
    )).rowcount
    dropped = (await db.execute(
        delete(ShoppingItem)
        .where(ShoppingItem.family_id == family.id, ShoppingItem.checked == False,  # noqa: E712
               ShoppingItem.source == "plan", ShoppingItem.week_start < monday)
        .execution_options(synchronize_session=False)
    )).rowcount
    return archived or 0, dropped or 0
