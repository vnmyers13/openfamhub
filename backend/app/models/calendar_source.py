import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CalendarSource(Base):
    __tablename__ = "calendar_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False, default="internal")
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    color_hex: Mapped[str] = mapped_column(String(7), nullable=False, default="#4F46E5")
    ics_url: Mapped[str] = mapped_column(String(1024), nullable=True)
    sync_interval_hours: Mapped[float] = mapped_column(Float, nullable=False, default=6.0)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_error: Mapped[str] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
