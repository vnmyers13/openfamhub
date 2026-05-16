import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CalendarEvent(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        Index("ix_calendar_events_source_dates", "source_id", "start_dt", "end_dt"),
        UniqueConstraint("source_id", "external_uid", name="uq_event_external_uid"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    external_uid: Mapped[str] = mapped_column(String(512), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    start_dt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_dt: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    all_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    location: Mapped[str] = mapped_column(String(256), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
