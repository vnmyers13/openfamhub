"""Phase 8: books (personal lists and the family library) and announcements.
Birthdays are a column on users; weather settings live in the family's
settings_json."""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


def _id() -> str:
    return str(uuid.uuid4())


class Book(Base):
    """A book on someone's list (owner_id set) or on the family shelf
    (owner_id null). reader_id is whoever is reading or finished it; for a
    personal book that's the owner. Finishing a book credits its reader once
    (points ledger, source "book", keyed by book and reader)."""

    __tablename__ = "books"
    __table_args__ = (Index("ix_books_family", "family_id", "owner_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    owner_id: Mapped[str] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    author: Mapped[str] = mapped_column(String(256), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="want_to_read")  # want_to_read|reading|finished
    reader_id: Mapped[str] = mapped_column(String, nullable=True)
    finished_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    added_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (Index("ix_announcements_family", "family_id", "pinned"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    author_id: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
