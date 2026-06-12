from uuid import uuid4

from sqlalchemy import Column, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Book(Base, TimestampMixin):
    __tablename__ = "books"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="want_to_read")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
