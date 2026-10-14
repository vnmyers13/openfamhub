from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

Slot = Literal["breakfast", "lunch", "dinner", "snack"]
SLOTS = ("breakfast", "lunch", "dinner", "snack")


def web_url(v: Optional[str]) -> Optional[str]:
    """Links are shown to the family, so only http(s) (never javascript: etc.)."""
    if v is None or not v.strip():
        return None
    v = v.strip()
    if not v.lower().startswith(("http://", "https://")) or len(v) > 2048:
        raise ValueError("must be an http(s) link")
    return v


def _lines(v: Optional[List[str]], limit: int = 200) -> Optional[List[str]]:
    if v is None:
        return v
    out = [s.strip()[:500] for s in v if s and s.strip()]
    if len(out) > limit:
        raise ValueError(f"at most {limit} lines")
    return out


def _tags(v: Optional[List[str]]) -> Optional[List[str]]:
    if v is None:
        return v
    out: List[str] = []
    for t in v:
        t = t.strip().lower()[:32]
        if t and t not in out:
            out.append(t)
    return out[:12]


# ---- recipes ----------------------------------------------------------------

class _RecipeFields(BaseModel):
    description: Optional[str] = Field(None, max_length=1000)
    servings: Optional[int] = Field(None, ge=1, le=100)
    prep_minutes: Optional[int] = Field(None, ge=0, le=10000)
    cook_minutes: Optional[int] = Field(None, ge=0, le=10000)
    ingredients: Optional[List[str]] = None
    steps: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    source_url: Optional[str] = None
    video_url: Optional[str] = None

    @field_validator("source_url", "video_url")
    @classmethod
    def links(cls, v):
        return web_url(v)

    @field_validator("ingredients", "steps")
    @classmethod
    def lines(cls, v):
        return _lines(v)

    @field_validator("tags")
    @classmethod
    def tag_list(cls, v):
        return _tags(v)

    @field_validator("title", check_fields=False)
    @classmethod
    def title_length(cls, v):
        if v is not None and not 1 <= len(v.strip()) <= 128:
            raise ValueError("title must be 1-128 characters")
        return v.strip() if v is not None else v


class RecipeCreate(_RecipeFields):
    title: str
    ingredients: List[str] = []
    steps: List[str] = []
    tags: List[str] = []


class RecipeUpdate(_RecipeFields):
    title: Optional[str] = None


class RecipeDraft(BaseModel):
    """What an import found; the user reviews it before saving."""
    title: str
    description: Optional[str] = None
    servings: Optional[int] = None
    prep_minutes: Optional[int] = None
    cook_minutes: Optional[int] = None
    ingredients: List[str] = []
    steps: List[str] = []
    tags: List[str] = []
    source_url: Optional[str] = None
    video_url: Optional[str] = None


class RecipeResponse(RecipeDraft):
    id: str
    catalog_key: Optional[str] = None
    created_by: Optional[str] = None


class CatalogRecipe(RecipeDraft):
    key: str
    added: bool = False


class ImportRequest(BaseModel):
    url: Optional[str] = None
    text: Optional[str] = Field(None, max_length=200_000)

    @field_validator("url")
    @classmethod
    def link(cls, v):
        return web_url(v)

    @model_validator(mode="after")
    def one_source(self):
        if bool(self.url) == bool(self.text and self.text.strip()):
            raise ValueError("send a url or some text (one of them)")
        return self


class EventDraft(BaseModel):
    title: str
    start_dt: datetime
    end_dt: datetime
    all_day: bool
    location: Optional[str] = None
    description: Optional[str] = None


# ---- meal plan ----------------------------------------------------------------

class PlanSlotSet(BaseModel):
    recipe_id: Optional[str] = None
    title: Optional[str] = Field(None, max_length=128)
    note: Optional[str] = Field(None, max_length=256)

    @model_validator(mode="after")
    def something(self):
        if not self.recipe_id and not (self.title and self.title.strip()):
            raise ValueError("pick a recipe or type what's planned")
        return self


class PlanEntryIn(PlanSlotSet):
    day: date
    slot: Slot


class PlanWeekSet(BaseModel):
    entries: List[PlanEntryIn] = Field(default_factory=list, max_length=7 * len(SLOTS))


class PlanEntry(BaseModel):
    id: str
    day: date
    slot: str
    recipe_id: Optional[str]
    title: str
    note: Optional[str]


class PlanWeek(BaseModel):
    week_start: date
    days: List[date]
    entries: List[PlanEntry]


# ---- shopping -----------------------------------------------------------------

class ShoppingCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    quantity: Optional[str] = Field(None, max_length=64)


class ShoppingUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=256)
    quantity: Optional[str] = Field(None, max_length=64)
    checked: Optional[bool] = None
    base: Optional[dict] = None  # offline edits: the item as last seen (core.conflicts)


class ShoppingResponse(BaseModel):
    id: str
    name: str
    quantity: Optional[str]
    source: str
    recipe_id: Optional[str]
    recipe_title: Optional[str]
    week_start: Optional[date]
    checked: bool
    checked_at: Optional[datetime]
    checked_by: Optional[str]
    in_pantry: Optional[str] = None  # name of a pantry item that may cover it


class RegenerateResult(BaseModel):
    added: int
    removed: int
    week_start: date


# ---- pantry -------------------------------------------------------------------

class _PantryFields(BaseModel):
    quantity: Optional[float] = Field(None, ge=0, le=1_000_000)
    unit: Optional[str] = Field(None, max_length=32)
    low_at: Optional[float] = Field(None, ge=0, le=1_000_000)
    expires_on: Optional[date] = None


class PantryCreate(_PantryFields):
    name: str = Field(..., min_length=1, max_length=128)


class PantryUpdate(_PantryFields):
    name: Optional[str] = Field(None, min_length=1, max_length=128)


class PantryResponse(BaseModel):
    id: str
    name: str
    quantity: Optional[float]
    unit: Optional[str]
    low_at: Optional[float]
    expires_on: Optional[date]
    is_low: bool
    expired: bool
    expires_soon: bool
