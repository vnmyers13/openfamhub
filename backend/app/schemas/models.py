from pydantic import BaseModel, Field
from typing import Optional


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    avatar_emoji: str = Field(default="👤", min_length=1, max_length=2)
    pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d+$")
    role: str = Field(default="member", pattern=r"^(admin|member)$")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    avatar_emoji: Optional[str] = Field(None, min_length=1, max_length=2)
    pin: Optional[str] = Field(None, min_length=4, max_length=6, pattern=r"^\d+$")
    role: Optional[str] = Field(None, pattern=r"^(admin|member)$")
    is_active: Optional[bool] = None


class UserResponse(BaseModel):
    id: str
    name: str
    avatar_emoji: str
    role: str
    is_active: bool
    last_login_at: Optional[str] = None
    created_at: str
    updated_at: str


class ProfileResponse(BaseModel):
    id: str
    name: str
    avatar_emoji: str
    is_active: bool


class LoginRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=6, pattern=r"^\d+$")


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class EventCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: str
    end_time: str
    is_all_day: bool = False
    assigned_to_id: Optional[str] = None
    color_hex: Optional[str] = None


class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    is_all_day: Optional[bool] = None
    assigned_to_id: Optional[str] = None
    color_hex: Optional[str] = None


class EventResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: str
    end_time: str
    is_all_day: bool
    created_by_id: str
    assigned_to_id: Optional[str] = None
    color_hex: Optional[str] = None
    created_at: str
    updated_at: str


class CalendarSourceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    url: str = Field(..., min_length=1)
    color_hex: str = Field(default="#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")
    sync_interval_hours: int = Field(default=4, ge=1, le=168)


class CalendarSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    color_hex: Optional[str] = None
    sync_interval_hours: Optional[int] = None
    is_active: Optional[bool] = None


class CalendarSourceResponse(BaseModel):
    id: str
    name: str
    url: str
    color_hex: str
    sync_interval_hours: int
    last_synced_at: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str


class CalendarEventResponse(BaseModel):
    id: str
    source_id: str
    external_uid: str
    title: str
    description: Optional[str] = None
    location: Optional[str] = None
    start_time: str
    end_time: str
    all_day: bool
    color_hex: str
    synced_at: Optional[str] = None


class SyncLogResponse(BaseModel):
    id: str
    source_id: str
    events_imported: int
    events_deleted: int
    errors: list[str]
    started_at: str
    completed_at: Optional[str] = None
    status: str


class AnnouncementCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


class AnnouncementResponse(BaseModel):
    id: str
    author_id: str
    content: str
    is_pinned: bool
    created_at: str
    updated_at: str
