import uuid
from datetime import datetime

from sqlalchemy import JSON, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


class NoteBoard(Base):
    __tablename__ = "note_boards"
    __table_args__ = (Index("ix_note_boards_family", "family_id", unique=True),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String(80), nullable=False, default="Family notes")
    scene_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
