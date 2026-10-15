from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from app.schemas import validators


class CalendarSourceResponse(BaseModel):
    id: str
    family_id: str
    provider: str
    display_name: str
    color_hex: str
    ics_url: Optional[str] = None
    sync_interval_hours: float
    last_synced_at: Optional[datetime] = None
    sync_error: Optional[str] = None
    enabled: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreateCalendarSourceRequest(BaseModel):
    display_name: str
    color_hex: str = "#4F46E5"
    provider: str = "ical"
    ics_url: Optional[str] = None
    sync_interval_hours: int = 6

    @field_validator("color_hex")
    @classmethod
    def check_color(cls, x):
        return validators.hex_color(x)

    @field_validator("provider")
    @classmethod
    def valid_provider(cls, v: str) -> str:
        # The family's single internal source is created on demand by the
        # server and is protected from deletion; clients can only add feeds.
        if v != "ical":
            raise ValueError('provider must be "ical"')
        return v


class PatchCalendarSourceRequest(BaseModel):
    display_name: Optional[str] = None
    color_hex: Optional[str] = None
    ics_url: Optional[str] = None
    sync_interval_hours: Optional[int] = Field(None, ge=1, le=168)
    enabled: Optional[bool] = None

    @field_validator("color_hex")
    @classmethod
    def check_color(cls, x):
        return validators.hex_color(x)

    @field_validator("display_name")
    @classmethod
    def check_name(cls, x):
        return validators.display_name(x).strip() if x is not None else x

    @field_validator("ics_url")
    @classmethod
    def check_url(cls, x):
        return validators.feed_url(x)


class CalendarEventResponse(BaseModel):
    id: str
    source_id: str
    family_id: str
    external_uid: Optional[str] = None
    title: str
    start_dt: str
    end_dt: str
    all_day: bool = False
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None
    organizer: Optional[str] = None
    attendees: Optional[List[str]] = None
    created_by: Optional[str] = None
    is_deleted: bool = False
    source_color_hex: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


def _event_link(v: Optional[str]) -> Optional[str]:
    """A web link on an event: http(s) only; "" clears it."""
    if v is None:
        return v
    v = v.strip()
    if v and (not v.lower().startswith(("http://", "https://")) or len(v) > 2048 or " " in v):
        raise ValueError("Use an http:// or https:// link")
    return v


class CreateEventRequest(BaseModel):
    title: str
    start_dt: str
    end_dt: str
    all_day: bool = False
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None

    @field_validator("url")
    @classmethod
    def link(cls, v: Optional[str]) -> Optional[str]:
        return _event_link(v)


class PatchEventRequest(BaseModel):
    title: Optional[str] = None
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    all_day: Optional[bool] = None
    location: Optional[str] = None
    description: Optional[str] = None
    url: Optional[str] = None  # "" clears it

    @field_validator("url")
    @classmethod
    def link(cls, v: Optional[str]) -> Optional[str]:
        return _event_link(v)


class SyncLogResponse(BaseModel):
    id: str
    source_id: str
    synced_at: datetime
    events_upserted: int
    events_deleted: int
    duration_ms: int
    error: Optional[str] = None

    model_config = {"from_attributes": True}
