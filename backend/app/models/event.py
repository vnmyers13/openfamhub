from datetime import date, datetime, timezone
from uuid import uuid4

from sqlalchemy import Column, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column

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


class Chore(Base, TimestampMixin):
    __tablename__ = "chores"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    assignment_mode: Mapped[str] = mapped_column(Text, nullable=False, default="assigned")
    recurrence_rule: Mapped[str] = mapped_column(Text, nullable=False)
    default_assigned_to_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    point_value: Mapped[int] = mapped_column(Integer, nullable=False, default=10)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)


class ChoreInstance(Base, TimestampMixin):
    __tablename__ = "chore_instances"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    chore_template_id: Mapped[str] = mapped_column(Text, ForeignKey("chores.id"), nullable=False)
    assigned_to_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    due_date: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    claimed_by_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    claimed_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_by_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    completed_at: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChoreCompletionLog(Base):
    __tablename__ = "chore_completion_logs"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    instance_id: Mapped[str] = mapped_column(Text, ForeignKey("chore_instances.id"), nullable=False)
    completed_by_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    completed_at: Mapped[str] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    points_earned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RewardPointsLedger(Base):
    __tablename__ = "reward_points_ledger"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    points: Mapped[int] = mapped_column(Integer, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    reference_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class AllowanceLedger(Base):
    __tablename__ = "allowance_ledger"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    amount: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    reference_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(Text, nullable=False)


class Reward(Base, TimestampMixin):
    __tablename__ = "rewards"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    point_cost: Mapped[int] = mapped_column(Integer, nullable=False)
    is_auto_fulfill: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)


class RewardRequest(Base):
    __tablename__ = "reward_requests"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    reward_id: Mapped[str] = mapped_column(Text, ForeignKey("rewards.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    requested_at: Mapped[str] = mapped_column(Text, nullable=False)
    approved_at: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_by_id: Mapped[str | None] = mapped_column(Text, ForeignKey("users.id"), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class BadgeDefinition(Base, TimestampMixin):
    __tablename__ = "badge_definitions"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_value: Mapped[int] = mapped_column(Integer, nullable=False)
    points_reward: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class UserBadge(Base):
    __tablename__ = "user_badges"

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), nullable=False)
    badge_definition_id: Mapped[str] = mapped_column(Text, ForeignKey("badge_definitions.id"), nullable=False)
    earned_at: Mapped[str] = mapped_column(Text, nullable=False)


class UserStreak(Base):
    __tablename__ = "user_streaks"

    user_id: Mapped[str] = mapped_column(Text, ForeignKey("users.id"), primary_key=True)
    current_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_completion_date: Mapped[str | None] = mapped_column(Text, nullable=True)
    grace_days: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
