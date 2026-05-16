from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


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
    def valid_hex(cls, v: str) -> str:
        if not v.startswith("#") or len(v) != 7:
            raise ValueError("color_hex must be #RRGGBB")
        int(v[1:], 16)
        return v

    @field_validator("provider")
    @classmethod
    def valid_provider(cls, v: str) -> str:
        if v not in ("internal", "ical"):
            raise ValueError('provider must be "internal" or "ical"')
        return v


class PatchCalendarSourceRequest(BaseModel):
    display_name: Optional[str] = None
    color_hex: Optional[str] = None
    ics_url: Optional[str] = None
    sync_interval_hours: Optional[int] = None
    enabled: Optional[bool] = None


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
    created_by: Optional[str] = None
    is_deleted: bool = False
    source_color_hex: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class CreateEventRequest(BaseModel):
    title: str
    start_dt: str
    end_dt: str
    all_day: bool = False
    location: Optional[str] = None
    description: Optional[str] = None


class PatchEventRequest(BaseModel):
    title: Optional[str] = None
    start_dt: Optional[str] = None
    end_dt: Optional[str] = None
    all_day: Optional[bool] = None
    location: Optional[str] = None
    description: Optional[str] = None


class SyncLogResponse(BaseModel):
    id: str
    source_id: str
    synced_at: datetime
    events_upserted: int
    events_deleted: int
    duration_ms: int
    error: Optional[str] = None

    model_config = {"from_attributes": True}
