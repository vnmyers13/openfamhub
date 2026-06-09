from sqlalchemy import Column, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column
from uuid import uuid4

from app.models.base import Base, TimestampMixin, SoftDeleteMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    avatar_emoji: Mapped[str] = mapped_column(Text, nullable=False, default="👤")
    pin_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(Text, nullable=False, default="member")
    settings_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_login_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class Event(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[str] = mapped_column(Text, nullable=False)
    end_time: Mapped[str] = mapped_column(Text, nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    assigned_to_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    color_hex: Mapped[str | None] = mapped_column(Text, nullable=True)


class CalendarSource(Base, TimestampMixin):
    __tablename__ = "calendar_sources"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    color_hex: Mapped[str] = mapped_column(Text, nullable=False, default="#3b82f6")
    sync_interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    last_synced_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class CalendarEvent(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(Text, ForeignKey("calendar_sources.id"), nullable=False)
    external_uid: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_time: Mapped[str] = mapped_column(Text, nullable=False)
    end_time: Mapped[str] = mapped_column(Text, nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    color_hex: Mapped[str] = mapped_column(Text, nullable=False, default="#3b82f6")
    synced_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class SyncLog(Base):
    __tablename__ = "sync_log"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[str] = mapped_column(Text, ForeignKey("calendar_sources.id"), nullable=False)
    events_imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    events_deleted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    errors: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    started_at: Mapped[str] = mapped_column(Text, nullable=False)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="success")


class Announcement(Base, TimestampMixin):
    __tablename__ = "announcements"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    author_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
