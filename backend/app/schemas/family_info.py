from datetime import date, datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

BookStatus = Literal["want_to_read", "reading", "finished"]


def _text(v: Optional[str], limit: int, what: str) -> Optional[str]:
    if v is None:
        return v
    v = v.strip()
    if not 1 <= len(v) <= limit:
        raise ValueError(f"{what} must be 1-{limit} characters")
    return v


# ---- books --------------------------------------------------------------------

class BookCreate(BaseModel):
    title: str
    author: Optional[str] = Field(None, max_length=256)
    notes: Optional[str] = Field(None, max_length=2000)
    status: BookStatus = "want_to_read"
    shelf: Literal["mine", "family"] = "mine"  # "family" puts it in the shared library

    @field_validator("title")
    @classmethod
    def title_length(cls, v):
        return _text(v, 256, "title")


class BookUpdate(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = Field(None, max_length=256)
    notes: Optional[str] = Field(None, max_length=2000)
    status: Optional[BookStatus] = None

    @field_validator("title")
    @classmethod
    def title_length(cls, v):
        return _text(v, 256, "title")


class BookResponse(BaseModel):
    id: str
    title: str
    author: Optional[str]
    notes: Optional[str]
    status: str
    owner_id: Optional[str]
    reader_id: Optional[str]
    finished_at: Optional[datetime]
    added_by: Optional[str]
    points_awarded: bool = False  # this change earned the reader BOOK_POINTS


# ---- announcements ------------------------------------------------------------

class AnnouncementCreate(BaseModel):
    body: str
    pinned: bool = False

    @field_validator("body")
    @classmethod
    def body_length(cls, v):
        return _text(v, 1000, "announcement")


class AnnouncementUpdate(BaseModel):
    body: Optional[str] = None
    pinned: Optional[bool] = None

    @field_validator("body")
    @classmethod
    def body_length(cls, v):
        return _text(v, 1000, "announcement")


class AnnouncementResponse(BaseModel):
    id: str
    body: str
    pinned: bool
    author_id: Optional[str]
    created_at: datetime


# ---- weather -------------------------------------------------------------------

class WeatherLocation(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    units: Literal["fahrenheit", "celsius"] = "fahrenheit"


class WeatherDay(BaseModel):
    date: date
    emoji: str
    label: str
    high: Optional[int]
    low: Optional[int]
    precip_chance: Optional[int]


class WeatherResponse(BaseModel):
    configured: bool
    place: Optional[str] = None
    units: Optional[str] = None
    temperature: Optional[int] = None
    emoji: Optional[str] = None
    label: Optional[str] = None
    wind: Optional[int] = None
    days: List[WeatherDay] = []
    error: Optional[str] = None


class Place(BaseModel):
    name: str
    latitude: float
    longitude: float


# ---- birthdays and the dashboard -------------------------------------------------

class UpcomingBirthday(BaseModel):
    user_id: str
    display_name: str
    color_hex: str
    avatar_value: Optional[str]
    date: date
    turns: int
    days_away: int


class ChoreCounts(BaseModel):
    mine_open: int
    mine_done: int
    family_open: int
    family_done: int


class MealToday(BaseModel):
    day: date
    slot: str
    title: str
    recipe_id: Optional[str]


class DashboardSummary(BaseModel):
    today: date
    events_today: List[dict]
    chores: ChoreCounts
    points_balance: int
    allowance_cents: int
    meals_today: List[MealToday]
    meals_week: List[MealToday]
    birthdays: List[UpcomingBirthday]
    announcements: List[AnnouncementResponse]
