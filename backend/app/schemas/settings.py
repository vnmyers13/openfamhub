from pydantic import BaseModel, Field
from typing import Optional


VALID_TIMEZONES = [
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
    "UTC",
]


class TimezoneSettingsResponse(BaseModel):
    timezone: str = Field(default="UTC")
