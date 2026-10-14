"""Phase 7: recipes, the weekly meal plan, the shopping list and the pantry.

Plan days are plain family-local `Date`s, like chore due dates.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Float, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


def _id() -> str:
    return str(uuid.uuid4())


class Recipe(Base):
    __tablename__ = "recipes"
    __table_args__ = (Index("ix_recipes_family", "family_id", "is_deleted"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    servings: Mapped[int] = mapped_column(Integer, nullable=True)
    prep_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    cook_minutes: Mapped[int] = mapped_column(Integer, nullable=True)
    ingredients: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # one line each
    steps: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tags: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # dietary tags etc., lowercase
    source_url: Mapped[str] = mapped_column(String(2048), nullable=True)
    video_url: Mapped[str] = mapped_column(String(2048), nullable=True)
    catalog_key: Mapped[str] = mapped_column(String(64), nullable=True)  # copied from the built-in catalog
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class MealPlanEntry(Base):
    """What's planned for one meal slot on one day: a recipe, or just a title
    ("Leftovers", "Pizza night"). The title is kept so a deleted recipe
    doesn't leave a hole in past weeks."""

    __tablename__ = "meal_plan_entries"
    __table_args__ = (UniqueConstraint("family_id", "day", "slot", name="uq_meal_plan_slot"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    slot: Mapped[str] = mapped_column(String(16), nullable=False)  # breakfast|lunch|dinner|snack
    recipe_id: Mapped[str] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    note: Mapped[str] = mapped_column(String(256), nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class ShoppingItem(Base):
    """A shopping-list line. Items made from the meal plan remember the recipe
    and week they came from, so regenerating replaces only those. Checked
    items are archived (kept as purchase history) by the weekly reset."""

    __tablename__ = "shopping_items"
    __table_args__ = (Index("ix_shopping_family", "family_id", "archived_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    quantity: Mapped[str] = mapped_column(String(64), nullable=True)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")  # manual|plan|pantry
    recipe_id: Mapped[str] = mapped_column(String, nullable=True)
    recipe_title: Mapped[str] = mapped_column(String(128), nullable=True)
    week_start: Mapped[date] = mapped_column(Date, nullable=True)
    checked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    checked_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    checked_by: Mapped[str] = mapped_column(String, nullable=True)
    archived_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class PantryItem(Base):
    """Something on hand. Low when quantity <= low_at; flags are computed."""

    __tablename__ = "pantry_items"
    __table_args__ = (Index("ix_pantry_family", "family_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[float] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(32), nullable=True)
    low_at: Mapped[float] = mapped_column(Float, nullable=True)
    expires_on: Mapped[date] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
