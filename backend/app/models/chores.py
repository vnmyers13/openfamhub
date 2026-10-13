"""Phase 5: chores, routines, to-dos and the points ledger.

Dates a family thinks in (when a chore is due, when a to-do is due, when a
chore or routine starts repeating) are plain `Date`s in the family's own
timezone. Moments (claimed, completed) are UTCDateTime like everything else.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.core.types import UTCDateTime


def _id() -> str:
    return str(uuid.uuid4())


class ChoreTemplate(Base):
    """A chore and how it repeats. Routine steps are templates with a routine_id."""

    __tablename__ = "chore_templates"
    __table_args__ = (Index("ix_chore_templates_family", "family_id", "is_active"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assignment: Mapped[str] = mapped_column(String(16), nullable=False, default="assigned")  # assigned | claimable
    assigned_to: Mapped[str] = mapped_column(String, nullable=True)
    # {"every": "none|day|week|month", "interval": n, "weekdays": ["mo",...], "month_day": 1..28 or -1}
    repeat: Mapped[dict] = mapped_column(JSON, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    routine_id: Mapped[str] = mapped_column(String, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    minutes: Mapped[int] = mapped_column(Integer, nullable=True)  # routine step length
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class ChoreInstance(Base):
    """One occurrence of a chore on a family-local date."""

    __tablename__ = "chore_instances"
    __table_args__ = (
        UniqueConstraint("template_id", "due_date", name="uq_chore_instance_template_date"),
        Index("ix_chore_instances_family_date", "family_id", "due_date"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    template_id: Mapped[str] = mapped_column(String, nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    assigned_to: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending|claimed|completed|missed
    claimed_by: Mapped[str] = mapped_column(String, nullable=True)
    claimed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    completed_by: Mapped[str] = mapped_column(String, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class ChoreCompletion(Base):
    """Audit log: who completed which chore, who got the points, and any undo."""

    __tablename__ = "chore_completions"
    __table_args__ = (Index("ix_chore_completions_family", "family_id", "completed_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    instance_id: Mapped[str] = mapped_column(String, nullable=False)
    completed_by: Mapped[str] = mapped_column(String, nullable=False)
    credited_to: Mapped[str] = mapped_column(String, nullable=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    undone_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    undone_by: Mapped[str] = mapped_column(String, nullable=True)


class PointsEntry(Base):
    """Append-only points ledger. A balance is the sum of a member's deltas;
    nothing is ever updated or deleted. (source_type, source_id) is unique, so
    one event can never credit twice."""

    __tablename__ = "points_ledger"
    __table_args__ = (
        UniqueConstraint("source_type", "source_id", name="uq_points_source"),
        Index("ix_points_family_user", "family_id", "user_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    user_id: Mapped[str] = mapped_column(String, nullable=False)
    delta: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())


class Routine(Base):
    """An ordered group of steps (chore templates) done together, e.g. a morning routine."""

    __tablename__ = "routines"
    __table_args__ = (Index("ix_routines_family", "family_id", "is_active"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    assigned_to: Mapped[str] = mapped_column(String, nullable=True)
    start_time: Mapped[str] = mapped_column(String(5), nullable=True)  # HH:MM, family timezone
    repeat: Mapped[dict] = mapped_column(JSON, nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())


class Todo(Base):
    """A one-off family task: no repeat, no points."""

    __tablename__ = "todos"
    __table_args__ = (Index("ix_todos_family", "family_id", "completed_at"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_id)
    family_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=True)
    assigned_to: Mapped[str] = mapped_column(String, nullable=True)
    due_date: Mapped[date] = mapped_column(Date, nullable=True)
    completed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=True)
    completed_by: Mapped[str] = mapped_column(String, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), server_default=func.now(), onupdate=func.now())
