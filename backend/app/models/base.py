from sqlalchemy import Column, Text, Boolean, DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)


class SoftDeleteMixin:
    is_deleted = Column(Boolean, nullable=False, default=False)
