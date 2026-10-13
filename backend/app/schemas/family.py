import re
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, field_validator, model_validator

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


class FamilySettings(BaseModel):
    name: str
    timezone: str
    sleep: SleepSchedule


class FamilySettingsUpdate(BaseModel):
    name: Optional[str] = None
    timezone: Optional[str] = None
    sleep: Optional[SleepSchedule] = None

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
