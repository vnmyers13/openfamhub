import re
from typing import List, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field, field_validator, model_validator

_HHMM = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class SleepSchedule(BaseModel):
    """When the wall screen goes dark (off) and comes back (on), as HH:MM in the
    family timezone. off later than on means overnight (e.g. 22:00 -> 06:30)."""

    enabled: bool = False
    off: str = "22:00"
    on: str = "06:30"

    @field_validator("off", "on")
    @classmethod
    def hhmm(cls, v: str) -> str:
        if not _HHMM.match(v):
            raise ValueError("times are HH:MM, 24-hour")
        return v

    @model_validator(mode="after")
    def distinct(self):
        if self.off == self.on:
            raise ValueError("off and on times must differ")
        return self


def _known_zone(v: str) -> str:
    try:
        ZoneInfo(v)
    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("unknown timezone; use an IANA name such as America/Detroit")
    return v


MAX_CLOCKS = 3


class WorldClock(BaseModel):
    """An extra clock on the wall (Phase 10): a label and an IANA timezone."""

    label: str
    timezone: str

    @field_validator("label")
    @classmethod
    def label_length(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 40:
            raise ValueError("a clock's label must be 1-40 characters")
        return v

    @field_validator("timezone")
    @classmethod
    def clock_zone(cls, v: str) -> str:
        return _known_zone(v)


class FamilySettings(BaseModel):
    name: str
    timezone: str
    sleep: SleepSchedule
    clocks: List[WorldClock] = []


class FamilySettingsUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    sleep: Optional[SleepSchedule] = None
    clocks: Optional[List[WorldClock]] = Field(None, max_length=MAX_CLOCKS)

    @field_validator("name")
    @classmethod
    def name_length(cls, v):
        if v is not None and not 1 <= len(v.strip()) <= 128:
            raise ValueError("name must be 1-128 characters")
        return v.strip() if v is not None else v

    @field_validator("timezone")
    @classmethod
    def known_zone(cls, v):
        if v is None:
            return v
        try:
            ZoneInfo(v)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("unknown timezone; use an IANA name such as America/Detroit")
        return v


WallDashboardWidgetKey = Literal[
    "clock", "events", "chores", "routines", "meals", "weather", "announcements", "progress", "birthdays", "home", "notes"
]


class WallDashboardWidget(BaseModel):
    key: WallDashboardWidgetKey
    size: Literal["normal", "wide"] = "normal"


class WallDashboardPage(BaseModel):
    name: str
    duration_seconds: int = Field(default=30, ge=5, le=300)
    widgets: list[WallDashboardWidget] = Field(default_factory=list, max_length=8)

    @field_validator("name")
    @classmethod
    def name_length(cls, v: str) -> str:
        v = v.strip()
        if not 1 <= len(v) <= 40:
            raise ValueError("name must be 1-40 characters")
        return v


class WallDashboardConfig(BaseModel):
    pages: list[WallDashboardPage] = Field(default_factory=list, max_length=6)


DEFAULT_WALL_DASHBOARD = WallDashboardConfig(
    pages=[
        WallDashboardPage(
            name="Today",
            widgets=[
                WallDashboardWidget(key="events", size="wide"),
                WallDashboardWidget(key="weather"),
                WallDashboardWidget(key="meals"),
            ],
        ),
        WallDashboardPage(
            name="Family",
            widgets=[
                WallDashboardWidget(key="routines", size="wide"),
                WallDashboardWidget(key="progress", size="wide"),
            ],
        ),
        WallDashboardPage(
            name="Notes",
            widgets=[
                WallDashboardWidget(key="announcements", size="wide"),
                WallDashboardWidget(key="birthdays"),
            ],
        ),
    ]
)
