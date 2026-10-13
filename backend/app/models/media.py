import uuid
from datetime import datetime

from sqlalchemy import Float, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


class Media(Base):
    """A photo or video in the family library, shown by the wall's slideshow.

    Only processed renditions are stored (wall-sized + thumbnail), never the
    uploaded original, so location metadata never reaches the disk for long.
    Files live under data/photos/media/<family_id>/<id>/ (services/media.py).
    """

    __tablename__ = "media"
    __table_args__ = (Index("ix_media_family_created", "family_id", "created_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String, nullable=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)  # photo | video
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="processing")  # processing | ready | failed
    error: Mapped[str] = mapped_column(Text, nullable=True)
    original_name: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    width: Mapped[int] = mapped_column(Integer, nullable=True)
    height: Mapped[int] = mapped_column(Integer, nullable=True)
    duration_s: Mapped[float] = mapped_column(Float, nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
