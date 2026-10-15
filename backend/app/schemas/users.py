import re
from datetime import date
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas import validators as v


class _UserFields(BaseModel):
    """Fields shared by create and update, with one copy of each rule."""

    email: Optional[str] = None
    password: Optional[str] = None
    pin: Optional[str] = None
    color_hex: Optional[str] = None
    ui_mode: Optional[str] = None
    role: Optional[str] = None
    avatar: Optional[str] = None  # an emoji, shown in the sign-in picker
    birthday: Optional[date] = None  # send null on update to clear it

    @field_validator("birthday")
    @classmethod
    def check_birthday(cls, x):
        if x is not None and not date(1900, 1, 1) <= x <= date.today():
            raise ValueError("birthday must be a past date")
        return x

    @field_validator("password")
    @classmethod
    def check_password(cls, x):
        return v.password(x)

    @field_validator("pin")
    @classmethod
    def check_pin(cls, x):
        return v.pin(x)

    @field_validator("color_hex")
    @classmethod
    def check_color(cls, x):
        return v.hex_color(x)

    @field_validator("role")
    @classmethod
    def check_role(cls, x):
        return v.role(x)

    @field_validator("ui_mode")
    @classmethod
    def check_ui_mode(cls, x):
        return v.ui_mode(x)

    @field_validator("avatar")
    @classmethod
    def check_avatar(cls, x):
        return v.avatar(x)


class CreateUserRequest(_UserFields):
    display_name: str

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, x):
        return v.display_name(x)


class UpdateUserRequest(_UserFields):
    display_name: Optional[str] = None

    @field_validator("display_name")
    @classmethod
    def check_display_name(cls, x):
        return v.display_name(x)


class SetPinRequest(BaseModel):
    pin: str

    @field_validator("pin")
    @classmethod
    def check_pin(cls, x):
        return v.pin(x)


class UserResponse(BaseModel):
    id: str
    display_name: str
    email: Optional[str] = None
    role: str
    color_hex: str
    ui_mode: str
    avatar_type: Optional[str] = None
    avatar_value: Optional[str] = None
    family_id: str
    has_password: bool = False
    has_pin: bool = False
    birthday: Optional[date] = None
    last_login_at: Optional[str] = None
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}


# ---- personal preferences (Phase 8) --------------------------------------------
WIDGET_KEYS = ("events", "weather", "my-day", "meals", "stars", "announcements", "birthdays", "sync")
WALLPAPERS = ("none", "dusk", "ocean", "forest", "sunrise", "photo")


class DashboardWidget(BaseModel):
    key: Literal[WIDGET_KEYS]  # type: ignore[valid-type]
    size: Literal["normal", "wide"] = "normal"


class DashboardPage(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    widgets: List[DashboardWidget] = Field(default_factory=list, max_length=len(WIDGET_KEYS))

    @model_validator(mode="after")
    def no_repeats(self):
        keys = [w.key for w in self.widgets]
        if len(keys) != len(set(keys)):
            raise ValueError("a widget can appear once per page")
        return self


_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class NotificationPrefs(BaseModel):
    """Which reminders a person gets on their devices (Phase 11)."""

    events: Literal["off", "mine", "all"] = "off"  # events they added, or every timed family event
    event_minutes: Literal[5, 10, 15, 30, 60] = 15
    daily: bool = True  # a nudge with today's chores and to-dos
    daily_time: str = "07:00"  # HH:MM, family timezone
    rewards: bool = True  # admins: reward requests waiting for a yes
    birthdays: bool = True  # the day before someone's birthday, at daily_time
    pantry: bool = True  # members and admins: food reaching its use-by date, at daily_time
    allowance: bool = True  # their weekly allowance was paid

    @field_validator("daily_time")
    @classmethod
    def hhmm(cls, v: str) -> str:
        if not _HHMM.match(v):
            raise ValueError("times are HH:MM, 24-hour")
        return v


class Preferences(BaseModel):
    """How one person likes the app: where the menu goes, their dashboard
    pages, wallpaper, and whether the calendar shows the family or just them."""

    nav: Literal["side", "top"] = "side"
    calendar_scope: Literal["family", "mine"] = "family"
    wallpaper: Literal[WALLPAPERS] = "none"  # type: ignore[valid-type]
    wallpaper_media_id: Optional[str] = Field(None, max_length=64)
    pages: List[DashboardPage] = Field(default_factory=list, max_length=6)  # empty = the default page
    notifications: NotificationPrefs = Field(default_factory=NotificationPrefs)
